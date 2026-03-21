from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.schemas.document import DocumentSchema


class CollectionCreate(BaseModel):
    name: str


class CollectionSchema(BaseModel):
    id: str
    name: str
    created_at: datetime
    documents: list[DocumentSchema] = []

    class Config:
        from_attributes = True
