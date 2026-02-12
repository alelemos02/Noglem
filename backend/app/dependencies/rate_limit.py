import math
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Header, HTTPException, Request, status

from app.config import settings


class InMemoryRateLimiter:
    """Simple process-local sliding-window rate limiter."""

    def __init__(self):
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.time()
        with self._lock:
            bucket = self._buckets[key]
            cutoff = now - window_seconds

            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(1, math.ceil(window_seconds - (now - bucket[0])))
                return False, retry_after

            bucket.append(now)
            return True, 0


limiter = InMemoryRateLimiter()


def _identity(request: Request, x_user_id: str | None) -> str:
    if x_user_id and x_user_id.strip():
        return x_user_id.strip()

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def _raise_limit_exceeded(retry_after: int):
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Limite de requisições excedido. Tente novamente em instantes.",
        headers={"Retry-After": str(retry_after)},
    )


async def enforce_translate_rate_limit(
    request: Request,
    x_user_id: str | None = Header(default=None),
):
    user = _identity(request, x_user_id)
    allowed, retry_after = limiter.allow(
        key=f"translate:{user}",
        limit=settings.RATE_LIMIT_TRANSLATE_PER_MIN,
        window_seconds=60,
    )
    if not allowed:
        _raise_limit_exceeded(retry_after)


async def enforce_pdf_rate_limit(
    request: Request,
    x_user_id: str | None = Header(default=None),
):
    user = _identity(request, x_user_id)
    allowed, retry_after = limiter.allow(
        key=f"pdf:{user}",
        limit=settings.RATE_LIMIT_PDF_PER_MIN,
        window_seconds=60,
    )
    if not allowed:
        _raise_limit_exceeded(retry_after)

