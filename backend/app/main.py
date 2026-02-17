import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import translate, pdf, rag
from app.database import engine, Base
# Importar modelos para garantir que o SQLAlchemy os conheça antes de criar tabelas
import app.models.rag_models

# Criar tabelas do banco de dados (SQLite)
Base.metadata.create_all(bind=engine)

# Criar diretórios necessários
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

# Criar aplicação FastAPI
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/")
async def root():
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "healthy",
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# Registrar routers
app.include_router(translate.router, prefix="/api/translate", tags=["Translate"])
app.include_router(pdf.router, prefix="/api/pdf", tags=["PDF"])
app.include_router(rag.router, prefix="/api/rag", tags=["RAG"])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
