import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_TITLE: str = "Conhecimento RAG Backend"
    API_VERSION: str = "1.0.0"
    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # DB settings
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    SQLALCHEMY_DATABASE_URL: str = f"sqlite:///{os.path.join(DATA_DIR, 'rag_app.db')}"
    CHROMA_DB_DIR: str = os.getenv("CHROMA_DB_DIR", os.path.join(DATA_DIR, "chroma_db"))
    
    # Files
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/tmp/julia-rag-uploads")
    
settings = Settings()
