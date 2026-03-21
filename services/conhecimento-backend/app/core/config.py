from pydantic_settings import BaseSettings
from pydantic import model_validator


class Settings(BaseSettings):
    PROJECT_NAME: str = "Conhecimento RAG - Base de Conhecimento"
    API_PREFIX: str = "/api/rag"

    # Database (same PostgreSQL instance as PATEC)
    DATABASE_URL: str = "postgresql+asyncpg://patec:patec@localhost:5432/patec"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://patec:patec@localhost:5432/patec"

    @model_validator(mode="after")
    def fix_database_urls(self):
        """Auto-convert Railway-style postgresql:// to driver-specific URLs."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://") or url.startswith("postgres://"):
            base = url.replace("postgres://", "postgresql://", 1)
            self.DATABASE_URL = base.replace("postgresql://", "postgresql+asyncpg://", 1)
            self.DATABASE_URL_SYNC = base.replace("postgresql://", "postgresql+psycopg2://", 1)
        return self

    # Gemini API
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    GEMINI_MAX_RETRIES: int = 4
    GEMINI_RETRY_BASE_SECONDS: float = 2.0
    GEMINI_RETRY_MAX_SECONDS: float = 20.0

    # RAG Configuration
    RAG_CHUNK_SIZE: int = 1500
    RAG_CHUNK_OVERLAP: int = 200
    RAG_TOP_K_INITIAL: int = 40  # Over-fetch for reranking
    RAG_TOP_K_FINAL: int = 7  # After reranking

    # Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50

    # Reranker
    RERANK_MODEL: str = "ms-marco-TinyBERT-L-2-v2"
    RERANK_CACHE_DIR: str = "./data/rerank_cache"

    # Internal API Key (shared with Next.js proxy)
    INTERNAL_API_KEY: str = ""

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost",
        "http://127.0.0.1",
    ]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
