import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


class MensagemChatEmbedding(Base):
    __tablename__ = "mensagens_chat_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    mensagem_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mensagens_chat.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    parecer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pareceres.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    embedding = mapped_column(Vector(768) if Vector else Text, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    mensagem = relationship("MensagemChat")
    parecer = relationship("Parecer")
