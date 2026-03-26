from sqlalchemy import Column, String, DateTime, Text
from datetime import datetime
import uuid
from app.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class AdminNote(Base):
    __tablename__ = "admin_notes"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    category = Column(String, nullable=False, default="idea")  # bug, idea, improvement, todo
    tool_context = Column(String, nullable=True)  # qual ferramenta o admin estava usando
    is_resolved = Column(String, default="false")  # "true" / "false"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
