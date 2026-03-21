import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


class DocumentoChunk(Base):
    __tablename__ = "con_document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("con_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    collection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("con_collections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(768) if Vector else Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_type: Mapped[str] = mapped_column(String(20), default="text")
    nome_arquivo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
