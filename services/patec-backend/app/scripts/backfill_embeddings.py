"""Backfill embeddings for existing documents.

Run this script after deploying RAG support to index all existing documents
that already have texto_extraido but no chunks in documento_chunks.

Usage:
    cd services/patec-backend
    python -m app.scripts.backfill_embeddings
"""

import asyncio
import logging
import sys

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("backfill_embeddings")


async def backfill():
    """Index all documents that have extracted text but no chunks."""
    # Import here to ensure app config is loaded
    from app.core.database import async_session
    from app.models.documento import Documento
    from app.models.documento_chunk import DocumentoChunk
    from app.services.indexer import index_document

    async with async_session() as db:
        # Find documents with texto_extraido but without chunks
        subq = (
            select(DocumentoChunk.documento_id)
            .distinct()
            .scalar_subquery()
        )
        result = await db.execute(
            select(Documento)
            .where(
                Documento.texto_extraido.isnot(None),
                Documento.texto_extraido != "",
                ~Documento.id.in_(subq),
            )
            .order_by(Documento.criado_em)
        )
        documents = result.scalars().all()

        if not documents:
            logger.info("No documents need backfilling. All documents already indexed.")
            return

        logger.info("Found %d documents to backfill", len(documents))

        total_chunks = 0
        errors = 0

        for i, doc in enumerate(documents, 1):
            logger.info(
                "[%d/%d] Indexing: %s (parecer_id=%s, tipo=%s)",
                i,
                len(documents),
                doc.nome_arquivo,
                doc.parecer_id,
                doc.tipo,
            )
            try:
                count = await index_document(doc, db)
                await db.commit()
                total_chunks += count
                logger.info("  -> %d chunks created", count)
            except Exception:
                logger.exception("  -> FAILED to index %s", doc.nome_arquivo)
                await db.rollback()
                errors += 1

        logger.info(
            "Backfill complete: %d documents processed, %d total chunks, %d errors",
            len(documents),
            total_chunks,
            errors,
        )


def main():
    asyncio.run(backfill())


if __name__ == "__main__":
    main()
