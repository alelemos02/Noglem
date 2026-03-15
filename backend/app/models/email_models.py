from sqlalchemy import Column, String, DateTime, Integer, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class EmailAccountStatus(str, enum.Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    TOKEN_EXPIRED = "token_expired"


class EmailSyncStatus(str, enum.Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    COMPLETED = "completed"
    FAILED = "failed"


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, index=True, unique=True)
    microsoft_user_id = Column(String, nullable=True)
    email_address = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    status = Column(String, default=EmailAccountStatus.CONNECTED)
    collection_id = Column(String, ForeignKey("collections.id"), nullable=True)
    consent_accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("EmailMessage", back_populates="account", cascade="all, delete-orphan")


class EmailMessage(Base):
    __tablename__ = "email_messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    account_id = Column(String, ForeignKey("email_accounts.id"))
    microsoft_message_id = Column(String, index=True, unique=True)
    subject = Column(String, nullable=True)
    sender_name = Column(String, nullable=True)
    sender_email = Column(String, nullable=True)
    recipients = Column(Text, nullable=True)
    received_at = Column(DateTime, nullable=True)
    body_preview = Column(String, nullable=True)
    is_indexed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("EmailAccount", back_populates="messages")


class EmailSyncJob(Base):
    __tablename__ = "email_sync_jobs"

    id = Column(String, primary_key=True, default=generate_uuid)
    account_id = Column(String, ForeignKey("email_accounts.id"))
    status = Column(String, default=EmailSyncStatus.IDLE)
    period_months = Column(Integer, default=3)
    total_emails = Column(Integer, default=0)
    processed_emails = Column(Integer, default=0)
    indexed_emails = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
