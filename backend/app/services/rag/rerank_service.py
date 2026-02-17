from flashrank import Ranker, RerankRequest
from typing import List, Dict, Any
from langchain_core.documents import Document
import os
from app.config import settings

class RerankService:
    def __init__(self):
        # Using a lightweight model fast enough for CPU
        cache_dir = os.path.join(settings.DATA_DIR, "rerank_cache")
        os.makedirs(cache_dir, exist_ok=True)
        self.ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2", cache_dir=cache_dir)

    def rerank(self, query: str, documents: List[Any], top_k: int = 5) -> List[Any]:
        """
        Reranks a list of Langchain Document objects based on relevance to the query.
        """
        if not documents:
            return []

        # Convert Langchain Docs to FlashRank Input format
        # Input: list of dicts with "id" and "text" (and "meta")
        passages = []
        for i, doc in enumerate(documents):
            # Using index as fallback ID if none in metadata
            doc_id = str(doc.metadata.get("id", i))
            passages.append({
                "id": doc_id,
                "text": doc.page_content,
                "meta": doc.metadata
            })

        # FlashRank requires 'query' and 'passages'
        request = RerankRequest(query=query, passages=passages)
        results = self.ranker.rerank(request)

        # Take Top K
        top_results = results[:top_k]

        # Convert back to Langchain Documents (preserving score if possible, or just order)
        reranked_docs = []
        
        for res in top_results:
            # We reconstruct the document
            doc = Document(
                page_content=res["text"],
                metadata=res["meta"]
            )
            # Inject score into metadata for debugging/UI
            doc.metadata["rerank_score"] = res["score"]
            reranked_docs.append(doc)

        return reranked_docs

rerank_service = RerankService()
