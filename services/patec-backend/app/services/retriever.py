"""Semantic retrieval service for PATEC RAG.

Uses pgvector cosine similarity to find the most relevant document chunks
for a given user query, scoped to a specific parecer's documents.
"""

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.documento_chunk import DocumentoChunk
from app.services.embedding import embed_query

logger = logging.getLogger(__name__)


async def retrieve_relevant_chunks(
    query: str,
    parecer_id: uuid.UUID,
    db: AsyncSession,
    top_k: int | None = None,
) -> list[DocumentoChunk]:
    """Retrieve the most relevant chunks for a query within a parecer's documents.

    Args:
        query: The user's question or search query.
        parecer_id: UUID of the parecer to scope the search.
        db: Async database session.
        top_k: Number of results to return (defaults to RAG_TOP_K from config).

    Returns:
        List of DocumentoChunk objects ordered by relevance (most relevant first).
    """
    if top_k is None:
        top_k = settings.RAG_TOP_K

    # 1. Embed the query
    try:
        query_embedding = await embed_query(query)
    except Exception:
        logger.exception("Failed to embed query for RAG retrieval")
        return []

    # 2. Search via pgvector cosine distance, filtered by parecer_id
    # Using raw SQL for pgvector operator support
    sql = text("""
        SELECT
            id, documento_id, parecer_id, conteudo, page_number,
            chunk_index, chunk_type, nome_arquivo, tipo_documento, criado_em,
            1 - (embedding <=> :query_vec::vector) AS similarity
        FROM documento_chunks
        WHERE parecer_id = :parecer_id
        ORDER BY embedding <=> :query_vec::vector
        LIMIT :top_k
    """)

    # Convert embedding list to pgvector string format: [0.1, 0.2, ...]
    vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    result = await db.execute(
        sql,
        {"query_vec": vec_str, "parecer_id": str(parecer_id), "top_k": top_k},
    )
    rows = result.fetchall()

    if not rows:
        logger.info("No chunks found for parecer %s", parecer_id)
        return []

    # 3. Build DocumentoChunk-like objects from results
    chunks = []
    for row in rows:
        chunk = DocumentoChunk(
            id=row.id,
            documento_id=row.documento_id,
            parecer_id=row.parecer_id,
            conteudo=row.conteudo,
            page_number=row.page_number,
            chunk_index=row.chunk_index,
            chunk_type=row.chunk_type,
            nome_arquivo=row.nome_arquivo,
            tipo_documento=row.tipo_documento,
            criado_em=row.criado_em,
        )
        # Attach similarity score as extra attribute
        chunk._similarity = row.similarity
        chunks.append(chunk)

    logger.info(
        "Retrieved %d chunks for parecer %s (top similarity: %.3f)",
        len(chunks),
        parecer_id,
        chunks[0]._similarity if chunks else 0,
    )

    return chunks
