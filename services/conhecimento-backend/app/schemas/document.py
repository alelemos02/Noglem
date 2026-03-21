from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class DocumentSchema(BaseModel):
    id: str
    collection_id: str
    filename: str
    status: DocumentStatus
    has_ocr: bool
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
