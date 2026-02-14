import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # API Settings
    API_TITLE = "Julia API"
    API_VERSION = "2.0.0"
    API_DESCRIPTION = "Backend unificado para o Julia"

    # CORS
    CORS_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://noglem.com.br",
        "https://www.noglem.com.br",
        "https://julia.vercel.app",
    ]

    # Google Gemini
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

    # OpenAI (for RAG)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # Internal auth between Next.js and FastAPI
    INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")

    # Rate limits (requests per minute per user)
    RATE_LIMIT_TRANSLATE_PER_MIN = int(os.getenv("RATE_LIMIT_TRANSLATE_PER_MIN", "30"))
    RATE_LIMIT_PDF_PER_MIN = int(os.getenv("RATE_LIMIT_PDF_PER_MIN", "5"))

    # File Upload
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS = {".pdf"}

    # Paths
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/julia-uploads")
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/tmp/julia-outputs")


settings = Settings()
