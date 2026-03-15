from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.error_handlers import register_exception_handlers


def _app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/http-error")
    async def http_error():
        raise HTTPException(status_code=400, detail="falha de regra")

    @app.get("/explode")
    async def explode():
        raise RuntimeError("boom")

    @app.get("/echo/{value}")
    async def echo(value: int):
        return {"value": value}

    return app


def test_http_exception_handler_returns_standard_payload():
    client = TestClient(_app())
    response = client.get("/http-error")
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "http_error"
    assert body["error"]["message"] == "falha de regra"
    assert "request_id" in body["error"]


def test_unhandled_exception_returns_internal_error_payload():
    client = TestClient(_app(), raise_server_exceptions=False)
    response = client.get("/explode")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "request_id" in body["error"]


def test_validation_error_handler_returns_422():
    client = TestClient(_app())
    response = client.get("/echo/not-an-int")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Requisicao invalida"
