from fastapi import Header, HTTPException, status

from app.config import settings


async def require_internal_api_key(
    x_internal_api_key: str | None = Header(default=None),
):
    """Accept only trusted requests coming from the Next.js backend."""
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="INTERNAL_API_KEY não configurada no backend",
        )

    if x_internal_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autorizado",
        )

