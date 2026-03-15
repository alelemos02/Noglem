import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token, get_password_hash
from app.models.usuario import Usuario

security = HTTPBearer(auto_error=False)
DIRECT_ACCESS_EMAIL = "acesso-direto@patec.local"
DIRECT_ACCESS_NAME = "Acesso Direto"
DIRECT_ACCESS_PASSWORD = "acesso-direto-local"


async def _get_or_create_direct_access_user(db: AsyncSession) -> Usuario:
    result = await db.execute(select(Usuario).where(Usuario.email == DIRECT_ACCESS_EMAIL))
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
    db: AsyncSession = Depends(get_db),
) -> Usuario:
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
                    result = await db.execute(select(Usuario).where(Usuario.id == parsed_user_id))
                    user = result.scalar_one_or_none()
                    if user and user.ativo:
                        return user

    # Fallback for direct-access mode: app works without explicit login/token.
    return await _get_or_create_direct_access_user(db)


def require_role(*roles: str):
    async def role_checker(current_user: Usuario = Depends(get_current_user)) -> Usuario:
        if current_user.papel not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. Papel necessario: {', '.join(roles)}",
            )
        return current_user
    return role_checker
