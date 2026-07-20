"""Semantic retrieval service for PATEC RAG.

Uses pgvector cosine similarity to find the most relevant document chunks
for a given user query, scoped to a specific parecer's documents.
"""

import asyncio
import logging
import uuid

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.documento_chunk import DocumentoChunk
from app.services.embedding import embed_query

logger = logging.getLogger(__name__)


def _build_sql(com_filtro_documentos: bool):
    """SQL da busca por cosine distance (pgvector), opcionalmente filtrada por
    documentos específicos (ex.: passe de amarrações — só o anexo citado).

    NB: usamos CAST(... AS vector) em vez de `::vector` — o operador `::`
    colide com a sintaxe de bind param `:nome` do SQLAlchemy text() e gera
    "syntax error at or near :".
    """
    doc_filter = "AND documento_id IN :doc_ids" if com_filtro_documentos else ""
    sql = text(f"""
        SELECT
            id, documento_id, parecer_id, conteudo, page_number,
            chunk_index, chunk_type, nome_arquivo, tipo_documento, criado_em,
            1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
        FROM documento_chunks
        WHERE parecer_id = :parecer_id
        {doc_filter}
        ORDER BY embedding <=> CAST(:query_vec AS vector)
        LIMIT :top_k
    """)
    if com_filtro_documentos:
        sql = sql.bindparams(bindparam("doc_ids", expanding=True))
    return sql


def _build_params(
    query_embedding: list[float],
    parecer_id: uuid.UUID,
    top_k: int,
    documento_ids: list[uuid.UUID] | None,
) -> dict:
    # Convert embedding list to pgvector string format: [0.1, 0.2, ...]
    vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    params = {"query_vec": vec_str, "parecer_id": str(parecer_id), "top_k": top_k}
    if documento_ids:
        params["doc_ids"] = [str(d) for d in documento_ids]
    return params


def _rows_to_chunks(rows, parecer_id: uuid.UUID) -> list[DocumentoChunk]:
    if not rows:
        logger.info("No chunks found for parecer %s", parecer_id)
        return []

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


async def retrieve_relevant_chunks(
    query: str,
    parecer_id: uuid.UUID,
    db: AsyncSession,
    top_k: int | None = None,
    documento_ids: list[uuid.UUID] | None = None,
) -> list[DocumentoChunk]:
    """Retrieve the most relevant chunks for a query within a parecer's documents.

    Args:
        query: The user's question or search query.
        parecer_id: UUID of the parecer to scope the search.
        db: Async database session.
        top_k: Number of results to return (defaults to RAG_TOP_K from config).
        documento_ids: Optional — restringe a busca a documentos específicos.

    Returns:
        List of DocumentoChunk objects ordered by relevance (most relevant first).
    """
    if top_k is None:
        top_k = settings.RAG_TOP_K

    try:
        query_embedding = await embed_query(query)
    except Exception:
        logger.exception("Failed to embed query for RAG retrieval")
        return []

    result = await db.execute(
        _build_sql(bool(documento_ids)),
        _build_params(query_embedding, parecer_id, top_k, documento_ids),
    )
    return _rows_to_chunks(result.fetchall(), parecer_id)


def retrieve_relevant_chunks_sync(
    query: str,
    parecer_id: uuid.UUID,
    db: Session,
    *,
    top_k: int | None = None,
    documento_ids: list[uuid.UUID] | None = None,
) -> list[DocumentoChunk]:
    """Versão sync de retrieve_relevant_chunks para o worker Celery (passe de
    amarrações da extração). Roda o embedding async via asyncio.run — mesmo
    precedente de index_document_sync."""
    if top_k is None:
        top_k = settings.RAG_TOP_K

    try:
        query_embedding = asyncio.run(embed_query(query))
    except Exception:
        logger.exception("Failed to embed query for RAG retrieval (sync)")
        return []

    result = db.execute(
        _build_sql(bool(documento_ids)),
        _build_params(query_embedding, parecer_id, top_k, documento_ids),
    )
    return _rows_to_chunks(result.fetchall(), parecer_id)
