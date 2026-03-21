import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # API Settings
    API_TITLE = "Julia API"
    API_VERSION = "2.0.1"
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
    RATE_LIMIT_PID_PER_MIN = int(os.getenv("RATE_LIMIT_PID_PER_MIN", "5"))

    # Microsoft Graph (Email RAG)
    MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "")
    MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "")
    MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID", "common")
    MICROSOFT_REDIRECT_URI = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:3000/api/email/callback")
    MICROSOFT_SCOPES = ["Mail.Read", "User.Read", "offline_access"]

    # Email RAG — Embeddings locais
    EMAIL_EMBEDDING_MODEL = os.getenv("EMAIL_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    EMAIL_CHROMA_COLLECTION = os.getenv("EMAIL_CHROMA_COLLECTION", "email_rag_collection")

    # File Upload
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS = {".pdf", ".docx"}

    # Paths
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/julia-uploads")
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/tmp/julia-outputs")
    # Base dir for data persistence
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    CHROMA_DB_DIR = os.getenv("CHROMA_DB_DIR", os.path.join(DATA_DIR, "chroma_db"))


settings = Settings()
