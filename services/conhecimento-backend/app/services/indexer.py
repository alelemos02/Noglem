"""Document indexing pipeline for Conhecimento RAG.

Orchestrates: extract text -> chunk text -> generate embeddings -> store in database.
Called automatically when documents are uploaded to a collection.
"""

import logging
import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentoChunk
from app.services.chunker import chunk_text
from app.services.embedding import embed_texts

logger = logging.getLogger(__name__)


async def index_document(
    document: Document,
    extracted_text: str,
    db: AsyncSession,
) -> int:
    """Chunk, embed, and store a document's text for RAG retrieval.

    Args:
        document: Document instance with metadata.
        extracted_text: The extracted text content.
        db: Async database session.

    Returns:
        Number of chunks created.
    """
    if not extracted_text or not extracted_text.strip():
        logger.warning("Document %s has no extracted text, skipping indexing", document.id)
        return 0

    # 1. Delete existing chunks for this document (handles re-uploads)
    await db.execute(
        delete(DocumentoChunk).where(DocumentoChunk.document_id == document.id)
    )

    # 2. Chunk the extracted text
    chunks = chunk_text(extracted_text)
    if not chunks:
        logger.warning("Document %s produced no chunks, skipping", document.id)
        return 0

    logger.info(
        "Indexing document %s (%s): %d chunks",
        document.id,
        document.filename,
        len(chunks),
    )

    # 3. Generate embeddings for all chunks
    texts = [c.conteudo for c in chunks]
    try:
        embeddings = await embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")
    except Exception:
        logger.exception(
            "Failed to generate embeddings for document %s, skipping indexing",
            document.id,
        )
        return 0

    if len(embeddings) != len(chunks):
        logger.error(
            "Embedding count mismatch: %d chunks vs %d embeddings for document %s",
            len(chunks),
            len(embeddings),
            document.id,
        )
        return 0

    # 4. Bulk insert chunks with embeddings
    chunk_objects = []
    for chunk, embedding in zip(chunks, embeddings):
        chunk_objects.append(
            DocumentoChunk(
                id=uuid.uuid4(),
                document_id=document.id,
                collection_id=document.collection_id,
                conteudo=chunk.conteudo,
                embedding=embedding,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                chunk_type=chunk.chunk_type,
                nome_arquivo=document.filename,
            )
        )

    db.add_all(chunk_objects)
    await db.flush()

    logger.info(
        "Indexed %d chunks for document %s (%s)",
        len(chunk_objects),
        document.id,
        document.filename,
    )

    return len(chunk_objects)
