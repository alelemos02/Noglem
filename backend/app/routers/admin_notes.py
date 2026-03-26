from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.models.admin_notes_models import AdminNote
from app.config import settings

router = APIRouter()


# --- Schemas ---

class AdminNoteCreate(BaseModel):
    title: str
    content: Optional[str] = None
    category: str = "idea"
    tool_context: Optional[str] = None


class AdminNoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    is_resolved: Optional[str] = None


class AdminNoteSchema(BaseModel):
    id: str
    title: str
    content: Optional[str]
    category: str
    tool_context: Optional[str]
    is_resolved: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Auth ---

def verify_admin(x_api_key: str = Header(...)):
    if x_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )


# --- Endpoints ---

@router.get("/", response_model=List[AdminNoteSchema])
def list_notes(
    category: Optional[str] = None,
    resolved: Optional[str] = None,
    db: Session = Depends(get_db),
    _admin=Depends(verify_admin),
):
    query = db.query(AdminNote)
    if category:
        query = query.filter(AdminNote.category == category)
    if resolved is not None:
        query = query.filter(AdminNote.is_resolved == resolved)
    return query.order_by(AdminNote.created_at.desc()).all()


@router.post("/", response_model=AdminNoteSchema)
def create_note(
    data: AdminNoteCreate,
    db: Session = Depends(get_db),
    _admin=Depends(verify_admin),
):
    note = AdminNote(
        title=data.title,
        content=data.content,
        category=data.category,
        tool_context=data.tool_context,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.patch("/{note_id}", response_model=AdminNoteSchema)
def update_note(
    note_id: str,
    data: AdminNoteUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(verify_admin),
):
    note = db.query(AdminNote).filter(AdminNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Nota não encontrada")

    if data.title is not None:
        note.title = data.title
    if data.content is not None:
        note.content = data.content
    if data.category is not None:
        note.category = data.category
    if data.is_resolved is not None:
        note.is_resolved = data.is_resolved

    note.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{note_id}")
def delete_note(
    note_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(verify_admin),
):
    note = db.query(AdminNote).filter(AdminNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Nota não encontrada")

    db.delete(note)
    db.commit()
    return {"success": True}
