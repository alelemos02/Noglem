from langchain_openai import OpenAIEmbeddings
from app.config import settings
import logging

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

embedding_service = EmbeddingService()
