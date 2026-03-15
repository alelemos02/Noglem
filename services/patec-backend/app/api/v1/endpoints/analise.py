import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.progress import get_progress, set_progress
from app.core.rate_limit import check_analysis_rate_limit
from app.models.usuario import Usuario
from app.models.parecer import Parecer
from app.models.documento import Documento
from app.services.audit import registrar_auditoria
from app.services.tasks import start_analysis_in_background

router = APIRouter(prefix="/pareceres/{parecer_id}", tags=["analise"])

ANALYSIS_PROFILE_LABELS = {
    "triagem_tecnica": "Triagem Tecnica",
    "conformidade_tecnica": "Conformidade Tecnica",
    "auditoria_tecnica_completa": "Auditoria Tecnica Completa",
}
DEFAULT_ANALYSIS_PROFILE = "conformidade_tecnica"


class AnaliseResponse(BaseModel):
    task_id: str
    message: str


class StatusResponse(BaseModel):
    status_processamento: str
    task_state: str | None = None
    message: str | None = None
    stage: str | None = None
    progress_percent: int | None = None
    parecer_geral: str | None = None
    total_itens: int = 0


class AnaliseRequest(BaseModel):
    perfil_analise: Literal[
        "triagem_tecnica",
        "conformidade_tecnica",
        "auditoria_tecnica_completa",
    ] = DEFAULT_ANALYSIS_PROFILE


@router.post("/analisar", response_model=AnaliseResponse, status_code=status.HTTP_202_ACCEPTED)
async def iniciar_analise(
    parecer_id: uuid.UUID,
    request: Request,
    payload: AnaliseRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "analista")),
):
    """Inicia a analise assincrona do parecer via LLM."""
    # Rate limit check
    await check_analysis_rate_limit(request, str(current_user.id))

    # Load parecer
    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")

    # Check if already processing
    if parecer.status_processamento == "processando":
        raise HTTPException(
            status_code=400,
            detail="Parecer ja esta sendo processado",
        )

    # Check if documents exist
    docs_result = await db.execute(
        select(Documento).where(Documento.parecer_id == parecer_id)
    )
    docs = docs_result.scalars().all()

    eng_docs = [d for d in docs if d.tipo == "engenharia"]
    forn_docs = [d for d in docs if d.tipo == "fornecedor"]

    if not eng_docs:
        raise HTTPException(
            status_code=400,
            detail="Faca upload de pelo menos um documento de engenharia antes de analisar",
        )
    if not forn_docs:
        raise HTTPException(
            status_code=400,
            detail="Faca upload de pelo menos um documento do fornecedor antes de analisar",
        )

    # Mark as processing and trigger in-process background thread
    parecer.status_processamento = "processando"
    parecer.comentario_geral = None
    await db.commit()

    perfil_analise = payload.perfil_analise if payload else DEFAULT_ANALYSIS_PROFILE
    perfil_label = ANALYSIS_PROFILE_LABELS.get(
        perfil_analise, ANALYSIS_PROFILE_LABELS[DEFAULT_ANALYSIS_PROFILE]
    )

    set_progress(
        str(parecer_id),
        2,
        f"Analise enfileirada ({perfil_label}) para processamento...",
        "queued",
    )
    task_id = start_analysis_in_background(str(parecer_id), perfil_analise)

    # Audit log
    await registrar_auditoria(
        db, current_user, "iniciar_analise", "parecer",
        recurso_id=str(parecer_id),
        detalhes=(
            f"Analise iniciada em background thread, "
            f"perfil={perfil_analise}, task_id={task_id}"
        ),
        request=request,
    )
    await db.commit()

    return AnaliseResponse(
        task_id=task_id,
        message=(
            f"Analise ({perfil_label}) iniciada com sucesso. "
            "Use o endpoint de status para acompanhar."
        ),
    )


@router.get("/status", response_model=StatusResponse)
async def status_analise(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_user),
):
    """Retorna o status atual do processamento do parecer."""
    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")

    response = StatusResponse(
        status_processamento=parecer.status_processamento,
        parecer_geral=parecer.parecer_geral,
        total_itens=parecer.total_itens,
    )

    # If processing, return Redis-backed progress
    if parecer.status_processamento == "processando":
        progress = get_progress(str(parecer_id))
        response.task_state = "PROGRESS"
        if progress:
            response.progress_percent = progress.get("percent")
            response.message = progress.get("message")
            response.stage = progress.get("stage")
        else:
            response.progress_percent = 5
            response.message = "Processando analise..."
            response.stage = "processing"

    elif parecer.status_processamento == "concluido":
        response.task_state = "SUCCESS"
        response.progress_percent = 100
        response.stage = "completed"
        response.message = "Analise concluida com sucesso."

    elif parecer.status_processamento == "erro":
        response.task_state = "FAILURE"
        response.progress_percent = 100
        response.stage = "error"
        response.message = parecer.comentario_geral

    return response
