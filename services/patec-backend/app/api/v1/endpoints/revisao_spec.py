"""
Endpoints da revisão de especificação — caminho lateral (blocos 35-41).

POST /pareceres/{id}/spec-versoes                 — upload da nova revisão (R4 em background)
GET  /pareceres/{id}/spec-versoes                 — histórico de revisões
GET  /pareceres/{id}/spec-versoes/{vid}           — detalhe com diff
GET  /pareceres/{id}/spec-versoes/{vid}/progresso — polling da comparação
POST /pareceres/{id}/spec-versoes/{vid}/aplicar   — W7
POST /pareceres/{id}/spec-versoes/{vid}/descartar
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.progress import get_progress
from app.models.parecer import Parecer
from app.models.versao_especificacao import VersaoEspecificacao
from app.services.audit import registrar_auditoria
from app.services.state_machine import ANALISE, CICLO_FORNECEDOR, VERIFICACAO_FINAL

router = APIRouter(prefix="/pareceres/{parecer_id}/spec-versoes", tags=["revisao-spec"])

_FASES_PERMITIDAS = {ANALISE, CICLO_FORNECEDOR, VERIFICACAO_FINAL}


class VersaoSpecResponse(BaseModel):
    id: str
    numero_versao: int
    status: str
    cenario: str | None
    resumo_diff: dict | None
    erro_detalhe: str | None
    fase_caso_anterior: str | None
    aplicado_em: str | None
    criado_em: str


def _to_response(v: VersaoEspecificacao) -> VersaoSpecResponse:
    return VersaoSpecResponse(
        id=str(v.id),
        numero_versao=v.numero_versao,
        status=v.status,
        cenario=v.cenario,
        resumo_diff=v.resumo_diff,
        erro_detalhe=v.erro_detalhe,
        fase_caso_anterior=v.fase_caso_anterior,
        aplicado_em=v.aplicado_em.isoformat() if v.aplicado_em else None,
        criado_em=v.criado_em.isoformat(),
    )


async def _get_versao(
    parecer_id: uuid.UUID, versao_id: uuid.UUID, db: AsyncSession
) -> VersaoEspecificacao:
    result = await db.execute(
        select(VersaoEspecificacao).where(
            VersaoEspecificacao.id == versao_id,
            VersaoEspecificacao.parecer_id == parecer_id,
        )
    )
    versao = result.scalar_one_or_none()
    if not versao:
        raise HTTPException(status_code=404, detail="Versao nao encontrada neste parecer.")
    return versao


@router.post("", response_model=VersaoSpecResponse, status_code=202)
async def criar_versao(
    parecer_id: uuid.UUID,
    request: Request,
    arquivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin", "analista")),
):
    """
    Bloco 35: o engenheiro sobe a nova revisão do documento de engenharia.
    A comparação contra os requisitos do BD (R4) roda em background.
    """
    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")
    if parecer.fase_caso not in _FASES_PERMITIDAS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Revisao de especificacao disponivel apenas com requisitos "
                f"aprovados e caso aberto (fase atual: {parecer.fase_caso})."
            ),
        )
    if parecer.revisao_spec_em_andamento:
        raise HTTPException(
            status_code=400,
            detail="Ja existe uma revisao de especificacao em andamento neste caso.",
        )

    from app.api.v1.endpoints.documentos import _upload_doc

    # Indexacao RAG adiada: roda DEPOIS do diff R4 (spec_diff) para nao concorrer
    # com a comparacao pela cota da LLM (evita 429 durante a comparacao).
    doc_response = await _upload_doc(
        parecer_id, "engenharia", arquivo, db, enfileirar_indexacao=False
    )

    proxima = await db.scalar(
        select(func.max(VersaoEspecificacao.numero_versao)).where(
            VersaoEspecificacao.parecer_id == parecer_id
        )
    )
    versao = VersaoEspecificacao(
        parecer_id=parecer_id,
        numero_versao=(proxima or 0) + 1,
        documento_id=uuid.UUID(doc_response.id),
        status="EM_COMPARACAO",
        fase_caso_anterior=parecer.fase_caso,
        criado_em=datetime.utcnow(),
    )
    db.add(versao)
    parecer.revisao_spec_em_andamento = True
    await db.commit()
    await db.refresh(versao)

    from app.services.spec_diff import start_spec_diff_in_background

    task_id = start_spec_diff_in_background(str(versao.id))

    await registrar_auditoria(
        db, current_user, "criar_revisao_spec", "versao_especificacao",
        recurso_id=str(versao.id),
        detalhes=f"numero_versao={versao.numero_versao}, doc={doc_response.nome_arquivo}, task={task_id}",
        request=request,
    )
    await db.commit()

    return _to_response(versao)


@router.get("", response_model=list[VersaoSpecResponse])
async def listar_versoes(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(VersaoEspecificacao)
        .where(VersaoEspecificacao.parecer_id == parecer_id)
        .order_by(VersaoEspecificacao.numero_versao)
    )
    return [_to_response(v) for v in result.scalars().all()]


@router.get("/{versao_id}", response_model=VersaoSpecResponse)
async def detalhar_versao(
    parecer_id: uuid.UUID,
    versao_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    versao = await _get_versao(parecer_id, versao_id, db)
    return _to_response(versao)


@router.get("/{versao_id}/progresso")
async def progresso_versao(
    parecer_id: uuid.UUID,
    versao_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    versao = await _get_versao(parecer_id, versao_id, db)
    progress = get_progress(f"specdiff:{versao_id}") or {}
    return {
        "status": versao.status,
        "cenario": versao.cenario,
        "percent": progress.get("percent"),
        "message": progress.get("message"),
        "stage": progress.get("stage"),
    }


class AplicarRevisaoRequest(BaseModel):
    incluir_novos: list[int] = []  # índices (0-based) dos novos aceitos (bloco 40)


class AplicarRevisaoResponse(BaseModel):
    cenario: str | None
    reabertos: int
    desativados: int
    incluidos: int
    fase_caso: str
    mensagem: str


@router.post("/{versao_id}/aplicar", response_model=AplicarRevisaoResponse)
async def aplicar_versao(
    parecer_id: uuid.UUID,
    versao_id: uuid.UUID,
    payload: AplicarRevisaoRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin", "analista")),
):
    """
    Operação W7 (blocos 38-41): aplica o diff. No cenário C os alterados e
    removidos são obrigatórios; `incluir_novos` lista os novos aceitos pelo
    engenheiro. O caso regride para CICLO_FORNECEDOR quando há mudanças.
    """
    versao = await _get_versao(parecer_id, versao_id, db)
    if versao.status != "AGUARDANDO_DECISAO":
        raise HTTPException(
            status_code=400,
            detail=f"Versao nao aguarda decisao (status: {versao.status}).",
        )

    from app.services.spec_diff import aplicar_revisao_sync

    usuario_id = getattr(current_user, "id", None)
    resultado = await db.run_sync(
        lambda sync_db: aplicar_revisao_sync(
            sync_db, versao, payload.incluir_novos, usuario_id
        )
    )

    await registrar_auditoria(
        db, current_user, "w7_aplicar_revisao_spec", "versao_especificacao",
        recurso_id=str(versao.id),
        detalhes=(
            f"cenario={resultado['cenario']}, reabertos={resultado['reabertos']}, "
            f"desativados={resultado['desativados']}, incluidos={resultado['incluidos']}"
        ),
        request=request,
    )
    await db.commit()

    if resultado["reabertos"] or resultado["incluidos"]:
        mensagem = (
            "Revisao aplicada (W7). Itens alterados/novos voltaram como pendencia — "
            "exporte o parecer com os destaques e envie ao fornecedor."
        )
    elif resultado["desativados"]:
        mensagem = "Revisao aplicada (W7): itens removidos foram desativados."
    else:
        mensagem = "Revisao aplicada sem mudancas nos itens."

    return AplicarRevisaoResponse(**resultado, mensagem=mensagem)


@router.post("/{versao_id}/recomparar", response_model=VersaoSpecResponse, status_code=202)
async def recomparar_versao(
    parecer_id: uuid.UUID,
    versao_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin", "analista")),
):
    """Reexecuta a comparação R4 de uma versão que falhou (ex: 429 transitório).

    Reaproveita o mesmo documento já enviado — não exige novo upload.
    """
    versao = await _get_versao(parecer_id, versao_id, db)
    if versao.status != "ERRO":
        raise HTTPException(
            status_code=400,
            detail=f"So e possivel recomparar uma versao com erro (status: {versao.status}).",
        )

    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if parecer and parecer.revisao_spec_em_andamento:
        raise HTTPException(
            status_code=400,
            detail="Ja existe uma revisao de especificacao em andamento neste caso.",
        )

    versao.status = "EM_COMPARACAO"
    versao.erro_detalhe = None
    versao.cenario = None
    versao.resumo_diff = None
    if parecer:
        parecer.revisao_spec_em_andamento = True
    await db.commit()
    await db.refresh(versao)

    from app.services.spec_diff import start_spec_diff_in_background

    task_id = start_spec_diff_in_background(str(versao.id))

    await registrar_auditoria(
        db, current_user, "recomparar_revisao_spec", "versao_especificacao",
        recurso_id=str(versao.id),
        detalhes=f"numero_versao={versao.numero_versao}, task={task_id}",
        request=request,
    )
    await db.commit()

    return _to_response(versao)


@router.post("/{versao_id}/descartar", response_model=VersaoSpecResponse)
async def descartar_versao(
    parecer_id: uuid.UUID,
    versao_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin", "analista")),
):
    """Descarta uma comparação sem aplicar (o documento permanece no histórico)."""
    versao = await _get_versao(parecer_id, versao_id, db)
    if versao.status not in ("AGUARDANDO_DECISAO", "ERRO"):
        raise HTTPException(
            status_code=400,
            detail=f"Versao nao pode ser descartada (status: {versao.status}).",
        )

    versao.status = "DESCARTADA"
    parecer_result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = parecer_result.scalar_one_or_none()
    if parecer:
        parecer.revisao_spec_em_andamento = False

    await registrar_auditoria(
        db, current_user, "descartar_revisao_spec", "versao_especificacao",
        recurso_id=str(versao.id),
        detalhes=f"numero_versao={versao.numero_versao}",
        request=request,
    )
    await db.commit()
    await db.refresh(versao)

    return _to_response(versao)
