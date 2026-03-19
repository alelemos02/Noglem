from fastapi import Request, HTTPException
from app.core.config import settings

async def require_internal_api_key(request: Request) -> None:
    if not settings.INTERNAL_API_KEY:
        return  # Skip in local dev se nao estiver configurado
    
    api_key = request.headers.get("x-internal-api-key", "")
    if api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="API Key inválida")
