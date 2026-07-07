import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class VersaoEspecificacao(Base):
    """
    Revisão da especificação de engenharia (caminho lateral, blocos 35-41).

    O engenheiro sobe a nova revisão do documento; a LLM compara contra os
    requisitos ativos do BD central (R4) e classifica o cenário:
      A — nada mudou (fluxo retorna ao ponto onde estava)
      B — só itens novos (engenheiro decide a inclusão, bloco 40)
      C — itens alterados (atualização forçada: alterações invalidam decisões)

    `resumo_diff` guarda o antes/depois por requisito — é o registro histórico
    da mudança. A aplicação (W7) reabre itens alterados, desativa removidos e
    inclui novos, sempre preservando o histórico.
    """

    __tablename__ = "versoes_especificacao"
    __table_args__ = (
        CheckConstraint(
            "cenario IN ('A','B','C') OR cenario IS NULL",
            name="ck_versao_spec_cenario",
        ),
        CheckConstraint(
            "status IN ('EM_COMPARACAO','AGUARDANDO_DECISAO','APLICADA','DESCARTADA','ERRO')",
            name="ck_versao_spec_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parecer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pareceres.id", ondelete="CASCADE"), nullable=False, index=True
    )
    numero_versao: Mapped[int] = mapped_column(Integer, nullable=False)
    documento_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documentos.id", ondelete="SET NULL"), nullable=True
    )
    resumo_diff: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cenario: Mapped[str | None] = mapped_column(String(1), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="EM_COMPARACAO")
    erro_detalhe: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fase_caso_anterior: Mapped[str | None] = mapped_column(String(30), nullable=True)
    aplicado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True
    )
    aplicado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    parecer = relationship("Parecer")
    documento = relationship("Documento")
