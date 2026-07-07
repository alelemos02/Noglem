import logging
import time
import uuid
from collections import defaultdict

import redis
from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)


class InMemoryRateLimiter:
    """Simple in-memory rate limiter with sliding window (per-processo)."""

    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _clean_old(self, key: str, now: float):
        cutoff = now - self.window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

    def check(self, key: str) -> tuple[bool, int]:
        """Check if request is allowed. Returns (allowed, remaining)."""
        now = time.time()
        self._clean_old(key, now)

        if len(self._requests[key]) >= self.max_requests:
            return False, 0

        self._requests[key].append(now)
        remaining = self.max_requests - len(self._requests[key])
        return True, remaining


class RedisRateLimiter:
    """Rate limiter COMPARTILHADO via Redis (sliding window com ZSET).

    Diferente do InMemoryRateLimiter (por processo), este limita globalmente
    entre replicas da API e o worker — o certo sob escala horizontal (Railway).
    Se o Redis estiver indisponivel, cai para um limitador em memoria: ainda
    protege por processo e NUNCA bloqueia usuarios por indisponibilidade do Redis.
    """

    def __init__(self, max_requests: int = 5, window_seconds: int = 60, prefix: str = "rl"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._prefix = prefix
        self._fallback = InMemoryRateLimiter(max_requests, window_seconds)
        self._client = None

    def _redis(self):
        if self._client is None:
            self._client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._client

    def check(self, key: str) -> tuple[bool, int]:
        now = time.time()
        rkey = f"ratelimit:{self._prefix}:{key}"
        member = f"{now:.6f}:{uuid.uuid4().hex}"
        try:
            client = self._redis()
            pipe = client.pipeline()
            pipe.zremrangebyscore(rkey, 0, now - self.window_seconds)
            pipe.zadd(rkey, {member: now})
            pipe.zcard(rkey)
            pipe.expire(rkey, self.window_seconds)
            count = pipe.execute()[2]
            if count > self.max_requests:
                # excedeu: remove o proprio registro para nao contar a tentativa bloqueada
                client.zrem(rkey, member)
                return False, 0
            return True, self.max_requests - count
        except Exception:
            logger.warning(
                "Redis rate limiter indisponivel — usando fallback em memoria",
                exc_info=True,
            )
            return self._fallback.check(key)


# Rate limiter for analysis endpoints: 5 requests per 60 seconds per user
# (compartilhado via Redis — antes era por processo, inefetivo com replicas)
analysis_rate_limiter = RedisRateLimiter(max_requests=5, window_seconds=60, prefix="analysis")


async def check_analysis_rate_limit(request: Request, user_id: str):
    """Check rate limit for analysis endpoints. Raises 429 if exceeded."""
    key = f"analysis:{user_id}"
    allowed, remaining = analysis_rate_limiter.check(key)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Limite de requisicoes excedido. "
                f"Maximo de {analysis_rate_limiter.max_requests} analises "
                f"por {analysis_rate_limiter.window_seconds} segundos."
            ),
            headers={"Retry-After": str(analysis_rate_limiter.window_seconds)},
        )
