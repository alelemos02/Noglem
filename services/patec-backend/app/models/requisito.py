import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Requisito(Base):
    """
    Requisito de engenharia aprovado pelo engenheiro (operação W1).

    Fonte única de verdade do que a engenharia exige. Criado na aprovação da
    lista extraída pela LLM; mutável apenas via revisão de especificação (W7).
    Requisitos removidos são desativados (ativo=False), nunca apagados.
    """

    __tablename__ = "requisitos"
    __table_args__ = (
        CheckConstraint(
            "prioridade IN ('ALTA','MEDIA','BAIXA') OR prioridade IS NULL",
            name="ck_requisito_prioridade",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parecer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pareceres.id", ondelete="CASCADE"), nullable=False, index=True
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    categoria: Mapped[str | None] = mapped_column(String(100), nullable=True)
    descricao_requisito: Mapped[str] = mapped_column(Text, nullable=False)
    referencia_engenharia: Mapped[str | None] = mapped_column(String(500), nullable=True)
    valor_requerido: Mapped[str | None] = mapped_column(Text, nullable=True)
    prioridade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    norma_referencia: Mapped[str | None] = mapped_column(String(200), nullable=True)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    desativado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    desativado_motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    origem_versao_spec_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("versoes_especificacao.id", ondelete="SET NULL"), nullable=True
    )
    alterado_versao_spec_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("versoes_especificacao.id", ondelete="SET NULL"), nullable=True
    )
    aprovado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True
    )
    aprovado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    parecer = relationship("Parecer", back_populates="requisitos")
    itens = relationship("ItemParecer", back_populates="requisito")
