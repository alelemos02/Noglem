"""Semantic memory for JULIA chat history.

Indexes saved chat messages with embeddings and retrieves older conversation
turns when the user explicitly asks JULIA to consult prior history.
"""

from __future__ import annotations

import logging
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.mensagem_chat import MensagemChat
from app.models.mensagem_chat_embedding import MensagemChatEmbedding
from app.services.embedding import embed_query, embed_texts

logger = logging.getLogger(__name__)


@dataclass
class ChatMemoryHit:
    id: uuid.UUID
    papel: str
    conteudo: str
    ordem: int
    criado_em: datetime
    similarity: float


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def should_retrieve_chat_memory(message: str) -> bool:
    """Return true when the user explicitly asks about older chat history."""
    text_norm = _normalize(message)
    triggers = (
        "historico",
        "conversa antiga",
        "conversas antigas",
        "mensagem antiga",
        "mensagens antigas",
        "ja falamos",
        "falamos antes",
        "anteriormente",
        "no passado",
        "consulte",
        "consulta antiga",
        "buscar na conversa",
        "procure na conversa",
        "lembra",
        "voce lembra",
        "o que eu disse",
        "o que foi dito",
    )
    return any(trigger in text_norm for trigger in triggers)


def _message_text(message: MensagemChat) -> str:
    role = "Usuario" if message.papel == "user" else "JULIA"
    created = message.criado_em.isoformat() if message.criado_em else ""
    return f"{role} em {created}:\n{message.conteudo}"


async def index_chat_message(
    message: MensagemChat,
    db: AsyncSession,
) -> bool:
    """Index a single chat message. Returns false when indexing fails."""
    try:
        embeddings = await embed_texts(
            [_message_text(message)],
            task_type="RETRIEVAL_DOCUMENT",
        )
        if not embeddings:
            return False

        exists = await db.execute(
            select(MensagemChatEmbedding.id).where(
                MensagemChatEmbedding.mensagem_id == message.id
            )
        )
        if exists.scalar_one_or_none():
            return True

        db.add(
            MensagemChatEmbedding(
                id=uuid.uuid4(),
                mensagem_id=message.id,
                parecer_id=message.parecer_id,
                embedding=embeddings[0],
            )
        )
        await db.flush()
        return True
    except Exception:
        logger.exception("Falha ao indexar mensagem de chat %s", message.id)
        await db.rollback()
        return False


async def index_missing_chat_messages(
    parecer_id: uuid.UUID,
    db: AsyncSession,
    limit: int | None = None,
) -> int:
    """Backfill embeddings for saved chat messages that are not indexed yet."""
    if limit is None:
        limit = settings.CHAT_MEMORY_BACKFILL_LIMIT

    result = await db.execute(
        select(MensagemChat)
        .outerjoin(
            MensagemChatEmbedding,
            MensagemChatEmbedding.mensagem_id == MensagemChat.id,
        )
        .where(
            MensagemChat.parecer_id == parecer_id,
            MensagemChatEmbedding.id.is_(None),
        )
        .order_by(MensagemChat.ordem.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    if not messages:
        return 0

    texts = [_message_text(message) for message in messages]
    try:
        embeddings = await embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")
    except Exception:
        logger.exception("Falha no backfill semantico do chat do parecer %s", parecer_id)
        return 0

    indexed = 0
    for message, embedding in zip(messages, embeddings):
        db.add(
            MensagemChatEmbedding(
                id=uuid.uuid4(),
                mensagem_id=message.id,
                parecer_id=message.parecer_id,
                embedding=embedding,
            )
        )
        indexed += 1

    try:
        await db.flush()
    except Exception:
        logger.exception("Falha ao salvar backfill semantico do chat %s", parecer_id)
        await db.rollback()
        return 0

    return indexed


async def retrieve_chat_memory(
    query: str,
    parecer_id: uuid.UUID,
    db: AsyncSession,
    top_k: int | None = None,
    exclude_message_ids: set[uuid.UUID] | None = None,
) -> list[ChatMemoryHit]:
    """Retrieve semantically relevant saved chat messages for a case."""
    if top_k is None:
        top_k = settings.CHAT_MEMORY_TOP_K

    try:
        query_embedding = await embed_query(query)
    except Exception:
        logger.exception("Falha ao gerar embedding para memoria do chat")
        return []

    exclude_message_ids = exclude_message_ids or set()
    exclude_sql = ""
    params: dict[str, object] = {
        "query_vec": "[" + ",".join(str(v) for v in query_embedding) + "]",
        "parecer_id": str(parecer_id),
        "top_k": top_k,
    }
    if exclude_message_ids:
        placeholders = []
        for idx, message_id in enumerate(exclude_message_ids):
            key = f"exclude_id_{idx}"
            placeholders.append(f"CAST(:{key} AS uuid)")
            params[key] = str(message_id)
        exclude_sql = f"AND m.id NOT IN ({', '.join(placeholders)})"

    sql = text(f"""
        SELECT
            m.id, m.papel, m.conteudo, m.ordem, m.criado_em,
            1 - (e.embedding <=> CAST(:query_vec AS vector)) AS similarity
        FROM mensagens_chat_embeddings e
        JOIN mensagens_chat m ON m.id = e.mensagem_id
        WHERE e.parecer_id = :parecer_id
        {exclude_sql}
        ORDER BY e.embedding <=> CAST(:query_vec AS vector)
        LIMIT :top_k
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    return [
        ChatMemoryHit(
            id=row.id,
            papel=row.papel,
            conteudo=row.conteudo,
            ordem=row.ordem,
            criado_em=row.criado_em,
            similarity=float(row.similarity or 0),
        )
        for row in rows
    ]
