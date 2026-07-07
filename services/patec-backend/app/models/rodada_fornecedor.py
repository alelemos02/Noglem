import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Os 4 tipos de resposta do fornecedor (bloco 21 do fluxo do caso técnico)
TIPO_PROPOSTA_REVISADA = "PROPOSTA_REVISADA"                        # Tipo 1
TIPO_RESPOSTA_ITENS = "RESPOSTA_ITENS"                              # Tipo 2
TIPO_RESPOSTA_ITENS_PROPOSTA_POSTERIOR = "RESPOSTA_ITENS_PROPOSTA_POSTERIOR"  # Tipo 3
TIPO_EMAIL_AVULSO = "EMAIL_AVULSO"                                  # Tipo 4

TIPOS_RODADA = {
    TIPO_PROPOSTA_REVISADA,
    TIPO_RESPOSTA_ITENS,
    TIPO_RESPOSTA_ITENS_PROPOSTA_POSTERIOR,
    TIPO_EMAIL_AVULSO,
}


class RodadaFornecedor(Base):
    """
    Resposta do fornecedor no nível do caso (bloco 22 do fluxo).

    Entidade da qual as avaliações por item (RodadaAvaliacao) descendem. O
    material entra por upload (documento_id) ou texto colado (tipo 4), a LLM
    sugere a vinculação aos itens abertos, e o engenheiro confirma (W3).
    """

    __tablename__ = "rodadas_fornecedor"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('PROPOSTA_REVISADA','RESPOSTA_ITENS',"
            "'RESPOSTA_ITENS_PROPOSTA_POSTERIOR','EMAIL_AVULSO')",
            name="ck_rodada_fornecedor_tipo",
        ),
        CheckConstraint(
            "status IN ('RECEBIDA','VINCULACAO_SUGERIDA','VINCULACAO_CONFIRMADA',"
            "'AVALIADA','ERRO')",
            name="ck_rodada_fornecedor_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parecer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pareceres.id", ondelete="CASCADE"), nullable=False, index=True
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    texto_colado: Mapped[str | None] = mapped_column(Text, nullable=True)
    documento_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documentos.id", ondelete="SET NULL"), nullable=True
    )
    proposta_final: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="RECEBIDA")
    erro_detalhe: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    parecer = relationship("Parecer", back_populates="rodadas_fornecedor")
    documento = relationship("Documento")
    avaliacoes = relationship(
        "RodadaAvaliacao",
        back_populates="rodada_fornecedor",
        order_by="RodadaAvaliacao.criado_em",
    )
