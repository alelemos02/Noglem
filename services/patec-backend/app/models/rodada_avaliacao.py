import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RodadaAvaliacao(Base):
    __tablename__ = "rodadas_avaliacao"
    __table_args__ = (
        CheckConstraint(
            "origem IN ('PROPOSTA_INICIAL','RESPOSTA_FORNECEDOR','COMENTARIO_ENGENHARIA')",
            name="ck_rodada_origem",
        ),
        CheckConstraint(
            "classificacao_ia IN ('A','B','C','D','E') OR classificacao_ia IS NULL",
            name="ck_rodada_classificacao_ia",
        ),
        CheckConstraint(
            "veredito_ia IN ('ATENDE','PARCIAL','NAO_ATENDE') OR veredito_ia IS NULL",
            name="ck_rodada_veredito_ia",
        ),
        CheckConstraint(
            "decisao_humana IN ('ATENDE','PARCIAL','NAO_ATENDE') OR decisao_humana IS NULL",
            name="ck_rodada_decisao_humana",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itens_parecer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    numero_rodada: Mapped[int] = mapped_column(Integer, nullable=False)
    origem: Mapped[str] = mapped_column(String(30), nullable=False)
    conteudo: Mapped[str | None] = mapped_column(Text, nullable=True)
    anexo_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    classificacao_ia: Mapped[str | None] = mapped_column(String(1), nullable=True)
    veredito_ia: Mapped[str | None] = mapped_column(String(15), nullable=True)
    justificativa_ia: Mapped[str | None] = mapped_column(Text, nullable=True)
    acao_requerida: Mapped[str | None] = mapped_column(Text, nullable=True)
    decisao_humana: Mapped[str | None] = mapped_column(String(15), nullable=True)
    revisor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    item = relationship("ItemParecer", back_populates="rodadas")
