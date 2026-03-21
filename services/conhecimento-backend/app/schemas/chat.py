from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ChatMessageCreate(BaseModel):
    role: str = "user"
    content: str


class ChatMessageSchema(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionCreate(BaseModel):
    collection_id: str
    title: Optional[str] = None


class ChatSessionSchema(BaseModel):
    id: str
    collection_id: str
    title: Optional[str] = None
    created_at: datetime
    messages: list[ChatMessageSchema] = []

    class Config:
        from_attributes = True
