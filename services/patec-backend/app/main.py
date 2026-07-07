import logging
import uuid

import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.error_handlers import register_exception_handlers
from app.api.v1.router import api_router
from app.core.logging import setup_logging

# Initialize structured logging
setup_logging()

logger = logging.getLogger(__name__)


def _validar_modelos_gemini() -> None:
    """Fail-fast quando um modelo Gemini configurado nao existe (404).

    Um nome de modelo invalido (ex.: 'gemini-3.1-pro' sem o sufixo '-preview')
    so quebraria no primeiro uso — aqui a falha aparece no startup. Erros
    transitorios (rede, 429, 5xx) NAO derrubam o boot: apenas logam aviso.
    """
    api_key = settings.GEMINI_API_KEY.strip()
    if not api_key:
        msg = "GEMINI_API_KEY nao configurada."
        if settings.is_production:
            raise RuntimeError(msg)
        logger.warning("%s Validacao de modelos ignorada (dev).", msg)
        return

    for nome in sorted(settings.gemini_models()):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{nome}"
        try:
            resp = httpx.get(url, params={"key": api_key}, timeout=15.0)
        except httpx.HTTPError as exc:
            logger.warning(
                "Nao foi possivel validar o modelo '%s' no startup (%s). "
                "Seguindo — sera checado no primeiro uso.",
                nome, exc,
            )
            continue
        if resp.status_code == 404:
            raise RuntimeError(
                f"Modelo Gemini invalido: '{nome}' retornou 404. Corrija o nome "
                "(ex.: sufixo '-preview') em GEMINI_MODEL / "
                "GEMINI_EXTRACTION_MODEL / GEMINI_VERIFIER_MODEL."
            )
        if resp.status_code >= 400:
            logger.warning(
                "Validacao do modelo '%s' retornou HTTP %d — seguindo.",
                nome, resp.status_code,
            )
        else:
            logger.info("Modelo Gemini '%s' OK.", nome)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
register_exception_handlers(app)


@app.middleware("http")
async def add_request_id_header(request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


@app.on_event("startup")
async def _startup_checks():
    # Ordem: segredos primeiro (barato, so leitura), depois modelos (rede).
    settings.validate_production_secrets()
    _validar_modelos_gemini()


@app.get("/health")
async def health_check(deep: bool = Query(default=False)):
    """Health check. Com ?deep=1 faz 1 chamada minima a LLM para detectar
    quebra de modelo/quota antes do usuario (nao use como liveness probe)."""
    if not deep:
        return {"status": "ok", "project": settings.PROJECT_NAME}

    from app.services.llm_client import call_llm

    try:
        call_llm("Responda apenas com a palavra: ok", "ping", max_output_tokens=16)
        llm_ok, detalhe = True, None
    except Exception as exc:  # noqa: BLE001 — health nunca deve estourar 500
        detalhe = str(exc)[:200]
        # Um corte por MAX_TOKENS PROVA que o modelo respondeu (existe, key valida,
        # sem 404/quota) — apenas nao coube texto no orcamento. Isso e alcancavel.
        # Modelos "thinking" (ex.: 2.5-flash) gastam o orcamento pensando.
        llm_ok = "MAX_TOKENS" in detalhe
        if llm_ok:
            detalhe = None
    return {
        "status": "ok" if llm_ok else "degraded",
        "project": settings.PROJECT_NAME,
        "llm": {"ok": llm_ok, "model": settings.GEMINI_MODEL, "detalhe": detalhe},
    }
