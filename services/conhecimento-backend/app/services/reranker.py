"""FlashRank reranking service for Conhecimento RAG.

Uses a lightweight cross-encoder model to rerank document chunks
after initial vector similarity retrieval, improving result quality.

Ported from the old RAG service — LangChain dependency removed.
"""

import logging
import os
from dataclasses import dataclass

from flashrank import Ranker, RerankRequest

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    """A reranked chunk with its score."""
    chunk_id: str
    text: str
    score: float
    metadata: dict


class RerankerService:
    def __init__(self):
        cache_dir = settings.RERANK_CACHE_DIR
        os.makedirs(cache_dir, exist_ok=True)
        self.ranker = Ranker(model_name=settings.RERANK_MODEL, cache_dir=cache_dir)

    def rerank(
        self,
        query: str,
        chunks: list,
        top_k: int = 7,
    ) -> list[RerankResult]:
        """Rerank a list of document chunks by relevance to the query.

        Args:
            query: The user's search query.
            chunks: List of DocumentoChunk objects (SQLAlchemy models).
            top_k: Number of top results to return.

        Returns:
            List of RerankResult ordered by relevance (best first).
        """
        if not chunks:
            return []

        # Convert chunks to FlashRank input format
        passages = []
        chunk_map = {}
        for i, chunk in enumerate(chunks):
            chunk_id = str(chunk.id) if hasattr(chunk, "id") else str(i)
            passages.append({
                "id": chunk_id,
                "text": chunk.conteudo,
                "meta": {
                    "index": i,
                    "page_number": chunk.page_number,
                    "chunk_type": chunk.chunk_type,
                    "nome_arquivo": chunk.nome_arquivo,
                },
            })
            chunk_map[chunk_id] = chunk

        request = RerankRequest(query=query, passages=passages)
        results = self.ranker.rerank(request)

        # Take top-K and build result objects
        top_results = results[:top_k]
        reranked = []
        for res in top_results:
            reranked.append(RerankResult(
                chunk_id=res["id"],
                text=res["text"],
                score=res["score"],
                metadata=res["meta"],
            ))

        return reranked


# Lazy singleton — only instantiated on first access
_reranker_service = None


def get_reranker_service() -> RerankerService:
    global _reranker_service
    if _reranker_service is None:
        _reranker_service = RerankerService()
    return _reranker_service
