import os
import shutil
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_internal_api_key
from app.core.config import settings
from app.models.collection import Collection
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentoChunk
from app.services.text_extractor import extract_text
from app.services.indexer import index_document
from app.schemas.document import DocumentSchema

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_internal_api_key)])

# Supported file types and their MIME mappings
ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
}


@router.post("/collections/{collection_id}/documents", response_model=DocumentSchema)
async def upload_document(
    collection_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # 1. Check if collection exists
    result = await db.execute(
        select(Collection).where(Collection.id == collection_id)
    )
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # 2. Validate file type
    content_type = file.content_type or ""
    file_type = ALLOWED_TYPES.get(content_type)

    # Fallback: check extension
    if not file_type and file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext in ("pdf", "docx", "xlsx"):
            file_type = ext

    if not file_type:
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, and XLSX files are allowed.")

    # 3. Create DB record
    doc_id = str(uuid.uuid4())
    collection_dir = os.path.join(settings.UPLOAD_DIR, collection_id)
    os.makedirs(collection_dir, exist_ok=True)
    file_location = os.path.join(collection_dir, f"{doc_id}_{file.filename}")

    db_doc = Document(
        id=doc_id,
        collection_id=collection_id,
        filename=file.filename,
        file_type=file_type,
        storage_path=file_location,
        status=DocumentStatus.PROCESSING,
    )
    db.add(db_doc)
    await db.commit()

    # 4. Save file to disk
    try:
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        db_doc.file_size_bytes = os.path.getsize(file_location)
        await db.commit()
    except Exception as e:
        db_doc.status = DocumentStatus.FAILED
        db_doc.error_message = f"Could not save file: {str(e)}"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")

    # 5. Extract text, chunk, and index
    try:
        extracted_text, has_ocr = extract_text(file_location, file_type)

        if not extracted_text or not extracted_text.strip():
            raise ValueError("No text extracted from file (even with OCR)")

        db_doc.has_ocr = has_ocr
        await db.commit()

        # Index document (chunk + embed + store in pgvector)
        num_chunks = await index_document(db_doc, extracted_text, db)

        db_doc.status = DocumentStatus.READY
        await db.commit()

        logger.info(
            "Document %s indexed: %d chunks (has_ocr=%s)",
            doc_id, num_chunks, has_ocr,
        )

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        db_doc.status = DocumentStatus.FAILED
        db_doc.error_message = error_msg
        await db.commit()
        logger.error("Ingestion failed for %s: %s", doc_id, error_msg, exc_info=True)

    await db.refresh(db_doc)
    return db_doc


@router.delete("/collections/{collection_id}/documents/{document_id}", status_code=204)
async def delete_document(
    collection_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.collection_id == collection_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete chunks from pgvector
    await db.execute(
        delete(DocumentoChunk).where(DocumentoChunk.document_id == document_id)
    )

    # Delete file from disk
    if doc.storage_path and os.path.exists(doc.storage_path):
        try:
            os.remove(doc.storage_path)
        except OSError as e:
            logger.warning("Error deleting file %s: %s", doc.storage_path, e)

    await db.delete(doc)
    await db.commit()
    return None


@router.get("/collections/{collection_id}/documents/{document_id}/content")
async def get_document_content(
    collection_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.collection_id == collection_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not doc.storage_path or not os.path.exists(doc.storage_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    media_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    return FileResponse(
        doc.storage_path,
        media_type=media_types.get(doc.file_type, "application/octet-stream"),
        filename=doc.filename,
    )
