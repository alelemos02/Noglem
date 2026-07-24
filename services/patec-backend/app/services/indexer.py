"""Document indexing pipeline for PATEC RAG.

Orchestrates: chunk text -> generate embeddings -> store in database.

O indexing roda em BACKGROUND (Celery) quando um documento e enviado: chunk +
embedding de N pedacos via API e lento (milhares de chamadas para documentos
grandes) e NAO pode bloquear a resposta HTTP do upload — senao a requisicao
estoura o timeout e o browser mostra "Failed to fetch". O indice RAG so e usado
no chat, muito depois do upload, entao o atraso e irrelevante.
"""

import asyncio
import logging
import uuid

from sqlalchemy import create_engine, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.documento import Documento
from app.models.documento_chunk import DocumentoChunk
from app.services.chunker import chunk_text
from app.services.embedding import embed_texts

logger = logging.getLogger(__name__)

_sync_engine = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(settings.DATABASE_URL_SYNC)
    return _sync_engine


def enqueue_indexing(documento_id: str) -> str | None:
    """Enfileira a indexacao RAG de um documento no Celery (nao bloqueia o upload).

    Devolve o task id, ou None se o enfileiramento falhar (ex: broker fora) —
    nesse caso o documento fica sem RAG, mas o upload nao quebra.
    """
    try:
        from app.worker import indexar_documento_task

        task = indexar_documento_task.delay(documento_id)
        return task.id
    except Exception:
        logger.exception(
            "Falha ao enfileirar indexacao do documento %s", documento_id
        )
        return None


def index_document_sync(documento_id: str) -> int:
    """Versao sincrona (Celery worker) de index_document: chunk + embed + store.

    Usa sessao sync propria e roda o embedding async via asyncio.run.
    """
    engine = _get_sync_engine()
    with Session(engine) as db:
        # Serializa indexacoes concorrentes do MESMO documento (task de upload
        # vs indexacao inline do passe de amarracoes): sem o lock, dois
        # delete+insert intercalados duplicam todos os chunks. O lock e liberado
        # no fim da transacao (commit/rollback).
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:doc_id))"),
            {"doc_id": str(documento_id)},
        )
        documento = db.get(Documento, uuid.UUID(documento_id))
        if not documento or not (documento.texto_extraido or "").strip():
            logger.warning(
                "Documento %s sem texto extraido, pulando indexacao", documento_id
            )
            return 0

        db.execute(
            delete(DocumentoChunk).where(
                DocumentoChunk.documento_id == documento.id
            )
        )

        chunks = chunk_text(documento.texto_extraido)
        if not chunks:
            db.commit()
            return 0

        logger.info(
            "Indexando documento %s (%s): %d chunks",
            documento.id,
            documento.nome_arquivo,
            len(chunks),
        )

        texts = [c.conteudo for c in chunks]
        try:
            embeddings = asyncio.run(
                embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")
            )
        except Exception:
            logger.exception(
                "Falha ao gerar embeddings do documento %s", documento.id
            )
            db.rollback()
            return 0

        if len(embeddings) != len(chunks):
            logger.error(
                "Contagem de embeddings difere: %d chunks vs %d embeddings (doc %s)",
                len(chunks),
                len(embeddings),
                documento.id,
            )
            db.rollback()
            return 0

        for chunk, embedding in zip(chunks, embeddings):
            db.add(
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

        db.commit()
        logger.info(
            "Indexados %d chunks para documento %s", len(chunks), documento.id
        )
        return len(chunks)


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
