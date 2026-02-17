from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum

class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"

class DocumentBase(BaseModel):
    filename: str

class Document(DocumentBase):
    id: str
    collection_id: str
    status: DocumentStatus
    has_ocr: bool
    created_at: datetime

    class Config:
        from_attributes = True

class CollectionBase(BaseModel):
    name: str

class CollectionCreate(CollectionBase):
    pass

class Collection(BaseModel):
    id: str
    name: str
    created_at: datetime
    documents: List[Document] = []

    class Config:
        from_attributes = True

# Chat Schemas
class ChatMessageBase(BaseModel):
    role: str
    content: str

class ChatMessageCreate(ChatMessageBase):
    pass

class ChatMessage(ChatMessageBase):
    id: str
    session_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChatSessionBase(BaseModel):
    title: Optional[str] = None

class ChatSessionCreate(ChatSessionBase):
    collection_id: str

class ChatSession(ChatSessionBase):
    id: str
    collection_id: str
    created_at: datetime
    messages: List[ChatMessage] = []

    class Config:
        from_attributes = True
