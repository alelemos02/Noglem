import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ItemParecer(Base):
    __tablename__ = "itens_parecer"
    __table_args__ = (
        CheckConstraint("status IN ('A','B','C','D','E')", name="ck_status"),
        CheckConstraint("prioridade IN ('ALTA','MEDIA','BAIXA')", name="ck_prioridade"),
        CheckConstraint(
            "estado IN ('ABERTO','PENDENTE_FORNECEDOR','EM_REAVALIACAO',"
            "'ACEITO','REPROVADO','DESATIVADO')",
            name="ck_item_estado",
        ),
        CheckConstraint(
            "marcacao_revisao IN ('NOVO','ALTERADO') OR marcacao_revisao IS NULL",
            name="ck_item_marcacao_revisao",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parecer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pareceres.id", ondelete="CASCADE"), nullable=False
    )
    requisito_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requisitos.id", ondelete="SET NULL"), nullable=True, index=True
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
    estado: Mapped[str] = mapped_column(String(25), nullable=False, default="ABERTO")
    marcacao_revisao: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Verificacao cruzada (pos-cache): flag = motivo deterministico do gatilho;
    # nota = veredito/correcao do modelo Pro que revisou o item sinalizado.
    verificacao_flag: Mapped[str | None] = mapped_column(Text, nullable=True)
    verificacao_nota: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Flags internos de QA — NUNCA vao para o parecer exportado (ficam fora da
    # justificativa_tecnica). Exibidos so como badge interno na UI.
    # flag_consistencia: termo do requisito achado no fornecedor mas item nao-conforme.
    # nota_revisao: correcao do self-review (status alterado apos segunda IA).
    flag_consistencia: Mapped[str | None] = mapped_column(Text, nullable=True)
    nota_revisao: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    parecer = relationship("Parecer", back_populates="itens")
    requisito = relationship("Requisito", back_populates="itens")
    rodadas = relationship(
        "RodadaAvaliacao",
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="RodadaAvaliacao.numero_rodada",
    )
