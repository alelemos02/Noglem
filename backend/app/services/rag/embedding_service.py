from langchain_openai import OpenAIEmbeddings
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            logging.warning("OPENAI_API_KEY not found. Embedding service may fail.")

        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY
        )

    def get_embeddings(self):
        return self.embeddings


# Lazy singleton — only instantiated on first access
_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
