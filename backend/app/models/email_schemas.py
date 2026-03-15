from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# --- Request Schemas ---

class EmailSyncRequest(BaseModel):
    period_months: int = 3


class EmailConsentRequest(BaseModel):
    accepted: bool = True


class EmailChatCreateRequest(BaseModel):
    title: Optional[str] = None


class EmailChatMessageRequest(BaseModel):
    content: str


# --- Response Schemas ---

class EmailAccountResponse(BaseModel):
    id: str
    email_address: Optional[str]
    display_name: Optional[str]
    status: str
    collection_id: Optional[str]
    consent_accepted_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class EmailSyncJobResponse(BaseModel):
    id: str
    status: str
    period_months: int
    total_emails: int
    processed_emails: int
    indexed_emails: int
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class EmailStatsResponse(BaseModel):
    total_emails: int
    indexed_emails: int
    last_sync: Optional[datetime]
    collection_id: Optional[str]


class OAuthUrlResponse(BaseModel):
    auth_url: str
