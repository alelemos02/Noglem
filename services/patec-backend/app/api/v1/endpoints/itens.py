import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.usuario import Usuario
from app.models.parecer import Parecer
from app.models.item_parecer import ItemParecer
from app.models.recomendacao import Recomendacao
from app.schemas.item_parecer import ItemParecerResponse, ItemParecerUpdate, RecomendacaoResponse

router = APIRouter(prefix="/pareceres/{parecer_id}", tags=["itens"])

VALID_STATUSES = {"A", "B", "C", "D", "E"}
VALID_PRIORITIES = {"ALTA", "MEDIA", "BAIXA"}


def _item_to_response(item: ItemParecer) -> ItemParecerResponse:
    return ItemParecerResponse(
        id=str(item.id),
        parecer_id=str(item.parecer_id),
        numero=item.numero,
        categoria=item.categoria,
        descricao_requisito=item.descricao_requisito,
        referencia_engenharia=item.referencia_engenharia,
        referencia_fornecedor=item.referencia_fornecedor,
        valor_requerido=item.valor_requerido,
        valor_fornecedor=item.valor_fornecedor,
        status=item.status,
        justificativa_tecnica=item.justificativa_tecnica,
        acao_requerida=item.acao_requerida,
        prioridade=item.prioridade,
        norma_referencia=item.norma_referencia,
        editado_manualmente=item.editado_manualmente,
        criado_em=item.criado_em,
        atualizado_em=item.atualizado_em,
    )


@router.get("/itens", response_model=list[ItemParecerResponse])
async def listar_itens(
    parecer_id: uuid.UUID,
    status_filter: str | None = Query(None, alias="status"),
    categoria: str | None = None,
    prioridade: str | None = None,
    busca: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Lista os itens de um parecer com filtros opcionais."""
    query = select(ItemParecer).where(ItemParecer.parecer_id == parecer_id)

    if status_filter:
        query = query.where(ItemParecer.status == status_filter)
    if categoria:
        query = query.where(ItemParecer.categoria == categoria)
    if prioridade:
        query = query.where(ItemParecer.prioridade == prioridade)
    if busca:
        search = f"%{busca}%"
        query = query.where(
            ItemParecer.descricao_requisito.ilike(search)
            | ItemParecer.justificativa_tecnica.ilike(search)
            | ItemParecer.acao_requerida.ilike(search)
        )

    query = query.order_by(ItemParecer.numero)
    result = await db.execute(query)
    items = result.scalars().all()

    return [_item_to_response(item) for item in items]


@router.put("/itens/{item_id}", response_model=ItemParecerResponse)
async def atualizar_item(
    parecer_id: uuid.UUID,
    item_id: uuid.UUID,
    data: ItemParecerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "analista")),
):
    """Atualiza um item individual do parecer."""
    result = await db.execute(
        select(ItemParecer).where(
            ItemParecer.id == item_id,
            ItemParecer.parecer_id == parecer_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item nao encontrado")

    update_data = data.model_dump(exclude_unset=True)

    if "status" in update_data and update_data["status"] not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status invalido. Validos: {VALID_STATUSES}")
    if "prioridade" in update_data and update_data["prioridade"] not in VALID_PRIORITIES:
        raise HTTPException(
            status_code=400, detail=f"Prioridade invalida. Validas: {VALID_PRIORITIES}"
        )

    for field, value in update_data.items():
        setattr(item, field, value)

    item.editado_manualmente = True
    await db.commit()
    await db.refresh(item)

    # Recalculate parecer summary
    await _recalculate_parecer_summary(parecer_id, db)

    return _item_to_response(item)


@router.get("/recomendacoes", response_model=list[RecomendacaoResponse])
async def listar_recomendacoes(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Lista as recomendacoes de um parecer."""
    result = await db.execute(
        select(Recomendacao)
        .where(Recomendacao.parecer_id == parecer_id)
        .order_by(Recomendacao.ordem)
    )
    recs = result.scalars().all()
    return [
        RecomendacaoResponse(
            id=str(r.id),
            parecer_id=str(r.parecer_id),
            texto=r.texto,
            ordem=r.ordem,
        )
        for r in recs
    ]


async def _recalculate_parecer_summary(parecer_id: uuid.UUID, db: AsyncSession):
    """Recalculate parecer summary counts after item changes."""
    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if not parecer:
        return

    # Count by status
    for status_code, field in [
        ("A", "total_aprovados"),
        ("B", "total_aprovados_comentarios"),
        ("C", "total_rejeitados"),
        ("D", "total_info_ausente"),
        ("E", "total_itens_adicionais"),
    ]:
        count_result = await db.execute(
            select(func.count()).where(
                ItemParecer.parecer_id == parecer_id,
                ItemParecer.status == status_code,
            )
        )
        setattr(parecer, field, count_result.scalar())

    # Total
    total_result = await db.execute(
        select(func.count()).where(ItemParecer.parecer_id == parecer_id)
    )
    parecer.total_itens = total_result.scalar()

    # Recalculate parecer_geral
    if parecer.total_rejeitados > 0:
        parecer.parecer_geral = "REJEITADO"
    elif parecer.total_aprovados_comentarios > 0 or parecer.total_info_ausente > 0:
        parecer.parecer_geral = "APROVADO COM COMENTARIOS"
    else:
        parecer.parecer_geral = "APROVADO"

    await db.commit()
