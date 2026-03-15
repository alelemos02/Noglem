import uuid

from sqlalchemy import Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Recomendacao(Base):
    __tablename__ = "recomendacoes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parecer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pareceres.id", ondelete="CASCADE"), nullable=False
    )
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)

    parecer = relationship("Parecer", back_populates="recomendacoes")
