import json
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db, async_session
from app.core.deps import require_internal_api_key
from app.models.collection import Collection
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.schemas.chat import ChatSessionCreate, ChatSessionSchema, ChatMessageCreate, ChatMessageSchema
from app.services.retriever import retrieve_relevant_chunks
from app.services.chat_service import build_chat_context, call_gemini_stream, call_gemini_sync

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_internal_api_key)])


@router.post("/chats", response_model=ChatSessionSchema)
async def create_chat_session(
    session: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Collection).where(Collection.id == session.collection_id)
    )
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    db_session = ChatSession(
        collection_id=session.collection_id,
        title=session.title or "New Chat",
    )
    db.add(db_session)
    await db.commit()
    await db.refresh(db_session, attribute_names=["messages"])
    return db_session


@router.get("/collections/{collection_id}/chats", response_model=list[ChatSessionSchema])
async def list_chats(
    collection_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.collection_id == collection_id)
        .options(selectinload(ChatSession.messages))
        .order_by(ChatSession.created_at.desc())
    )
    return result.scalars().all()


@router.get("/chats/{chat_id}", response_model=ChatSessionSchema)
async def get_chat(
    chat_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == chat_id)
        .options(selectinload(ChatSession.messages))
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return chat


@router.delete("/chats/{chat_id}")
async def delete_chat(
    chat_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == chat_id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # Cascade delete handles messages
    await db.delete(chat)
    await db.commit()
    return {"message": "Chat deleted successfully"}


@router.get("/chats/{chat_id}/messages", response_model=list[ChatMessageSchema])
async def get_messages(
    chat_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return result.scalars().all()


async def _get_chat_history(db: AsyncSession, chat_id: str, limit: int = 10) -> list[dict]:
    """Get recent chat history for context."""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    return [{"role": msg.role, "content": msg.content} for msg in messages]


@router.post("/chats/{chat_id}/messages", response_model=ChatMessageSchema)
async def send_message(
    chat_id: str,
    message: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == chat_id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # 1. Save user message
    user_msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=chat_id,
        role="user",
        content=message.content,
    )
    db.add(user_msg)

    # Update title if first message
    if chat.title == "New Chat":
        chat.title = message.content[:30] + ("..." if len(message.content) > 30 else "")

    await db.commit()

    # 2. Retrieve relevant chunks
    chunks = await retrieve_relevant_chunks(
        query=message.content,
        collection_id=chat.collection_id,
        db=db,
    )

    # 3. Build context and get response
    chat_history = await _get_chat_history(db, chat_id, limit=10)
    system_prompt, contents = build_chat_context(
        chunks=chunks,
        chat_history=chat_history,
        new_message=message.content,
    )

    response_text = await call_gemini_sync(system_prompt, contents)

    # 4. Save assistant message
    ai_msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=chat_id,
        role="assistant",
        content=response_text,
    )
    db.add(ai_msg)
    await db.commit()
    await db.refresh(ai_msg)

    return ai_msg


@router.post("/chats/{chat_id}/messages/stream")
async def send_message_stream(
    chat_id: str,
    message: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == chat_id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # 1. Save user message
    user_msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=chat_id,
        role="user",
        content=message.content,
    )
    db.add(user_msg)

    # Update title if first message
    if chat.title == "New Chat":
        chat.title = message.content[:30] + ("..." if len(message.content) > 30 else "")

    await db.commit()

    # 2. Retrieve relevant chunks
    chunks = await retrieve_relevant_chunks(
        query=message.content,
        collection_id=chat.collection_id,
        db=db,
    )

    # 3. Build context
    chat_history = await _get_chat_history(db, chat_id, limit=10)
    system_prompt, contents = build_chat_context(
        chunks=chunks,
        chat_history=chat_history,
        new_message=message.content,
    )

    # Capture collection_id and chat_id for the generator closure
    saved_chat_id = chat_id

    async def generate():
        full_response = ""
        try:
            async for chunk in call_gemini_stream(system_prompt, contents):
                full_response += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            # Save complete response using a fresh session
            async with async_session() as save_db:
                ai_msg = ChatMessage(
                    id=str(uuid.uuid4()),
                    session_id=saved_chat_id,
                    role="assistant",
                    content=full_response,
                )
                save_db.add(ai_msg)
                await save_db.commit()

                yield f"data: {json.dumps({'done': True, 'message_id': ai_msg.id})}\n\n"

        except Exception as e:
            logger.error("Streaming error: %s", e, exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
