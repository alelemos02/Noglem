import logging

from fastapi import Header, HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)


async def require_internal_api_key(
    x_internal_api_key: str = Header(default=""),
) -> str:
    """Validate the internal API key from the request header."""
    if not settings.INTERNAL_API_KEY:
        # No key configured — allow all requests (dev mode)
        return "dev"

    if x_internal_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    return x_internal_api_key
