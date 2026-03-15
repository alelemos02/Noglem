import uuid
from datetime import datetime

from sqlalchemy import String, BigInteger, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Documento(Base):
    __tablename__ = "documentos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parecer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pareceres.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    nome_arquivo: Mapped[str] = mapped_column(String(500), nullable=False)
    tipo_arquivo: Mapped[str] = mapped_column(String(10), nullable=False)
    tamanho_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    caminho_storage: Mapped[str] = mapped_column(String(500), nullable=False)
    texto_extraido: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    parecer = relationship("Parecer", back_populates="documentos")
