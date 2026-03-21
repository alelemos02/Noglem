"""Semantic retrieval service for Conhecimento RAG.

Uses pgvector cosine similarity for initial retrieval, then FlashRank
cross-encoder reranking to return the most relevant document chunks.
"""

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document_chunk import DocumentoChunk
from app.services.embedding import embed_query
from app.services.reranker import get_reranker_service

logger = logging.getLogger(__name__)


async def retrieve_relevant_chunks(
    query: str,
    collection_id: str,
    db: AsyncSession,
    top_k_initial: int | None = None,
    top_k_final: int | None = None,
) -> list[DocumentoChunk]:
    """Retrieve the most relevant chunks for a query within a collection.

    Two-stage pipeline:
    1. pgvector cosine similarity → top_k_initial candidates
    2. FlashRank cross-encoder reranking → top_k_final results

    Args:
        query: The user's question or search query.
        collection_id: UUID of the collection to scope the search.
        db: Async database session.
        top_k_initial: Number of candidates for reranking (defaults to RAG_TOP_K_INITIAL).
        top_k_final: Number of final results (defaults to RAG_TOP_K_FINAL).

    Returns:
        List of DocumentoChunk objects ordered by relevance (most relevant first).
    """
    if top_k_initial is None:
        top_k_initial = settings.RAG_TOP_K_INITIAL
    if top_k_final is None:
        top_k_final = settings.RAG_TOP_K_FINAL

    # 1. Embed the query
    try:
        query_embedding = await embed_query(query)
    except Exception:
        logger.exception("Failed to embed query for RAG retrieval")
        return []

    # 2. Search via pgvector cosine distance, filtered by collection_id
    sql = text("""
        SELECT
            id, document_id, collection_id, conteudo, page_number,
            chunk_index, chunk_type, nome_arquivo, created_at,
            1 - (embedding <=> :query_vec::vector) AS similarity
        FROM con_document_chunks
        WHERE collection_id = :collection_id
        ORDER BY embedding <=> :query_vec::vector
        LIMIT :top_k
    """)

    vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    result = await db.execute(
        sql,
        {"query_vec": vec_str, "collection_id": collection_id, "top_k": top_k_initial},
    )
    rows = result.fetchall()

    if not rows:
        logger.info("No chunks found for collection %s", collection_id)
        return []

    # 3. Build DocumentoChunk objects from results
    initial_chunks = []
    for row in rows:
        chunk = DocumentoChunk(
            id=row.id,
            document_id=row.document_id,
            collection_id=row.collection_id,
            conteudo=row.conteudo,
            page_number=row.page_number,
            chunk_index=row.chunk_index,
            chunk_type=row.chunk_type,
            nome_arquivo=row.nome_arquivo,
            created_at=row.created_at,
        )
        chunk._similarity = row.similarity
        initial_chunks.append(chunk)

    logger.info(
        "Retrieved %d initial chunks for collection %s (top similarity: %.3f)",
        len(initial_chunks),
        collection_id,
        initial_chunks[0]._similarity if initial_chunks else 0,
    )

    # 4. Rerank with FlashRank cross-encoder
    try:
        reranked = get_reranker_service().rerank(
            query=query,
            chunks=initial_chunks,
            top_k=top_k_final,
        )

        if not reranked:
            logger.warning("Reranker returned empty results, using similarity results")
            return initial_chunks[:top_k_final]

        # Check for near-zero scores (reranker failed to distinguish)
        if reranked[0].score <= 0.0001:
            logger.warning("Reranker scores too low (%.6f), falling back to similarity", reranked[0].score)
            return initial_chunks[:top_k_final]

        # Map reranked results back to chunk objects
        chunk_by_id = {str(c.id): c for c in initial_chunks}
        final_chunks = []
        for r in reranked:
            chunk = chunk_by_id.get(r.chunk_id)
            if chunk:
                chunk._rerank_score = r.score
                final_chunks.append(chunk)

        logger.info(
            "Reranked to %d chunks (top rerank score: %.4f)",
            len(final_chunks),
            reranked[0].score,
        )
        return final_chunks

    except Exception:
        logger.exception("Reranking failed, falling back to similarity results")
        return initial_chunks[:top_k_final]
