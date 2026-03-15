from langchain_huggingface import HuggingFaceEmbeddings
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class LocalEmbeddingService:
    def __init__(self):
        self._embeddings = None

    def get_embeddings(self) -> HuggingFaceEmbeddings:
        if self._embeddings is None:
            logger.info(f"Carregando modelo de embeddings local: {settings.EMAIL_EMBEDDING_MODEL}")
            self._embeddings = HuggingFaceEmbeddings(
                model_name=settings.EMAIL_EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            logger.info("Modelo de embeddings local carregado")
        return self._embeddings


_local_embedding_service = None


def get_local_embedding_service() -> LocalEmbeddingService:
    global _local_embedding_service
    if _local_embedding_service is None:
        _local_embedding_service = LocalEmbeddingService()
    return _local_embedding_service
