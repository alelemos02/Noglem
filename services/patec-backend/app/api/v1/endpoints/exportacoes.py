import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.item_parecer import ItemParecer
from app.models.parecer import Parecer
from app.models.recomendacao import Recomendacao
from app.models.usuario import Usuario
from app.services.exporter import export_docx, export_pdf, export_xlsx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pareceres", tags=["exportacoes"])


async def _load_export_data(parecer_id: uuid.UUID, db: AsyncSession):
    parecer_result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = parecer_result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")

    itens_result = await db.execute(
        select(ItemParecer)
        .where(ItemParecer.parecer_id == parecer_id)
        .order_by(ItemParecer.numero)
    )
    itens = itens_result.scalars().all()

    recomendacoes_result = await db.execute(
        select(Recomendacao)
        .where(Recomendacao.parecer_id == parecer_id)
        .order_by(Recomendacao.ordem)
    )
    recomendacoes = recomendacoes_result.scalars().all()

    return parecer, itens, recomendacoes


@router.get("/{parecer_id}/exportar/pdf")
async def exportar_pdf(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_user),
):
    parecer, itens, recomendacoes = await _load_export_data(parecer_id, db)
    try:
        content = export_pdf(parecer, itens, recomendacoes)
    except Exception:
        logger.exception("Falha ao exportar PDF para parecer %s", parecer_id)
        raise HTTPException(status_code=500, detail="Erro ao gerar relatorio PDF")
    filename = f"parecer_{parecer.numero_parecer}.pdf"

    return StreamingResponse(
        iter([content]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{parecer_id}/exportar/xlsx")
async def exportar_xlsx_endpoint(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_user),
):
    parecer, itens, recomendacoes = await _load_export_data(parecer_id, db)
    try:
        content = export_xlsx(parecer, itens, recomendacoes)
    except Exception:
        logger.exception("Falha ao exportar XLSX para parecer %s", parecer_id)
        raise HTTPException(status_code=500, detail="Erro ao gerar relatorio XLSX")
    filename = f"parecer_{parecer.numero_parecer}.xlsx"

    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{parecer_id}/exportar/docx")
async def exportar_docx_endpoint(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_user),
):
    parecer, itens, recomendacoes = await _load_export_data(parecer_id, db)
    try:
        content = export_docx(parecer, itens, recomendacoes)
    except Exception:
        logger.exception("Falha ao exportar DOCX para parecer %s", parecer_id)
        raise HTTPException(status_code=500, detail="Erro ao gerar relatorio DOCX")
    filename = f"parecer_{parecer.numero_parecer}.docx"

    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
