import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RevisaoParecer(Base):
    __tablename__ = "revisoes_parecer"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parecer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pareceres.id", ondelete="CASCADE"), nullable=False
    )
    numero_revisao: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    criado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True
    )

    # Snapshot of parecer state at this revision
    parecer_geral: Mapped[str | None] = mapped_column(String(30), nullable=True)
    comentario_geral: Mapped[str | None] = mapped_column(Text, nullable=True)
    conclusao: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_itens: Mapped[int] = mapped_column(Integer, default=0)
    total_aprovados: Mapped[int] = mapped_column(Integer, default=0)
    total_aprovados_comentarios: Mapped[int] = mapped_column(Integer, default=0)
    total_rejeitados: Mapped[int] = mapped_column(Integer, default=0)
    total_info_ausente: Mapped[int] = mapped_column(Integer, default=0)
    total_itens_adicionais: Mapped[int] = mapped_column(Integer, default=0)

    # Full snapshot of items and recommendations as JSON
    itens_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recomendacoes_snapshot: Mapped[list | None] = mapped_column(JSON, nullable=True)

    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    parecer = relationship("Parecer", back_populates="revisoes")
