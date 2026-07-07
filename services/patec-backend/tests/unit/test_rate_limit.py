import uuid

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.rate_limit import (
    InMemoryRateLimiter,
    RedisRateLimiter,
    check_analysis_rate_limit,
)


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def test_in_memory_rate_limiter_allows_then_blocks():
    limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60)
    allowed_1, remaining_1 = limiter.check("u1")
    allowed_2, remaining_2 = limiter.check("u1")
    allowed_3, remaining_3 = limiter.check("u1")

    assert allowed_1 is True and remaining_1 == 1
    assert allowed_2 is True and remaining_2 == 0
    assert allowed_3 is False and remaining_3 == 0


def test_redis_rate_limiter_allows_then_blocks():
    # Chave unica por execucao: com Redis no ar limita globalmente; sem Redis cai
    # no fallback em memoria — em ambos os casos, 2 permitidos e o 3o bloqueado.
    limiter = RedisRateLimiter(max_requests=2, window_seconds=60, prefix="pytest")
    key = uuid.uuid4().hex
    assert limiter.check(key)[0] is True
    assert limiter.check(key)[0] is True
    assert limiter.check(key)[0] is False


def test_redis_rate_limiter_fallback_quando_redis_indisponivel(monkeypatch):
    limiter = RedisRateLimiter(max_requests=2, window_seconds=60, prefix="pytest")

    def _boom():
        raise ConnectionError("redis indisponivel")

    monkeypatch.setattr(limiter, "_redis", _boom)
    # Cai no fallback em memoria e continua limitando (nunca bloqueia por erro).
    assert limiter.check("k")[0] is True
    assert limiter.check("k")[0] is True
    assert limiter.check("k")[0] is False


@pytest.mark.asyncio
async def test_check_analysis_rate_limit_raises_429_after_limit():
    req = _request()
    user = f"pytest-{uuid.uuid4().hex}"  # chave unica p/ isolar do estado do Redis
    for _ in range(5):
        await check_analysis_rate_limit(req, user)

    try:
        await check_analysis_rate_limit(req, user)
        assert False, "Era esperado HTTPException 429"
    except HTTPException as exc:
        assert exc.status_code == 429
