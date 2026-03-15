import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CacheAnalise(Base):
    __tablename__ = "cache_analises"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    hash_documentos: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    resultado: Mapped[dict] = mapped_column(JSON, nullable=False)
    total_tokens_entrada: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens_saida: Mapped[int | None] = mapped_column(Integer, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
