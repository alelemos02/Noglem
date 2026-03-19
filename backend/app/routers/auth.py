import random
import string
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.models.auth_models import InvitationCode
from app.config import settings

router = APIRouter()

class InvitationCodeCreate(BaseModel):
    expires_at: Optional[datetime] = None

class InvitationCodeSchema(BaseModel):
    code: str
    is_used: bool
    created_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True

def generate_random_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def verify_admin(x_api_key: str = Header(...)):
    if x_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )

@router.post("/generate", response_model=InvitationCodeSchema)
def generate_code(data: InvitationCodeCreate, db: Session = Depends(get_db), _admin = Depends(verify_admin)):
    code = generate_random_code()
    # Ensure uniqueness
    while db.query(InvitationCode).filter(InvitationCode.code == code).first():
        code = generate_random_code()
    
    new_invite = InvitationCode(
        code=code,
        expires_at=data.expires_at
    )
    db.add(new_invite)
    db.commit()
    db.refresh(new_invite)
    return new_invite

@router.get("/list", response_model=List[InvitationCodeSchema])
def list_codes(db: Session = Depends(get_db), _admin = Depends(verify_admin)):
    return db.query(InvitationCode).all()

@router.get("/validate/{code}")
def validate_code(code: str, db: Session = Depends(get_db)):
    invite = db.query(InvitationCode).filter(InvitationCode.code == code).first()
    
    if not invite:
        raise HTTPException(status_code=404, detail="Código inválido")
    
    if invite.is_used:
        raise HTTPException(status_code=400, detail="Este código já foi utilizado")
    
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Este código expirou")
    
    return {"valid": True, "code": code}

@router.post("/use/{code}")
def use_code(code: str, email: Optional[str] = None, db: Session = Depends(get_db), _admin = Depends(verify_admin)):
    invite = db.query(InvitationCode).filter(InvitationCode.code == code).first()
    
    if not invite:
        raise HTTPException(status_code=404, detail="Código inválido")
    
    if invite.is_used:
        raise HTTPException(status_code=400, detail="Este código já foi utilizado")
    
    invite.is_used = True
    invite.used_by_email = email
    db.commit()
    
    return {"success": True}
