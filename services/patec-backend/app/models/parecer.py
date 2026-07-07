import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Parecer(Base):
    __tablename__ = "pareceres"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    numero_parecer: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    projeto: Mapped[str] = mapped_column(String(200), nullable=False)
    fornecedor: Mapped[str] = mapped_column(String(200), nullable=False)
    revisao: Mapped[str] = mapped_column(String(10), default="0")
    disciplina: Mapped[str] = mapped_column(String(30), nullable=False, default="instrumentacao")
    idioma_relatorio: Mapped[str] = mapped_column(String(10), nullable=False, default="pt")
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
    fase_caso: Mapped[str] = mapped_column(String(30), nullable=False, default="SETUP")
    desfecho: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fechado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fechado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True
    )
    motivo_fechamento: Mapped[str | None] = mapped_column(Text, nullable=True)
    revisao_spec_em_andamento: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # Setup: o usuário já resolveu os documentos complementares da engenharia
    # (anexou referências/normas OU declarou que não tem). Gate conversacional
    # entre o documento principal e a proposta do fornecedor.
    complementares_resolvidos: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    criado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    documentos = relationship("Documento", back_populates="parecer", cascade="all, delete-orphan")
    itens = relationship("ItemParecer", back_populates="parecer", cascade="all, delete-orphan")
    requisitos = relationship(
        "Requisito", back_populates="parecer", cascade="all, delete-orphan",
        order_by="Requisito.numero",
    )
    rodadas_fornecedor = relationship(
        "RodadaFornecedor", back_populates="parecer", cascade="all, delete-orphan",
        order_by="RodadaFornecedor.numero",
    )
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
