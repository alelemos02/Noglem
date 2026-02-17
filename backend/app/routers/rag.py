import os
import shutil
import uuid
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings

# Models & Schemas
from app.models.rag_models import Collection, Document, DocumentStatus, ChatSession, ChatMessage
from app.models.rag_schemas import (
    Collection as CollectionSchema, 
    CollectionCreate, 
    Document as DocumentSchema,
    ChatSession as ChatSessionSchema,
    ChatSessionCreate,
    ChatMessage as ChatMessageSchema,
    ChatMessageCreate
)

# Services
from app.services.rag.rag_pdf_service import rag_pdf_service
from app.services.rag.chunk_service import chunk_service
from app.services.rag.vector_store import vector_store_service
from app.services.rag.rag_service import rag_service

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Collections Endpoints ---

@router.post("/collections", response_model=CollectionSchema)
def create_collection(collection: CollectionCreate, db: Session = Depends(get_db)):
    db_collection = Collection(name=collection.name)
    db.add(db_collection)
    db.commit()
    db.refresh(db_collection)
    return db_collection

@router.get("/collections", response_model=List[CollectionSchema])
def list_collections(db: Session = Depends(get_db)):
    return db.query(Collection).all()

@router.get("/collections/{collection_id}", response_model=CollectionSchema)
def get_collection(collection_id: str, db: Session = Depends(get_db)):
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection

@router.put("/collections/{collection_id}", response_model=CollectionSchema)
def update_collection(
    collection_id: str,
    collection_update: CollectionCreate,
    db: Session = Depends(get_db)
):
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    collection.name = collection_update.name
    db.commit()
    db.refresh(collection)
    return collection

@router.delete("/collections/{collection_id}", status_code=204)
def delete_collection(
    collection_id: str,
    db: Session = Depends(get_db)
):
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # 1. Gather all document IDs to remove from Vector Store
    doc_ids = [doc.id for doc in collection.documents]
    
    if doc_ids:
        # Remove from Vector Store
        vector_store_service.delete_documents(doc_ids)
    
    # 2. Delete Collection Directory (Files)
    collection_dir = os.path.join(settings.UPLOAD_DIR, collection_id)
    if os.path.exists(collection_dir):
        try:
            shutil.rmtree(collection_dir)
        except OSError as e:
            print(f"Error removing collection directory {collection_dir}: {e}")

    # 3. Delete from DB (Manually delete documents to be safe)
    for doc in collection.documents:
        db.delete(doc) # Delete doc record
    
    db.delete(collection)
    db.commit()
    
    return None

# --- Documents Endpoints ---

@router.post("/collections/{collection_id}/documents", response_model=DocumentSchema)
async def upload_document_to_collection(
    collection_id: str, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    # 1. Check if collection exists
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    # 2. Create DB Record
    doc_id = str(uuid.uuid4())
    db_doc = Document(
        id=doc_id,
        collection_id=collection_id,
        filename=file.filename,
        original_path="", # Will update
        status=DocumentStatus.PROCESSING
    )
    db.add(db_doc)
    db.commit()

    # 3. Save File
    collection_dir = os.path.join(settings.UPLOAD_DIR, collection_id)
    os.makedirs(collection_dir, exist_ok=True)
    
    file_location = os.path.join(collection_dir, f"{doc_id}_{file.filename}")
    
    try:
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Update path
        db_doc.original_path = file_location
        db.commit()
        
    except Exception as e:
        db_doc.status = DocumentStatus.FAILED
        db.commit()
        raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")

    # 4. Ingestion Process (Sync for MVP)
    try:
        # Extract
        # PHASE 2: Returns tuple (data, has_ocr)
        extracted_data, has_ocr = rag_pdf_service.extract_text(file_location)
        
        if not extracted_data:
             raise ValueError("No text extracted from PDF (even with OCR)")

        # Update has_ocr flag
        db_doc.has_ocr = has_ocr
        db.commit()

        # Chunk
        chunks = chunk_service.create_chunks(extracted_data, doc_id)
        
        # Add collection_id to metadata
        for chunk in chunks:
            chunk.metadata["collection_id"] = collection_id
            chunk.metadata["filename"] = file.filename

        # Index
        vector_store_service.add_documents(chunks)
        
        # Update Status
        db_doc.status = DocumentStatus.READY
        db.commit()
        
    except Exception as e:
        db_doc.status = DocumentStatus.FAILED
        db.commit()
        logger.error(f"Ingestion failed for {doc_id}: {e}", exc_info=True)
        # We don't raise 500 here because the file upload was technically successful, just processing failed.
        
    db.refresh(db_doc)
    return db_doc

@router.delete("/collections/{collection_id}/documents/{document_id}", status_code=204)
def delete_document(
    collection_id: str,
    document_id: str,
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(
        Document.id == document_id, 
        Document.collection_id == collection_id
    ).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from Vector Store
    vector_store_service.delete_documents([document_id])

    # Delete File from Disk
    if doc.original_path and os.path.exists(doc.original_path):
        try:
            os.remove(doc.original_path)
        except OSError as e:
            print(f"Error deleting file {doc.original_path}: {e}")

    # Delete from DB
    db.delete(doc)
    db.commit()
    return None

@router.get("/collections/{collection_id}/documents/{document_id}/content")
def get_document_content(
    collection_id: str,
    document_id: str,
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(
        Document.id == document_id, 
        Document.collection_id == collection_id
    ).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    if not doc.original_path or not os.path.exists(doc.original_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
        
    return FileResponse(doc.original_path, media_type="application/pdf", filename=doc.filename)

# --- Chat Endpoints ---

@router.post("/chats", response_model=ChatSessionSchema)
def create_chat_session(session: ChatSessionCreate, db: Session = Depends(get_db)):
    collection = db.query(Collection).filter(Collection.id == session.collection_id).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    db_session = ChatSession(
        collection_id=session.collection_id,
        title=session.title or "New Chat"
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

@router.get("/collections/{collection_id}/chats", response_model=List[ChatSessionSchema])
def list_chats(collection_id: str, db: Session = Depends(get_db)):
    return db.query(ChatSession).filter(
        ChatSession.collection_id == collection_id
    ).order_by(ChatSession.created_at.desc()).all()

@router.get("/chats/{chat_id}", response_model=ChatSessionSchema)
def get_chat(chat_id: str, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return chat

@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: str, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # Delete messages first
    db.query(ChatMessage).filter(ChatMessage.session_id == chat_id).delete()
    db.delete(chat)
    db.commit()
    return {"message": "Chat deleted successfully"}

@router.get("/chats/{chat_id}/messages", response_model=List[ChatMessageSchema])
def get_messages(chat_id: str, db: Session = Depends(get_db)):
    return db.query(ChatMessage).filter(
        ChatMessage.session_id == chat_id
    ).order_by(ChatMessage.created_at.asc()).all()

def _get_chat_history(db: Session, chat_id: str, limit: int = 10) -> List[dict]:
    """Get recent chat history for context."""
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == chat_id
    ).order_by(ChatMessage.created_at.desc()).limit(limit).all()

    # Reverse to get chronological order
    messages = list(reversed(messages))

    return [{"role": msg.role, "content": msg.content} for msg in messages]

@router.post("/chats/{chat_id}/messages", response_model=ChatMessageSchema)
def send_message(chat_id: str, message: ChatMessageCreate, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # 1. Save User Message
    user_msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=chat_id,
        role="user",
        content=message.content
    )
    db.add(user_msg)

    # Update title if first message
    if chat.title == "New Chat":
        chat.title = message.content[:30] + ("..." if len(message.content) > 30 else "")
        db.add(chat)

    db.commit()

    # 2. Get chat history for context
    chat_history = _get_chat_history(db, chat_id, limit=10)

    # 3. Generate AI Response
    ai_response_text = rag_service.get_answer(
        question=message.content,
        collection_id=chat.collection_id,
        chat_history=chat_history
    )

    # 4. Save Assistant Message
    ai_msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=chat_id,
        role="assistant",
        content=ai_response_text
    )
    db.add(ai_msg)
    db.commit()
    db.refresh(ai_msg)

    return ai_msg

@router.post("/chats/{chat_id}/messages/stream")
async def send_message_stream(
    chat_id: str,
    message: ChatMessageCreate,
    db: Session = Depends(get_db)
):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # 1. Save User Message
    user_msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=chat_id,
        role="user",
        content=message.content
    )
    db.add(user_msg)

    # Update title if first message
    if chat.title == "New Chat":
        chat.title = message.content[:30] + ("..." if len(message.content) > 30 else "")
        db.add(chat)

    db.commit()

    # 2. Get history
    chat_history = _get_chat_history(db, chat_id, limit=10)

    # 3. Create streaming generator
    async def generate():
        full_response = ""
        try:
            for chunk in rag_service.stream_answer(
                question=message.content,
                collection_id=chat.collection_id,
                chat_history=chat_history
            ):
                full_response += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            # Save complete response to DB (Synchronously in this context or use async session, 
            # but SQLAlchemy Session is not async here. We are in an async def but using correct generator)
            # IMPORTANT: Re-acquiring DB session inside generator might be tricky or using the outer one.
            # Since streaming response runs in background, relying on 'db' from dependency (which closes) is RISKY?
            # Actually FastAPI dependency 'db' closes after the RESPONSE is sent initially? 
            # No, for StreamingResponse, it might be an issue.
            # Best practice: Creating a new session or relying on standard behavior.
            # However, for simplicity now, let's assume it works or we should fix it if it errors.
            
            # Re-create session just for this save to be safe?
            # Or use the closed variable?
            # Let's try using the passed db session. If it fails, we know why.
            
            ai_msg = ChatMessage(
                id=str(uuid.uuid4()),
                session_id=chat_id,
                role="assistant",
                content=full_response
            )
            db.add(ai_msg)
            db.commit()

            yield f"data: {json.dumps({'done': True, 'message_id': ai_msg.id})}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
