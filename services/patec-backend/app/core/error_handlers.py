import logging
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    existing = request.headers.get("x-request-id")
    if existing:
        return existing
    return str(uuid.uuid4())


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        req_id = _request_id(request)
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Requisicao invalida",
                    "details": exc.errors(),
                    "request_id": req_id,
                }
            },
            headers={"X-Request-Id": req_id},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        req_id = _request_id(request)
        detail = exc.detail if isinstance(exc.detail, str) else "Erro na requisicao"
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "http_error",
                    "message": detail,
                    "request_id": req_id,
                }
            },
            headers={"X-Request-Id": req_id},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        req_id = _request_id(request)
        logger.exception("Unhandled error request_id=%s", req_id, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Erro interno do servidor",
                    "request_id": req_id,
                }
            },
            headers={"X-Request-Id": req_id},
        )
