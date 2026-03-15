import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.documento import Documento
from app.models.parecer import Parecer
from app.models.usuario import Usuario

router = APIRouter(prefix="/pareceres/{parecer_id}", tags=["estimativa"])

# Approximation: 1 token ~ 4 chars for Portuguese text
CHARS_PER_TOKEN = 4

# Gemini Flash pricing approximation (per million tokens)
PRICE_INPUT_PER_M = 0.35   # USD
PRICE_OUTPUT_PER_M = 1.05  # USD

# Approximate output tokens per analysis call
ESTIMATED_OUTPUT_TOKENS = 4000

# System prompt overhead (chars)
SYSTEM_PROMPT_CHARS = 5000


class EstimativaCustoResponse(BaseModel):
    total_caracteres: int
    tokens_estimados_entrada: int
    tokens_estimados_saida: int
    num_chamadas_api: int
    custo_estimado_usd: float
    custo_estimado_brl: float
    modelo: str
    aviso: str | None = None


@router.get("/estimativa-custo", response_model=EstimativaCustoResponse)
async def estimar_custo(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_user),
):
    """Estimate the cost of running LLM analysis on this parecer's documents."""
    # Check parecer exists
    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")

    # Load documents
    docs_result = await db.execute(
        select(Documento).where(Documento.parecer_id == parecer_id)
    )
    docs = docs_result.scalars().all()

    if not docs:
        raise HTTPException(
            status_code=400,
            detail="Nenhum documento encontrado. Faca upload antes de estimar.",
        )

    # Calculate total chars
    total_chars = sum(len(d.texto_extraido or "") for d in docs)
    total_chars += SYSTEM_PROMPT_CHARS  # system prompt overhead

    # Estimate tokens
    tokens_entrada = total_chars // CHARS_PER_TOKEN

    # Estimate number of API calls (chunking)
    max_input_chars = 150_000
    num_chamadas = max(1, (total_chars + max_input_chars - 1) // max_input_chars)
    if num_chamadas > 1:
        num_chamadas += 1  # extra call for reduce step

    tokens_saida = ESTIMATED_OUTPUT_TOKENS * num_chamadas

    # Calculate cost
    custo_entrada = (tokens_entrada / 1_000_000) * PRICE_INPUT_PER_M
    custo_saida = (tokens_saida / 1_000_000) * PRICE_OUTPUT_PER_M
    custo_total_usd = custo_entrada + custo_saida

    # BRL conversion (approximate)
    taxa_cambio = 5.50
    custo_total_brl = custo_total_usd * taxa_cambio

    aviso = None
    if num_chamadas > 1:
        aviso = (
            f"Documentos grandes: serao necessarias {num_chamadas} chamadas a API "
            f"(incluindo consolidacao). O custo pode variar."
        )

    return EstimativaCustoResponse(
        total_caracteres=total_chars,
        tokens_estimados_entrada=tokens_entrada,
        tokens_estimados_saida=tokens_saida,
        num_chamadas_api=num_chamadas,
        custo_estimado_usd=round(custo_total_usd, 4),
        custo_estimado_brl=round(custo_total_brl, 2),
        modelo=settings.GEMINI_MODEL,
        aviso=aviso,
    )
