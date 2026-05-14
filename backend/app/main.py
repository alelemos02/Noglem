import os
import time
import json
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import translate, pdf, pid, auth, admin_notes, civil
from app.database import engine, Base
# Importar modelos para garantir que o SQLAlchemy os conheça antes de criar tabelas
import app.models.auth_models
import app.models.admin_notes_models

# Criar tabelas do banco de dados (SQLite)
Base.metadata.create_all(bind=engine)

# Criar diretórios necessários
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("julia")

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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000)

    # Ignora health checks para não poluir os logs
    if request.url.path not in ("/", "/health"):
        logger.info(json.dumps({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "method": request.method,
            "path": request.url.path,
            "user_id": request.headers.get("X-User-Id", "anonymous"),
            "status": response.status_code,
            "duration_ms": duration_ms,
        }))

    return response


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

app.include_router(pid.router, prefix="/api/pid", tags=["PID"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(admin_notes.router, prefix="/api/admin-notes", tags=["Admin Notes"])
app.include_router(civil.router, prefix="/api/civil", tags=["Civil"])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
