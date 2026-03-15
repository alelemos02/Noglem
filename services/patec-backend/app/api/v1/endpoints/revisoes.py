import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.usuario import Usuario
from app.models.parecer import Parecer
from app.models.item_parecer import ItemParecer
from app.models.recomendacao import Recomendacao
from app.models.revisao import RevisaoParecer
from app.schemas.revisao import (
    RevisaoCreate,
    RevisaoResponse,
    RevisaoListResponse,
    RevisaoCompareResponse,
)
from app.services.audit import registrar_auditoria

router = APIRouter(prefix="/pareceres/{parecer_id}/revisoes", tags=["revisoes"])


def _revisao_to_response(r: RevisaoParecer) -> RevisaoResponse:
    return RevisaoResponse(
        id=str(r.id),
        parecer_id=str(r.parecer_id),
        numero_revisao=r.numero_revisao,
        motivo=r.motivo,
        criado_por=str(r.criado_por) if r.criado_por else None,
        parecer_geral=r.parecer_geral,
        comentario_geral=r.comentario_geral,
        conclusao=r.conclusao,
        total_itens=r.total_itens,
        total_aprovados=r.total_aprovados,
        total_aprovados_comentarios=r.total_aprovados_comentarios,
        total_rejeitados=r.total_rejeitados,
        total_info_ausente=r.total_info_ausente,
        total_itens_adicionais=r.total_itens_adicionais,
        criado_em=r.criado_em,
    )


async def _get_parecer(parecer_id: uuid.UUID, db: AsyncSession) -> Parecer:
    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")
    return parecer


@router.post("", response_model=RevisaoResponse, status_code=201)
async def criar_revisao(
    parecer_id: uuid.UUID,
    data: RevisaoCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "analista")),
):
    """Create a snapshot (revision) of the current parecer state."""
    parecer = await _get_parecer(parecer_id, db)

    # Determine next revision number
    max_rev_result = await db.execute(
        select(func.coalesce(func.max(RevisaoParecer.numero_revisao), 0))
        .where(RevisaoParecer.parecer_id == parecer_id)
    )
    next_rev = max_rev_result.scalar() + 1

    # Snapshot items
    itens_result = await db.execute(
        select(ItemParecer)
        .where(ItemParecer.parecer_id == parecer_id)
        .order_by(ItemParecer.numero)
    )
    itens = itens_result.scalars().all()
    itens_snapshot = [
        {
            "numero": item.numero,
            "categoria": item.categoria,
            "descricao_requisito": item.descricao_requisito,
            "referencia_engenharia": item.referencia_engenharia,
            "referencia_fornecedor": item.referencia_fornecedor,
            "valor_requerido": item.valor_requerido,
            "valor_fornecedor": item.valor_fornecedor,
            "status": item.status,
            "justificativa_tecnica": item.justificativa_tecnica,
            "acao_requerida": item.acao_requerida,
            "prioridade": item.prioridade,
            "norma_referencia": item.norma_referencia,
            "editado_manualmente": item.editado_manualmente,
        }
        for item in itens
    ]

    # Snapshot recommendations
    recs_result = await db.execute(
        select(Recomendacao)
        .where(Recomendacao.parecer_id == parecer_id)
        .order_by(Recomendacao.ordem)
    )
    recs = recs_result.scalars().all()
    recs_snapshot = [{"ordem": r.ordem, "texto": r.texto} for r in recs]

    revisao = RevisaoParecer(
        parecer_id=parecer_id,
        numero_revisao=next_rev,
        motivo=data.motivo,
        criado_por=current_user.id,
        parecer_geral=parecer.parecer_geral,
        comentario_geral=parecer.comentario_geral,
        conclusao=parecer.conclusao,
        total_itens=parecer.total_itens,
        total_aprovados=parecer.total_aprovados,
        total_aprovados_comentarios=parecer.total_aprovados_comentarios,
        total_rejeitados=parecer.total_rejeitados,
        total_info_ausente=parecer.total_info_ausente,
        total_itens_adicionais=parecer.total_itens_adicionais,
        itens_snapshot=itens_snapshot,
        recomendacoes_snapshot=recs_snapshot,
    )
    db.add(revisao)

    await registrar_auditoria(
        db, current_user, "criar", "revisao",
        recurso_id=str(parecer_id),
        detalhes=f"Revisao {next_rev} criada: {data.motivo or 'sem motivo'}",
        request=request,
    )

    await db.commit()
    await db.refresh(revisao)
    return _revisao_to_response(revisao)


@router.get("", response_model=RevisaoListResponse)
async def listar_revisoes(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_user),
):
    """List all revisions for a parecer."""
    await _get_parecer(parecer_id, db)

    count_result = await db.execute(
        select(func.count()).where(RevisaoParecer.parecer_id == parecer_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(RevisaoParecer)
        .where(RevisaoParecer.parecer_id == parecer_id)
        .order_by(RevisaoParecer.numero_revisao.desc())
    )
    revisoes = result.scalars().all()

    return RevisaoListResponse(
        items=[_revisao_to_response(r) for r in revisoes],
        total=total,
    )


@router.get("/{revisao_id}", response_model=RevisaoResponse)
async def obter_revisao(
    parecer_id: uuid.UUID,
    revisao_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_user),
):
    """Get a specific revision."""
    result = await db.execute(
        select(RevisaoParecer).where(
            RevisaoParecer.id == revisao_id,
            RevisaoParecer.parecer_id == parecer_id,
        )
    )
    revisao = result.scalar_one_or_none()
    if not revisao:
        raise HTTPException(status_code=404, detail="Revisao nao encontrada")
    return _revisao_to_response(revisao)


@router.get("/{revisao_id}/itens")
async def obter_itens_revisao(
    parecer_id: uuid.UUID,
    revisao_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_user),
):
    """Get the items snapshot from a specific revision."""
    result = await db.execute(
        select(RevisaoParecer).where(
            RevisaoParecer.id == revisao_id,
            RevisaoParecer.parecer_id == parecer_id,
        )
    )
    revisao = result.scalar_one_or_none()
    if not revisao:
        raise HTTPException(status_code=404, detail="Revisao nao encontrada")
    return {
        "itens": revisao.itens_snapshot or [],
        "recomendacoes": revisao.recomendacoes_snapshot or [],
    }


@router.get("/comparar/{rev_a}/{rev_b}", response_model=RevisaoCompareResponse)
async def comparar_revisoes(
    parecer_id: uuid.UUID,
    rev_a: int,
    rev_b: int,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_user),
):
    """Compare two revisions of a parecer (diff)."""
    result_a = await db.execute(
        select(RevisaoParecer).where(
            RevisaoParecer.parecer_id == parecer_id,
            RevisaoParecer.numero_revisao == rev_a,
        )
    )
    revisao_a = result_a.scalar_one_or_none()
    if not revisao_a:
        raise HTTPException(status_code=404, detail=f"Revisao {rev_a} nao encontrada")

    result_b = await db.execute(
        select(RevisaoParecer).where(
            RevisaoParecer.parecer_id == parecer_id,
            RevisaoParecer.numero_revisao == rev_b,
        )
    )
    revisao_b = result_b.scalar_one_or_none()
    if not revisao_b:
        raise HTTPException(status_code=404, detail=f"Revisao {rev_b} nao encontrada")

    diferencas = _calcular_diferencas(revisao_a, revisao_b)

    return RevisaoCompareResponse(
        revisao_a=_revisao_to_response(revisao_a),
        revisao_b=_revisao_to_response(revisao_b),
        diferencas=diferencas,
    )


def _calcular_diferencas(rev_a: RevisaoParecer, rev_b: RevisaoParecer) -> dict:
    """Calculate differences between two revisions."""
    # Summary diffs
    resumo_diff = {}
    for campo in [
        "parecer_geral", "total_itens", "total_aprovados",
        "total_aprovados_comentarios", "total_rejeitados",
        "total_info_ausente", "total_itens_adicionais",
    ]:
        val_a = getattr(rev_a, campo)
        val_b = getattr(rev_b, campo)
        if val_a != val_b:
            resumo_diff[campo] = {"de": val_a, "para": val_b}

    # Items diff
    itens_a = {item.get("numero"): item for item in (rev_a.itens_snapshot or [])}
    itens_b = {item.get("numero"): item for item in (rev_b.itens_snapshot or [])}

    all_nums = sorted(set(itens_a.keys()) | set(itens_b.keys()))

    itens_adicionados = []
    itens_removidos = []
    itens_alterados = []

    for num in all_nums:
        if num not in itens_a:
            itens_adicionados.append(itens_b[num])
        elif num not in itens_b:
            itens_removidos.append(itens_a[num])
        else:
            item_a = itens_a[num]
            item_b = itens_b[num]
            campos_alterados = {}
            for key in item_a:
                if item_a.get(key) != item_b.get(key):
                    campos_alterados[key] = {
                        "de": item_a.get(key),
                        "para": item_b.get(key),
                    }
            if campos_alterados:
                itens_alterados.append({
                    "numero": num,
                    "alteracoes": campos_alterados,
                })

    return {
        "resumo": resumo_diff,
        "itens_adicionados": len(itens_adicionados),
        "itens_removidos": len(itens_removidos),
        "itens_alterados": itens_alterados,
    }
