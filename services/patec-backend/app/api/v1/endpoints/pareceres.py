import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.usuario import Usuario
from app.models.parecer import Parecer
from app.schemas.parecer import (
    ParecerCreate,
    ParecerUpdate,
    ParecerResponse,
    ParecerListResponse,
)
from app.services.audit import registrar_auditoria

router = APIRouter(prefix="/pareceres", tags=["pareceres"])


def _to_response(p: Parecer) -> ParecerResponse:
    return ParecerResponse(
        id=str(p.id),
        numero_parecer=p.numero_parecer,
        projeto=p.projeto,
        fornecedor=p.fornecedor,
        revisao=p.revisao,
        status_processamento=p.status_processamento,
        parecer_geral=p.parecer_geral,
        comentario_geral=p.comentario_geral,
        conclusao=p.conclusao,
        total_itens=p.total_itens,
        total_aprovados=p.total_aprovados,
        total_aprovados_comentarios=p.total_aprovados_comentarios,
        total_rejeitados=p.total_rejeitados,
        total_info_ausente=p.total_info_ausente,
        total_itens_adicionais=p.total_itens_adicionais,
        criado_em=p.criado_em,
        atualizado_em=p.atualizado_em,
    )


@router.post("", response_model=ParecerResponse, status_code=status.HTTP_201_CREATED)
async def criar_parecer(
    data: ParecerCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "analista")),
):
    result = await db.execute(
        select(Parecer).where(Parecer.numero_parecer == data.numero_parecer)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Numero de parecer ja existe",
        )

    parecer = Parecer(
        numero_parecer=data.numero_parecer,
        projeto=data.projeto,
        fornecedor=data.fornecedor,
        revisao=data.revisao,
        comentario_geral=data.comentario_geral,
        criado_por=current_user.id,
    )
    db.add(parecer)
    await db.flush()

    await registrar_auditoria(
        db, current_user, "criar", "parecer",
        recurso_id=str(parecer.id),
        detalhes=f"Parecer {data.numero_parecer} criado",
        request=request,
    )

    await db.commit()
    await db.refresh(parecer)
    return _to_response(parecer)


@router.get("", response_model=ParecerListResponse)
async def listar_pareceres(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    projeto: str | None = None,
    fornecedor: str | None = None,
    status_processamento: str | None = None,
    parecer_geral: str | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_user),
):
    query = select(Parecer)
    count_query = select(func.count(Parecer.id))

    if projeto:
        query = query.where(Parecer.projeto.ilike(f"%{projeto}%"))
        count_query = count_query.where(Parecer.projeto.ilike(f"%{projeto}%"))
    if fornecedor:
        query = query.where(Parecer.fornecedor.ilike(f"%{fornecedor}%"))
        count_query = count_query.where(Parecer.fornecedor.ilike(f"%{fornecedor}%"))
    if status_processamento:
        query = query.where(Parecer.status_processamento == status_processamento)
        count_query = count_query.where(Parecer.status_processamento == status_processamento)
    if parecer_geral:
        query = query.where(Parecer.parecer_geral == parecer_geral)
        count_query = count_query.where(Parecer.parecer_geral == parecer_geral)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(Parecer.criado_em.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    pareceres = result.scalars().all()

    return ParecerListResponse(
        items=[_to_response(p) for p in pareceres],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{parecer_id}", response_model=ParecerResponse)
async def obter_parecer(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_user),
):
    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")
    return _to_response(parecer)


@router.put("/{parecer_id}", response_model=ParecerResponse)
async def atualizar_parecer(
    parecer_id: uuid.UUID,
    data: ParecerUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "analista")),
):
    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(parecer, field, value)

    await registrar_auditoria(
        db, current_user, "atualizar", "parecer",
        recurso_id=str(parecer_id),
        detalhes=f"Campos atualizados: {', '.join(update_data.keys())}",
        request=request,
    )

    await db.commit()
    await db.refresh(parecer)
    return _to_response(parecer)


@router.delete("/{parecer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_parecer(
    parecer_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "analista")),
):
    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")

    await registrar_auditoria(
        db, current_user, "excluir", "parecer",
        recurso_id=str(parecer_id),
        detalhes=f"Parecer {parecer.numero_parecer} excluido",
        request=request,
    )

    await db.delete(parecer)
    await db.commit()
