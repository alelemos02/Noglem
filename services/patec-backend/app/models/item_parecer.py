import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Text, Boolean, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ItemParecer(Base):
    __tablename__ = "itens_parecer"
    __table_args__ = (
        CheckConstraint("status IN ('A','B','C','D','E')", name="ck_status"),
        CheckConstraint("prioridade IN ('ALTA','MEDIA','BAIXA')", name="ck_prioridade"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parecer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pareceres.id", ondelete="CASCADE"), nullable=False
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    categoria: Mapped[str | None] = mapped_column(String(100), nullable=True)
    descricao_requisito: Mapped[str] = mapped_column(Text, nullable=False)
    referencia_engenharia: Mapped[str | None] = mapped_column(String(500), nullable=True)
    referencia_fornecedor: Mapped[str | None] = mapped_column(String(500), nullable=True)
    valor_requerido: Mapped[str | None] = mapped_column(Text, nullable=True)
    valor_fornecedor: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(1), nullable=False)
    justificativa_tecnica: Mapped[str] = mapped_column(Text, nullable=False)
    acao_requerida: Mapped[str | None] = mapped_column(Text, nullable=True)
    prioridade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    norma_referencia: Mapped[str | None] = mapped_column(String(200), nullable=True)
    editado_manualmente: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    parecer = relationship("Parecer", back_populates="itens")
