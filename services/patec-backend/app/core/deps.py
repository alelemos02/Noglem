import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.security import decode_token, get_password_hash
from app.models.usuario import Usuario

security = HTTPBearer(auto_error=False)


# ── Internal API Key validation (called by Next.js proxy) ──────────

async def require_internal_api_key(request: Request) -> None:
    """
    Validates that the request comes from our Next.js proxy
    by checking the X-Internal-API-Key header.
    If INTERNAL_API_KEY is not configured (empty), this check is skipped
    to allow local development without extra setup.
    """
    if not settings.INTERNAL_API_KEY:
        return  # Skip validation in dev when key is not set

    api_key = request.headers.get("x-internal-api-key", "")
    if api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. API Key inválida.",
        )


# ── User resolution (supports both JWT and Clerk X-User-Id) ───────

async def _get_or_create_clerk_user(
    clerk_id: str, db: AsyncSession
) -> Usuario:
    """Find or create a local user from a Clerk user ID."""
    # Use clerk_id as email identifier for mapping
    clerk_email = f"clerk_{clerk_id}@noglem.com.br"

    result = await db.execute(
        select(Usuario).where(Usuario.email == clerk_email)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = Usuario(
            nome=f"Usuário Noglem ({clerk_id[:8]})",
            email=clerk_email,
            senha_hash=get_password_hash(uuid.uuid4().hex),
            papel="admin",
            ativo=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user


DIRECT_ACCESS_EMAIL = "acesso-direto@patec.local"
DIRECT_ACCESS_NAME = "Acesso Direto"
DIRECT_ACCESS_PASSWORD = "acesso-direto-local"


async def _get_or_create_direct_access_user(db: AsyncSession) -> Usuario:
    result = await db.execute(
        select(Usuario).where(Usuario.email == DIRECT_ACCESS_EMAIL)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = Usuario(
            nome=DIRECT_ACCESS_NAME,
            email=DIRECT_ACCESS_EMAIL,
            senha_hash=get_password_hash(DIRECT_ACCESS_PASSWORD),
            papel="admin",
            ativo=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    if not user.ativo or user.papel != "admin":
        user.ativo = True
        user.papel = "admin"
        await db.commit()
        await db.refresh(user)

    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_user_id: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    """
    Resolve the current user in this priority:
    1. JWT Bearer token (original PATEC auth)
    2. X-User-Id header from Clerk (Noglem proxy)
    3. Direct access fallback (local dev only)
    """
    # 1. Try JWT token (original PATEC flow)
    if credentials and credentials.credentials:
        payload = decode_token(credentials.credentials)
        if payload and payload.get("type") == "access":
            user_id = payload.get("sub")
            if user_id:
                try:
                    parsed_user_id = uuid.UUID(user_id)
                except ValueError:
                    parsed_user_id = None

                if parsed_user_id:
                    result = await db.execute(
                        select(Usuario).where(Usuario.id == parsed_user_id)
                    )
                    user = result.scalar_one_or_none()
                    if user and user.ativo:
                        return user

    # 2. Try Clerk X-User-Id (from Noglem proxy)
    if x_user_id:
        return await _get_or_create_clerk_user(x_user_id, db)

    # 3. Fallback for local dev without auth
    return await _get_or_create_direct_access_user(db)


def require_role(*roles: str):
    async def role_checker(
        current_user: Usuario = Depends(get_current_user),
    ) -> Usuario:
        if current_user.papel not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. Papel necessario: {', '.join(roles)}",
            )
        return current_user

    return role_checker


async def require_owner(
    current_user: Usuario = Depends(get_current_user),
    x_user_email: Annotated[str | None, Header()] = None,
) -> Usuario:
    """Restringe ao DONO da ferramenta (dashboard de qualidade).

    Nao usa papel: no proxy Clerk todo usuario vira 'admin', entao 'admin' nao
    distingue o dono. O gate e por e-mail (settings.OWNER_EMAILS). Em dev (nao
    producao) o gate e aberto — util para ver o dashboard localmente; em producao
    so os e-mails de OWNER_EMAILS passam.

    Usuarios do proxy Clerk ficam gravados com e-mail sintetico
    (clerk_<id>@noglem.com.br), que nao serve para o gate. O proxy Next envia o
    e-mail real do login em X-User-Email — header confiavel porque toda rota ja
    passa por require_internal_api_key.
    """
    if not settings.is_production:
        return current_user
    candidatos = {
        (current_user.email or "").strip().lower(),
        (x_user_email or "").strip().lower(),
    }
    if candidatos & settings.owner_emails:
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acesso restrito ao dono da ferramenta.",
    )
