import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Parecer(Base):
    __tablename__ = "pareceres"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    numero_parecer: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    projeto: Mapped[str] = mapped_column(String(200), nullable=False)
    fornecedor: Mapped[str] = mapped_column(String(200), nullable=False)
    revisao: Mapped[str] = mapped_column(String(10), default="0")
    status_processamento: Mapped[str] = mapped_column(String(20), default="pendente")
    parecer_geral: Mapped[str | None] = mapped_column(String(30), nullable=True)
    comentario_geral: Mapped[str | None] = mapped_column(Text, nullable=True)
    conclusao: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_itens: Mapped[int] = mapped_column(Integer, default=0)
    total_aprovados: Mapped[int] = mapped_column(Integer, default=0)
    total_aprovados_comentarios: Mapped[int] = mapped_column(Integer, default=0)
    total_rejeitados: Mapped[int] = mapped_column(Integer, default=0)
    total_info_ausente: Mapped[int] = mapped_column(Integer, default=0)
    total_itens_adicionais: Mapped[int] = mapped_column(Integer, default=0)
    criado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    documentos = relationship("Documento", back_populates="parecer", cascade="all, delete-orphan")
    itens = relationship("ItemParecer", back_populates="parecer", cascade="all, delete-orphan")
    recomendacoes = relationship(
        "Recomendacao", back_populates="parecer", cascade="all, delete-orphan"
    )
    revisoes = relationship(
        "RevisaoParecer", back_populates="parecer", cascade="all, delete-orphan",
        order_by="RevisaoParecer.numero_revisao.desc()",
    )
    mensagens_chat = relationship(
        "MensagemChat", back_populates="parecer", cascade="all, delete-orphan",
        order_by="MensagemChat.ordem",
    )
