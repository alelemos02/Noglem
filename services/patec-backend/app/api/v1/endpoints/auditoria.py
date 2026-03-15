import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.audit_log import AuditLog
from app.models.usuario import Usuario
from app.schemas.audit_log import AuditLogResponse, AuditLogListResponse

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("", response_model=AuditLogListResponse)
async def listar_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    acao: str | None = None,
    recurso: str | None = None,
    usuario_email: str | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(require_role("admin")),
):
    """List audit logs (admin only)."""
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if acao:
        query = query.where(AuditLog.acao == acao)
        count_query = count_query.where(AuditLog.acao == acao)
    if recurso:
        query = query.where(AuditLog.recurso == recurso)
        count_query = count_query.where(AuditLog.recurso == recurso)
    if usuario_email:
        query = query.where(AuditLog.usuario_email.ilike(f"%{usuario_email}%"))
        count_query = count_query.where(AuditLog.usuario_email.ilike(f"%{usuario_email}%"))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(AuditLog.criado_em.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    logs = result.scalars().all()

    return AuditLogListResponse(
        items=[
            AuditLogResponse(
                id=str(log.id),
                usuario_id=str(log.usuario_id) if log.usuario_id else None,
                usuario_email=log.usuario_email,
                acao=log.acao,
                recurso=log.recurso,
                recurso_id=log.recurso_id,
                detalhes=log.detalhes,
                ip_address=log.ip_address,
                criado_em=log.criado_em,
            )
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
