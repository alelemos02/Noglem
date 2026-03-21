"""FlashRank reranking service — retained for the Email RAG feature.

The Conhecimento RAG has been migrated to services/conhecimento-backend/.
This file is kept because the Email RAG service depends on it.
"""

from flashrank import Ranker, RerankRequest
from typing import List, Any
from langchain_core.documents import Document
import os
from app.config import settings


class RerankService:
    def __init__(self):
        cache_dir = os.path.join(settings.DATA_DIR, "rerank_cache")
        os.makedirs(cache_dir, exist_ok=True)
        self.ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2", cache_dir=cache_dir)

    def rerank(self, query: str, documents: List[Any], top_k: int = 5) -> List[Any]:
        if not documents:
            return []

        passages = []
        for i, doc in enumerate(documents):
            doc_id = str(doc.metadata.get("id", i))
            passages.append({
                "id": doc_id,
                "text": doc.page_content,
                "meta": doc.metadata,
            })

        request = RerankRequest(query=query, passages=passages)
        results = self.ranker.rerank(request)

        top_results = results[:top_k]
        reranked_docs = []

        for res in top_results:
            doc = Document(
                page_content=res["text"],
                metadata=res["meta"],
            )
            doc.metadata["rerank_score"] = res["score"]
            reranked_docs.append(doc)

        return reranked_docs


_rerank_service = None


def get_rerank_service() -> RerankService:
    global _rerank_service
    if _rerank_service is None:
        _rerank_service = RerankService()
    return _rerank_service
