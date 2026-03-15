import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True
    )
    usuario_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    acao: Mapped[str] = mapped_column(String(50), nullable=False)
    recurso: Mapped[str] = mapped_column(String(50), nullable=False)
    recurso_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    detalhes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
