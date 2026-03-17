import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    # Fallback for environments without pgvector installed
    Vector = None


class DocumentoChunk(Base):
    __tablename__ = "documento_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    documento_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documentos.id", ondelete="CASCADE"), nullable=False
    )
    parecer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pareceres.id", ondelete="CASCADE"), nullable=False
    )
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(3072) if Vector else Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_type: Mapped[str] = mapped_column(String(20), default="text")
    nome_arquivo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tipo_documento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    documento = relationship("Documento")
    parecer = relationship("Parecer")
