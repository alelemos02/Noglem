from sqlalchemy import Column, String, DateTime, Boolean
from datetime import datetime
import uuid
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class InvitationCode(Base):
    __tablename__ = "invitation_codes"

    id = Column(String, primary_key=True, default=generate_uuid)
    code = Column(String, unique=True, index=True, nullable=False)
    is_used = Column(Boolean, default=False)
    used_by_email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
