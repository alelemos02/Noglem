"""Document indexing pipeline for PATEC RAG.

Orchestrates: chunk text -> generate embeddings -> store in database.
Called automatically when documents are uploaded.
"""

import logging
import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documento import Documento
from app.models.documento_chunk import DocumentoChunk
from app.services.chunker import chunk_text
from app.services.embedding import embed_texts

logger = logging.getLogger(__name__)


async def index_document(documento: Documento, db: AsyncSession) -> int:
    """Chunk, embed, and store a document's text for RAG retrieval.

    Args:
        documento: Documento instance with texto_extraido populated.
        db: Async database session.

    Returns:
        Number of chunks created.
    """
    if not documento.texto_extraido or not documento.texto_extraido.strip():
        logger.warning("Documento %s has no extracted text, skipping indexing", documento.id)
        return 0

    # 1. Delete existing chunks for this document (handles re-uploads)
    await db.execute(
        delete(DocumentoChunk).where(DocumentoChunk.documento_id == documento.id)
    )

    # 2. Chunk the extracted text
    chunks = chunk_text(documento.texto_extraido)
    if not chunks:
        logger.warning("Documento %s produced no chunks, skipping", documento.id)
        return 0

    logger.info(
        "Indexing documento %s (%s): %d chunks",
        documento.id,
        documento.nome_arquivo,
        len(chunks),
    )

    # 3. Generate embeddings for all chunks
    texts = [c.conteudo for c in chunks]
    try:
        embeddings = await embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")
    except Exception:
        logger.exception(
            "Failed to generate embeddings for documento %s, skipping indexing",
            documento.id,
        )
        return 0

    if len(embeddings) != len(chunks):
        logger.error(
            "Embedding count mismatch: %d chunks vs %d embeddings for documento %s",
            len(chunks),
            len(embeddings),
            documento.id,
        )
        return 0

    # 4. Bulk insert chunks with embeddings
    chunk_objects = []
    for chunk, embedding in zip(chunks, embeddings):
        chunk_objects.append(
            DocumentoChunk(
                id=uuid.uuid4(),
                documento_id=documento.id,
                parecer_id=documento.parecer_id,
                conteudo=chunk.conteudo,
                embedding=embedding,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                chunk_type=chunk.chunk_type,
                nome_arquivo=documento.nome_arquivo,
                tipo_documento=documento.tipo,
            )
        )

    db.add_all(chunk_objects)
    await db.flush()

    logger.info(
        "Indexed %d chunks for documento %s (%s)",
        len(chunk_objects),
        documento.id,
        documento.nome_arquivo,
    )

    return len(chunk_objects)
