import os
import shutil
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import require_internal_api_key
from app.core.config import settings
from app.models.collection import Collection
from app.models.document_chunk import DocumentoChunk
from app.schemas.collection import CollectionCreate, CollectionSchema

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_internal_api_key)])


@router.post("/collections", response_model=CollectionSchema)
async def create_collection(
    collection: CollectionCreate,
    db: AsyncSession = Depends(get_db),
):
    db_collection = Collection(name=collection.name)
    db.add(db_collection)
    await db.commit()
    await db.refresh(db_collection, attribute_names=["documents"])
    return db_collection


@router.get("/collections", response_model=list[CollectionSchema])
async def list_collections(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Collection).options(selectinload(Collection.documents))
    )
    return result.scalars().all()


@router.get("/collections/{collection_id}", response_model=CollectionSchema)
async def get_collection(
    collection_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Collection)
        .where(Collection.id == collection_id)
        .options(selectinload(Collection.documents))
    )
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


@router.put("/collections/{collection_id}", response_model=CollectionSchema)
async def update_collection(
    collection_id: str,
    collection_update: CollectionCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Collection)
        .where(Collection.id == collection_id)
        .options(selectinload(Collection.documents))
    )
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    collection.name = collection_update.name
    await db.commit()
    await db.refresh(collection, attribute_names=["documents"])
    return collection


@router.delete("/collections/{collection_id}", status_code=204)
async def delete_collection(
    collection_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Collection).where(Collection.id == collection_id)
    )
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Delete files from disk
    collection_dir = os.path.join(settings.UPLOAD_DIR, collection_id)
    if os.path.exists(collection_dir):
        try:
            shutil.rmtree(collection_dir)
        except OSError as e:
            logger.warning("Error removing collection directory %s: %s", collection_dir, e)

    # Cascade delete handles documents, chunks, chats, and messages
    await db.delete(collection)
    await db.commit()
    return None
