import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
import app.models.rag_models
from app.core.deps import require_internal_api_key

# Modifica as rotas pra injetar a dependencia
from app.api.v1.endpoints import rag
rag.router.dependencies = [Depends(require_internal_api_key)]

Base.metadata.create_all(bind=engine)

from sqlalchemy import text, inspect
with engine.connect() as conn:
    inspector = inspect(engine)
    if "documents" in inspector.get_table_names():
        existing_cols = [c["name"] for c in inspector.get_columns("documents")]
        if "error_message" not in existing_cols:
            conn.execute(text("ALTER TABLE documents ADD COLUMN error_message TEXT"))
            conn.commit()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

app = FastAPI(title=settings.API_TITLE, version=settings.API_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rag.router, prefix="/api/rag", tags=["RAG"])
