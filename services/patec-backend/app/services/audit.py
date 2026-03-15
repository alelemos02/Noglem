import logging

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.usuario import Usuario

logger = logging.getLogger(__name__)


async def registrar_auditoria(
    db: AsyncSession,
    usuario: Usuario | None,
    acao: str,
    recurso: str,
    recurso_id: str | None = None,
    detalhes: str | None = None,
    request: Request | None = None,
):
    """Register an audit log entry."""
    ip_address = None
    if request:
        ip_address = request.client.host if request.client else None

    log = AuditLog(
        usuario_id=usuario.id if usuario else None,
        usuario_email=usuario.email if usuario else None,
        acao=acao,
        recurso=recurso,
        recurso_id=recurso_id,
        detalhes=detalhes,
        ip_address=ip_address,
    )
    db.add(log)
    await db.flush()
    logger.info(
        "Audit: %s %s %s by %s",
        acao, recurso, recurso_id or "", usuario.email if usuario else "system",
    )
