import re
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.progress import get_progress, set_progress
from app.models.documento import Documento
from app.models.parecer import Parecer
from app.models.usuario import Usuario
from app.schemas.requisito import (
    AprovarRequisitosRequest,
    ExtracaoAsyncResponse,
    ExtracaoProgressoResponse,
    ExtracaoRequest,
    RequisitoResponse,
    RequisitosAprovadosResponse,
    RequisitoUpdate,
)
from app.services import requisitos as requisitos_service
from app.services.audit import registrar_auditoria

router = APIRouter(prefix="/pareceres/{parecer_id}/requisitos", tags=["requisitos"])

_VALID_PROFILE_RE = re.compile(
    r"^(simples|padrao|completa|integral|triagem_tecnica|conformidade_tecnica|"
    r"auditoria_tecnica_completa|custom_\d+)$"
)

# Progresso sem stage terminal e mais novo que isso bloqueia um novo disparo
# (409). Mais velho = task morta (worker caiu sem gravar stage error) — libera.
_EXTRACAO_STALE_SECONDS = 15 * 60
_STAGES_TERMINAIS = {"completed", "error"}


@router.post(
    "/extrair",
    response_model=ExtracaoAsyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def extrair(
    parecer_id: uuid.UUID,
    request: Request,
    payload: ExtracaoRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "analista")),
):
    """
    Inicia a extracao assincrona da lista candidata de requisitos (blocos 8-9)
    via worker Celery. A lista e persistida como RASCUNHO ao final; acompanhe
    pelo GET /extracao/progresso (stage completed/error encerra).
    """
    perfil = payload.perfil_analise if payload else "padrao"
    if not _VALID_PROFILE_RE.match(perfil):
        raise HTTPException(status_code=422, detail="perfil_analise invalido.")
    escopo = payload.escopo if payload else None
    feedback = payload.feedback if payload else None

    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")

    if parecer.fase_caso not in requisitos_service._FASES_APROVACAO:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Extracao de requisitos indisponivel na fase {parecer.fase_caso}. "
                "Apos a analise, use a revisao de especificacao."
            ),
        )

    docs_result = await db.execute(
        select(Documento).where(
            Documento.parecer_id == parecer_id, Documento.tipo == "engenharia"
        )
    )
    if not docs_result.scalars().first():
        raise HTTPException(
            status_code=400,
            detail=(
                "Faca upload de pelo menos um documento de engenharia antes de "
                "extrair requisitos."
            ),
        )

    key = requisitos_service.progress_key_extracao(parecer_id)
    progresso = get_progress(key)
    if progresso and progresso.get("stage") not in _STAGES_TERMINAIS:
        updated_at = progresso.get("updated_at")
        if updated_at and (time.time() - float(updated_at)) < _EXTRACAO_STALE_SECONDS:
            raise HTTPException(
                status_code=409,
                detail="Ja existe uma extracao de requisitos em andamento para este caso.",
            )

    set_progress(key, 2, "Extração enfileirada para processamento...", "queued")
    task_id = requisitos_service.start_extracao_in_background(
        str(parecer_id), perfil, escopo, feedback
    )

    await registrar_auditoria(
        db, current_user, "extrair_requisitos", "parecer",
        recurso_id=str(parecer_id),
        detalhes=(
            f"Extracao enfileirada no worker, perfil={perfil}, "
            f"escopo={'sim' if escopo else 'nao'}, task_id={task_id}"
        ),
        request=request,
    )
    await db.commit()

    return ExtracaoAsyncResponse(
        task_id=task_id,
        message="Extração iniciada. Use o endpoint de progresso para acompanhar.",
    )


@router.get("/extracao/progresso", response_model=ExtracaoProgressoResponse)
async def progresso_extracao(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_user),
):
    """Progresso da extracao em background (stage completed/error = terminou;
    a mensagem do stage completed carrega o resumo da extracao)."""
    result = await db.execute(select(Parecer.id).where(Parecer.id == parecer_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")

    progresso = get_progress(requisitos_service.progress_key_extracao(parecer_id)) or {}
    return ExtracaoProgressoResponse(
        percent=progresso.get("percent"),
        message=progresso.get("message"),
        stage=progresso.get("stage"),
    )


@router.get("", response_model=list[RequisitoResponse])
async def listar(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_user),
):
    """Lista os requisitos aprovados (W1) do parecer, incluindo desativados."""
    try:
        requisitos = await requisitos_service.listar_requisitos(parecer_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return requisitos


@router.get("/draft", response_model=list[RequisitoResponse])
async def listar_draft(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_user),
):
    """Lista o rascunho de requisitos em revisao (W1 ainda pendente)."""
    try:
        requisitos = await requisitos_service.listar_draft(parecer_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return requisitos


@router.put("/draft", response_model=list[RequisitoResponse])
async def salvar_draft(
    parecer_id: uuid.UUID,
    payload: AprovarRequisitosRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(require_role("admin", "analista")),
):
    """Substitui o rascunho de requisitos no BD (edicao manual ou via JULIA)."""
    itens = [r.model_dump() for r in payload.requisitos]
    try:
        requisitos = await requisitos_service.salvar_draft(parecer_id, db, itens)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return requisitos


@router.post("/reabrir", response_model=list[RequisitoResponse])
async def reabrir(
    parecer_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "analista")),
):
    """Reabre os requisitos aprovados para edicao (rascunho) na fase ANALISE.

    Copia a lista aprovada de volta para um rascunho editavel; ao reaprovar, a
    analise e refeita. Indisponivel a partir do ciclo (use a revisao de spec).
    """
    try:
        requisitos = await requisitos_service.reabrir_requisitos(parecer_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await registrar_auditoria(
        db, current_user, "reabrir_requisitos", "parecer",
        recurso_id=str(parecer_id),
        detalhes=f"{len(requisitos)} requisitos reabertos para edicao",
        request=request,
    )
    await db.commit()

    return requisitos


@router.post("/aprovar", response_model=RequisitosAprovadosResponse)
async def aprovar(
    parecer_id: uuid.UUID,
    payload: AprovarRequisitosRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "analista")),
):
    """
    Operacao W1: grava a lista de requisitos validada pelo engenheiro no BD
    central e avanca o caso para a fase ANALISE.
    """
    itens = [r.model_dump() for r in payload.requisitos]

    try:
        parecer, requisitos = await requisitos_service.aprovar_requisitos(
            parecer_id, db, itens, current_user
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await registrar_auditoria(
        db, current_user, "w1_aprovar_requisitos", "parecer",
        recurso_id=str(parecer_id),
        detalhes=f"{len(requisitos)} requisitos aprovados; fase_caso=ANALISE",
        request=request,
    )
    await db.commit()

    return RequisitosAprovadosResponse(
        requisitos=[RequisitoResponse.model_validate(r) for r in requisitos],
        total_itens=len(requisitos),
        fase_caso=parecer.fase_caso,
    )


@router.patch("/{requisito_id}", response_model=RequisitoResponse)
async def atualizar(
    parecer_id: uuid.UUID,
    requisito_id: uuid.UUID,
    payload: RequisitoUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "analista")),
):
    """Edita um requisito aprovado — permitido apenas antes da analise inicial."""
    campos = payload.model_dump(exclude_unset=True)
    if not campos:
        raise HTTPException(status_code=422, detail="Nenhum campo para atualizar.")

    try:
        requisito = await requisitos_service.atualizar_requisito(
            parecer_id, requisito_id, db, campos
        )
    except ValueError as e:
        detail = str(e)
        status_code = 404 if "nao encontrado" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail)

    await registrar_auditoria(
        db, current_user, "atualizar_requisito", "requisito",
        recurso_id=str(requisito_id),
        detalhes=f"Campos: {', '.join(campos.keys())}",
        request=request,
    )
    await db.commit()

    return requisito
