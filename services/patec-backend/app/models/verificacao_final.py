import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class VerificacaoFinal(Base):
    """
    Verificação final do caso (blocos 29-33 do fluxo, operações R3/W5).

    Bifurcação do bloco 29: se a última resposta decidida veio do Tipo 1
    (proposta totalmente revisada), a verificação LLM é dispensada
    (ia_dispensada=True) — a proposta já foi analisada nas rodadas. Caso
    contrário, aguarda a proposta revisada final e a LLM verifica contra os
    acordos do BD central (R3). O resultado só vale após validação humana (W5).
    """

    __tablename__ = "verificacoes_finais"
    __table_args__ = (
        CheckConstraint(
            "resultado_validado IN ('CONFORME','CONFORME_COM_PENDENCIA','NAO_CONFORME') "
            "OR resultado_validado IS NULL",
            name="ck_verificacao_resultado_validado",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parecer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pareceres.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    rodada_fornecedor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rodadas_fornecedor.id", ondelete="SET NULL"), nullable=True
    )
    ia_dispensada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDENTE")
    resultado_ia: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resultado_validado: Mapped[str | None] = mapped_column(String(30), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    validado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True
    )
    validado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    parecer = relationship("Parecer")
    rodada_fornecedor = relationship("RodadaFornecedor")
