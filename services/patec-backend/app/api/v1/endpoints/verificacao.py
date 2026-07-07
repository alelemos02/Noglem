"""
Endpoints da verificação final e fechamento do caso (blocos 29-34 + terminais).

GET  /pareceres/{id}/verificacao-final            — estado + bifurcação (bloco 29)
POST /pareceres/{id}/verificacao-final/executar   — dispara R3 (blocos 31-32)
GET  /pareceres/{id}/verificacao-final/progresso  — polling da task
POST /pareceres/{id}/verificacao-final/validar    — W5 (bloco 33)
POST /pareceres/{id}/fechar                       — W6 (bloco 34 + terminais)
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.progress import get_progress
from app.models.parecer import Parecer
from app.models.rodada_fornecedor import TIPO_PROPOSTA_REVISADA, RodadaFornecedor
from app.models.verificacao_final import VerificacaoFinal
from app.services.audit import registrar_auditoria
from app.services.state_machine import (
    CICLO_FORNECEDOR,
    DESFECHOS,
    FECHADO,
    VERIFICACAO_FINAL,
)

router = APIRouter(prefix="/pareceres", tags=["verificacao-final"])

_RESULTADOS_VALIDADOS = {"CONFORME", "CONFORME_COM_PENDENCIA", "NAO_CONFORME"}


class VerificacaoFinalResponse(BaseModel):
    id: str
    ia_dispensada: bool
    status: str
    rodada_fornecedor_id: str | None
    resultado_ia: dict | None
    resultado_validado: str | None
    observacoes: str | None
    validado_em: str | None


def _to_response(v: VerificacaoFinal) -> VerificacaoFinalResponse:
    return VerificacaoFinalResponse(
        id=str(v.id),
        ia_dispensada=v.ia_dispensada,
        status=v.status,
        rodada_fornecedor_id=str(v.rodada_fornecedor_id) if v.rodada_fornecedor_id else None,
        resultado_ia=v.resultado_ia,
        resultado_validado=v.resultado_validado,
        observacoes=v.observacoes,
        validado_em=v.validado_em.isoformat() if v.validado_em else None,
    )


async def _get_parecer(parecer_id: uuid.UUID, db: AsyncSession) -> Parecer:
    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")
    return parecer


async def _bifurcacao_dispensa_llm(parecer_id: uuid.UUID, db: AsyncSession) -> bool:
    """
    Bloco 29: a verificação LLM é dispensada quando a última rodada (não final)
    foi do Tipo 1 — a proposta revisada acabou de ser analisada — ou quando não
    houve nenhuma rodada (caso 100% aprovado na análise inicial).
    """
    ultima_tipo = await db.scalar(
        select(RodadaFornecedor.tipo)
        .where(
            RodadaFornecedor.parecer_id == parecer_id,
            RodadaFornecedor.proposta_final.is_(False),
        )
        .order_by(RodadaFornecedor.numero.desc())
        .limit(1)
    )
    return ultima_tipo is None or ultima_tipo == TIPO_PROPOSTA_REVISADA


@router.get("/{parecer_id}/verificacao-final", response_model=VerificacaoFinalResponse)
async def obter_verificacao_final(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """
    Estado da verificação final. Na primeira consulta com o caso na fase
    VERIFICACAO_FINAL, cria o registro aplicando a bifurcação do bloco 29.
    """
    parecer = await _get_parecer(parecer_id, db)

    result = await db.execute(
        select(VerificacaoFinal).where(VerificacaoFinal.parecer_id == parecer_id)
    )
    verificacao = result.scalar_one_or_none()

    if not verificacao:
        if parecer.fase_caso not in (VERIFICACAO_FINAL, FECHADO):
            raise HTTPException(
                status_code=404,
                detail=f"Verificacao final indisponivel na fase {parecer.fase_caso}.",
            )
        dispensada = await _bifurcacao_dispensa_llm(parecer_id, db)
        verificacao = VerificacaoFinal(
            parecer_id=parecer_id,
            ia_dispensada=dispensada,
            status="DISPENSADA" if dispensada else "AGUARDANDO_PROPOSTA_FINAL",
        )
        db.add(verificacao)
        await db.commit()
        await db.refresh(verificacao)

    return _to_response(verificacao)


class ExecutarVerificacaoRequest(BaseModel):
    rodada_fornecedor_id: str


class ExecutarVerificacaoResponse(BaseModel):
    verificacao_id: str
    task_id: str
    mensagem: str


@router.post(
    "/{parecer_id}/verificacao-final/executar",
    response_model=ExecutarVerificacaoResponse,
    status_code=202,
)
async def executar_verificacao(
    parecer_id: uuid.UUID,
    payload: ExecutarVerificacaoRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin", "analista")),
):
    """
    Blocos 31-32 (R3): com a proposta final carregada (rodada com
    proposta_final=true), dispara a verificação LLM contra os acordos do BD.
    """
    parecer = await _get_parecer(parecer_id, db)
    if parecer.fase_caso != VERIFICACAO_FINAL:
        raise HTTPException(
            status_code=400,
            detail=f"Verificacao so pode rodar na fase VERIFICACAO_FINAL (atual: {parecer.fase_caso}).",
        )

    result = await db.execute(
        select(VerificacaoFinal).where(VerificacaoFinal.parecer_id == parecer_id)
    )
    verificacao = result.scalar_one_or_none()
    if not verificacao:
        raise HTTPException(
            status_code=400,
            detail="Consulte GET /verificacao-final antes de executar.",
        )
    if verificacao.ia_dispensada:
        raise HTTPException(
            status_code=400,
            detail="Verificacao LLM dispensada (resposta veio do Tipo 1). Valide e feche o caso.",
        )
    if verificacao.status == "EM_VERIFICACAO":
        raise HTTPException(status_code=400, detail="Verificacao ja esta em andamento.")

    rodada = await db.scalar(
        select(RodadaFornecedor).where(
            RodadaFornecedor.id == uuid.UUID(payload.rodada_fornecedor_id),
            RodadaFornecedor.parecer_id == parecer_id,
            RodadaFornecedor.proposta_final.is_(True),
        )
    )
    if not rodada:
        raise HTTPException(
            status_code=404,
            detail="Rodada da proposta final nao encontrada. Carregue a proposta com proposta_final=true.",
        )

    verificacao.rodada_fornecedor_id = rodada.id
    verificacao.status = "EM_VERIFICACAO"
    await db.commit()

    from app.services.verificador_final import start_verificacao_in_background

    task_id = start_verificacao_in_background(str(verificacao.id))

    await registrar_auditoria(
        db, current_user, "executar_verificacao_final", "parecer",
        recurso_id=str(parecer_id),
        detalhes=f"rodada={rodada.id}, task={task_id}",
        request=request,
    )
    await db.commit()

    return ExecutarVerificacaoResponse(
        verificacao_id=str(verificacao.id),
        task_id=task_id,
        mensagem="Verificacao final em andamento. Valide o resultado quando concluir (W5).",
    )


@router.get("/{parecer_id}/verificacao-final/progresso")
async def progresso_verificacao(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(VerificacaoFinal).where(VerificacaoFinal.parecer_id == parecer_id)
    )
    verificacao = result.scalar_one_or_none()
    if not verificacao:
        raise HTTPException(status_code=404, detail="Verificacao nao encontrada.")
    progress = get_progress(f"verificacao:{parecer_id}") or {}
    return {
        "status": verificacao.status,
        "percent": progress.get("percent"),
        "message": progress.get("message"),
        "stage": progress.get("stage"),
    }


class ValidarVerificacaoRequest(BaseModel):
    resultado_validado: str  # CONFORME | CONFORME_COM_PENDENCIA | NAO_CONFORME
    observacoes: str | None = None


@router.post("/{parecer_id}/verificacao-final/validar", response_model=VerificacaoFinalResponse)
async def validar_verificacao(
    parecer_id: uuid.UUID,
    payload: ValidarVerificacaoRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin", "analista")),
):
    """
    Operação W5 (bloco 33): o engenheiro valida o resultado da verificação.
    O BD registra a decisão humana — se a LLM disse "conforme" mas o engenheiro
    discordou, vale a decisão do engenheiro.
    """
    if payload.resultado_validado not in _RESULTADOS_VALIDADOS:
        raise HTTPException(
            status_code=400,
            detail=f"resultado_validado deve ser um de: {', '.join(sorted(_RESULTADOS_VALIDADOS))}.",
        )

    parecer = await _get_parecer(parecer_id, db)
    if parecer.fase_caso != VERIFICACAO_FINAL:
        raise HTTPException(
            status_code=400,
            detail=f"Validacao so na fase VERIFICACAO_FINAL (atual: {parecer.fase_caso}).",
        )

    result = await db.execute(
        select(VerificacaoFinal).where(VerificacaoFinal.parecer_id == parecer_id)
    )
    verificacao = result.scalar_one_or_none()
    if not verificacao:
        raise HTTPException(status_code=404, detail="Verificacao nao encontrada.")
    if not verificacao.ia_dispensada and not verificacao.resultado_ia:
        raise HTTPException(
            status_code=400,
            detail="Execute a verificacao LLM antes de validar (ou aguarde a conclusao).",
        )

    verificacao.resultado_validado = payload.resultado_validado
    verificacao.observacoes = payload.observacoes
    verificacao.validado_por = getattr(current_user, "id", None)
    verificacao.validado_em = datetime.utcnow()
    verificacao.status = "VALIDADA"

    await registrar_auditoria(
        db, current_user, "w5_validar_verificacao", "parecer",
        recurso_id=str(parecer_id),
        detalhes=f"resultado_validado={payload.resultado_validado}",
        request=request,
    )
    await db.commit()
    await db.refresh(verificacao)

    return _to_response(verificacao)


class FecharCasoRequest(BaseModel):
    desfecho: str  # APROVADO | COM_PENDENCIA | REPROVADO
    observacoes: str | None = None


class FecharCasoResponse(BaseModel):
    fase_caso: str
    desfecho: str
    fechado_em: str
    mensagem: str


@router.post("/{parecer_id}/fechar", response_model=FecharCasoResponse)
async def fechar_caso(
    parecer_id: uuid.UUID,
    payload: FecharCasoRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin", "analista")),
):
    """
    Operação W6: fecha o caso com um dos três desfechos terminais.

    Na fase VERIFICACAO_FINAL com verificação LLM executada, exige a validação
    humana prévia (W5). Também permitido na CICLO_FORNECEDOR — para encerrar
    com pendências um caso em que o fornecedor não responde (substitui o
    antigo escalonamento gerencial).
    """
    if payload.desfecho not in DESFECHOS:
        raise HTTPException(
            status_code=400,
            detail=f"desfecho deve ser um de: {', '.join(sorted(DESFECHOS))}.",
        )

    parecer = await _get_parecer(parecer_id, db)

    if parecer.fase_caso not in (VERIFICACAO_FINAL, CICLO_FORNECEDOR):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Caso nao pode ser fechado na fase {parecer.fase_caso}. "
                "Fechamento e permitido nas fases VERIFICACAO_FINAL e CICLO_FORNECEDOR."
            ),
        )

    # W6 depende de W5 quando a verificação LLM foi executada
    if parecer.fase_caso == VERIFICACAO_FINAL:
        result = await db.execute(
            select(VerificacaoFinal).where(VerificacaoFinal.parecer_id == parecer_id)
        )
        verificacao = result.scalar_one_or_none()
        if (
            verificacao
            and not verificacao.ia_dispensada
            and verificacao.resultado_ia
            and not verificacao.resultado_validado
        ):
            raise HTTPException(
                status_code=400,
                detail="Valide o resultado da verificacao final (W5) antes de fechar o caso.",
            )

    agora = datetime.utcnow()
    parecer.fase_caso = FECHADO
    parecer.desfecho = payload.desfecho
    parecer.fechado_em = agora
    parecer.fechado_por = getattr(current_user, "id", None)
    parecer.motivo_fechamento = payload.observacoes

    await registrar_auditoria(
        db, current_user, "w6_fechar_caso", "parecer",
        recurso_id=str(parecer_id),
        detalhes=f"desfecho={payload.desfecho}",
        request=request,
    )
    await db.commit()

    return FecharCasoResponse(
        fase_caso=parecer.fase_caso,
        desfecho=parecer.desfecho,
        fechado_em=agora.isoformat(),
        mensagem=f"Caso fechado com desfecho {payload.desfecho}.",
    )
