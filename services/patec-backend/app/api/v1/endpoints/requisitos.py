import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.usuario import Usuario
from app.schemas.requisito import (
    AprovarRequisitosRequest,
    ExtracaoRequest,
    ExtracaoResponse,
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


@router.post("/extrair", response_model=ExtracaoResponse)
async def extrair(
    parecer_id: uuid.UUID,
    payload: ExtracaoRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "analista")),
):
    """
    Extrai a lista candidata de requisitos dos documentos de engenharia via LLM
    (blocos 8-9 do fluxo). Sincrono; nada e persistido — a lista so entra no BD
    central na aprovacao (W1).
    """
    perfil = payload.perfil_analise if payload else "padrao"
    if not _VALID_PROFILE_RE.match(perfil):
        raise HTTPException(status_code=422, detail="perfil_analise invalido.")
    escopo = payload.escopo if payload else None
    feedback = payload.feedback if payload else None

    try:
        data = await requisitos_service.extrair_requisitos(
            parecer_id, db, perfil, escopo, feedback
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    return ExtracaoResponse(**data)


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
