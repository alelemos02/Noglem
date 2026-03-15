import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    """Simple in-memory rate limiter with sliding window."""

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


# Rate limiter for analysis endpoints: 5 requests per 60 seconds per user
analysis_rate_limiter = InMemoryRateLimiter(max_requests=5, window_seconds=60)


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
