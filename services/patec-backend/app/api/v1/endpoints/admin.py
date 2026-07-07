"""
Endpoints do DONO da ferramenta (nao expostos ao usuario final).

Dashboard de qualidade: metricas agregadas sobre o desempenho da IA ao longo de
todos os pareceres — instrumento de controle de qualidade do produto. Protegido
por require_owner (por e-mail; ver core/deps.py).
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_owner
from app.models.item_parecer import ItemParecer
from app.models.parecer import Parecer
from app.models.usuario import Usuario

router = APIRouter(prefix="/admin", tags=["admin"])

# Marca do placeholder injetado pela reconciliacao de escopo (T2/B2): mede quantas
# vezes a IA deixou um requisito aprovado sem cobrir.
_MARCA_PLACEHOLDER = "nao coberto pela analise automatica"


async def _scalar(db: AsyncSession, stmt) -> int:
    return int((await db.execute(stmt)).scalar() or 0)


def _taxa(parte: int, total: int) -> float:
    return round(parte / total, 4) if total else 0.0


@router.get("/qualidade")
async def qualidade(
    db: AsyncSession = Depends(get_db),
    _owner: Usuario = Depends(require_owner),
):
    """Métricas de qualidade da IA, agregadas sobre todos os pareceres."""
    # ── Pareceres ──────────────────────────────────────────────────────────
    total_pareceres = await _scalar(db, select(func.count(Parecer.id)))
    analisados = await _scalar(
        db,
        select(func.count(Parecer.id)).where(
            Parecer.status_processamento == "concluido"
        ),
    )
    por_disciplina = {
        (d or "?"): n
        for d, n in (
            await db.execute(
                select(Parecer.disciplina, func.count(Parecer.id)).group_by(
                    Parecer.disciplina
                )
            )
        ).all()
    }
    por_desfecho = {
        (g or "EM_ABERTO"): n
        for g, n in (
            await db.execute(
                select(Parecer.parecer_geral, func.count(Parecer.id)).group_by(
                    Parecer.parecer_geral
                )
            )
        ).all()
    }

    # ── Itens ──────────────────────────────────────────────────────────────
    total_itens = await _scalar(db, select(func.count(ItemParecer.id)))
    por_status = {
        s: n
        for s, n in (
            await db.execute(
                select(ItemParecer.status, func.count(ItemParecer.id)).group_by(
                    ItemParecer.status
                )
            )
        ).all()
    }
    editados = await _scalar(
        db,
        select(func.count(ItemParecer.id)).where(
            ItemParecer.editado_manualmente.is_(True)
        ),
    )
    placeholders = await _scalar(
        db,
        select(func.count(ItemParecer.id)).where(
            ItemParecer.justificativa_tecnica.ilike(f"%{_MARCA_PLACEHOLDER}%")
        ),
    )
    verif_correcoes = await _scalar(
        db,
        select(func.count(ItemParecer.id)).where(
            ItemParecer.verificacao_nota.ilike("Corrigido%")
        ),
    )
    consistencia = await _scalar(
        db,
        select(func.count(ItemParecer.id)).where(
            ItemParecer.flag_consistencia.isnot(None)
        ),
    )

    return {
        "pareceres": {
            "total": total_pareceres,
            "analisados": analisados,
            "por_disciplina": por_disciplina,
            "por_desfecho": por_desfecho,
        },
        "itens": {
            "total": total_itens,
            "media_por_parecer": (
                round(total_itens / analisados, 1) if analisados else 0.0
            ),
            "por_status": por_status,
        },
        # Sinais de qualidade: quanto MAIOR, mais atencao merece.
        "qualidade": {
            # engenheiro sobrescreveu a IA (se alto, a IA erra muito)
            "correcao_manual": {"itens": editados, "taxa": _taxa(editados, total_itens)},
            # requisito aprovado que a IA nao cobriu (reconciliacao injetou D)
            "requisitos_nao_cobertos": {
                "itens": placeholders,
                "taxa": _taxa(placeholders, total_itens),
            },
            # itens corrigidos pelo verificador Pro
            "verificador_correcoes": verif_correcoes,
            # itens com alerta de consistencia (termo achado mas classificado como desvio)
            "consistencia_flags": consistencia,
        },
    }
