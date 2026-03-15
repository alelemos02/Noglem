from pydantic_settings import BaseSettings
from pydantic import model_validator


class Settings(BaseSettings):
    PROJECT_NAME: str = "PATEC - Parecer Tecnico de Engenharia"
    API_V1_PREFIX: str = "/api/v1"

    # Database
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

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Gemini API
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_MAX_RETRIES: int = 4
    GEMINI_RETRY_BASE_SECONDS: float = 2.0
    GEMINI_RETRY_MAX_SECONDS: float = 20.0

    # Self-review: optional second LLM pass to verify flagged items
    ENABLE_LLM_SELF_REVIEW: bool = False

    # Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50
    DOCUMENT_ENCRYPTION_KEY: str = ""

    # Internal API Key (shared with Next.js proxy for secure communication)
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
