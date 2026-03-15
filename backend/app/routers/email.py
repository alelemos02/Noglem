import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.email_models import (
    EmailAccount,
    EmailMessage,
    EmailSyncJob,
    EmailAccountStatus,
    EmailSyncStatus,
)
from app.models.email_schemas import (
    EmailAccountResponse,
    EmailSyncRequest,
    EmailSyncJobResponse,
    EmailStatsResponse,
    EmailConsentRequest,
    EmailChatCreateRequest,
    EmailChatMessageRequest,
    OAuthUrlResponse,
)
from app.models.rag_models import ChatSession, ChatMessage
from app.services.email.microsoft_graph import get_graph_service
from app.services.email.email_sync_service import sync_emails
from app.services.email.email_vector_store import get_email_vector_store_service
from app.services.email.email_rag_service import get_email_rag_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_account_or_404(user_id: str, db: Session) -> EmailAccount:
    account = db.query(EmailAccount).filter(EmailAccount.user_id == user_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Conta Microsoft não conectada")
    return account


# --- OAuth ---


@router.get("/auth/url", response_model=OAuthUrlResponse)
def get_oauth_url(user_id: str = Query(...)):
    auth_url = get_graph_service().get_auth_url(state=user_id)
    return {"auth_url": auth_url}


@router.post("/auth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(""),
    db: Session = Depends(get_db),
):
    try:
        result = get_graph_service().exchange_code(code)
        access_token = result["access_token"]
        refresh_token = result.get("refresh_token", "")
        expires_in = result.get("expires_in", 3600)

        profile = await get_graph_service().get_user_profile(access_token)

        account = db.query(EmailAccount).filter(EmailAccount.user_id == state).first()
        if account:
            account.access_token = access_token
            account.refresh_token = refresh_token
            account.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            account.microsoft_user_id = profile.get("id")
            account.email_address = profile.get("mail") or profile.get("userPrincipalName")
            account.display_name = profile.get("displayName")
            account.status = EmailAccountStatus.CONNECTED
        else:
            account = EmailAccount(
                user_id=state,
                microsoft_user_id=profile.get("id"),
                email_address=profile.get("mail") or profile.get("userPrincipalName"),
                display_name=profile.get("displayName"),
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=datetime.utcnow() + timedelta(seconds=expires_in),
                status=EmailAccountStatus.CONNECTED,
            )
            db.add(account)

        db.commit()
        db.refresh(account)
        return {"status": "connected", "email": account.email_address}

    except Exception as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


# --- Consent ---


@router.post("/consent")
def accept_consent(
    request: EmailConsentRequest,
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    account = db.query(EmailAccount).filter(EmailAccount.user_id == user_id).first()
    if account:
        account.consent_accepted_at = datetime.utcnow() if request.accepted else None
        db.commit()
        return {"status": "consent_recorded"}

    # Criar registro parcial apenas com consentimento
    account = EmailAccount(
        user_id=user_id,
        consent_accepted_at=datetime.utcnow() if request.accepted else None,
        status=EmailAccountStatus.DISCONNECTED,
    )
    db.add(account)
    db.commit()
    return {"status": "consent_recorded"}


# --- Account ---


@router.get("/account", response_model=EmailAccountResponse)
def get_account(user_id: str = Query(...), db: Session = Depends(get_db)):
    return _get_account_or_404(user_id, db)


@router.delete("/account")
def disconnect_account(user_id: str = Query(...), db: Session = Depends(get_db)):
    account = _get_account_or_404(user_id, db)

    # Limpar vector store
    if account.collection_id:
        try:
            get_email_vector_store_service().delete_by_collection(account.collection_id)
        except Exception as e:
            logger.error(f"Erro ao limpar vector store: {e}")

    # Limpar dados
    db.query(EmailSyncJob).filter(EmailSyncJob.account_id == account.id).delete()
    db.query(EmailMessage).filter(EmailMessage.account_id == account.id).delete()

    account.status = EmailAccountStatus.DISCONNECTED
    account.access_token = None
    account.refresh_token = None
    account.token_expires_at = None
    db.commit()
    return {"status": "disconnected"}


# --- Sync ---


@router.post("/sync", response_model=EmailSyncJobResponse)
async def start_sync(
    request: EmailSyncRequest,
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    account = _get_account_or_404(user_id, db)

    if account.status != EmailAccountStatus.CONNECTED:
        raise HTTPException(status_code=400, detail="Conta não conectada")

    active_job = (
        db.query(EmailSyncJob)
        .filter(
            EmailSyncJob.account_id == account.id,
            EmailSyncJob.status == EmailSyncStatus.SYNCING,
        )
        .first()
    )
    if active_job:
        raise HTTPException(status_code=409, detail="Sincronização já em andamento")

    job = await sync_emails(account.id, request.period_months, db)
    return job


@router.get("/sync/status", response_model=EmailSyncJobResponse)
def get_sync_status(user_id: str = Query(...), db: Session = Depends(get_db)):
    account = _get_account_or_404(user_id, db)

    job = (
        db.query(EmailSyncJob)
        .filter(EmailSyncJob.account_id == account.id)
        .order_by(EmailSyncJob.created_at.desc())
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Nenhuma sincronização encontrada")
    return job


# --- Stats ---


@router.get("/stats", response_model=EmailStatsResponse)
def get_stats(user_id: str = Query(...), db: Session = Depends(get_db)):
    account = db.query(EmailAccount).filter(EmailAccount.user_id == user_id).first()
    if not account:
        return EmailStatsResponse(
            total_emails=0, indexed_emails=0, last_sync=None, collection_id=None
        )

    total = db.query(EmailMessage).filter(EmailMessage.account_id == account.id).count()
    indexed = (
        db.query(EmailMessage)
        .filter(EmailMessage.account_id == account.id, EmailMessage.is_indexed == True)
        .count()
    )

    last_job = (
        db.query(EmailSyncJob)
        .filter(
            EmailSyncJob.account_id == account.id,
            EmailSyncJob.status == EmailSyncStatus.COMPLETED,
        )
        .order_by(EmailSyncJob.completed_at.desc())
        .first()
    )

    return EmailStatsResponse(
        total_emails=total,
        indexed_emails=indexed,
        last_sync=last_job.completed_at if last_job else None,
        collection_id=account.collection_id,
    )


# --- Chat ---


def _get_email_chat_history(db: Session, chat_id: str, limit: int = 10) -> List[dict]:
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == chat_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    messages = list(reversed(messages))
    return [{"role": msg.role, "content": msg.content} for msg in messages]


@router.post("/chat")
def create_chat(
    request: EmailChatCreateRequest,
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    account = _get_account_or_404(user_id, db)
    if not account.collection_id:
        raise HTTPException(status_code=400, detail="Nenhum email sincronizado ainda")

    session = ChatSession(
        collection_id=account.collection_id,
        title=request.title or "Chat de Emails",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "title": session.title, "created_at": str(session.created_at)}


@router.get("/chat/{session_id}/history")
def get_chat_history(
    session_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    account = _get_account_or_404(user_id, db)

    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session or session.collection_id != account.collection_id:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [
        {"id": m.id, "role": m.role, "content": m.content, "created_at": str(m.created_at)}
        for m in messages
    ]


@router.post("/chat/{session_id}/message")
async def send_chat_message(
    session_id: str,
    message: EmailChatMessageRequest,
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    account = _get_account_or_404(user_id, db)

    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session or session.collection_id != account.collection_id:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    # Salvar mensagem do usuário
    user_msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role="user",
        content=message.content,
    )
    db.add(user_msg)

    if session.title == "Chat de Emails":
        session.title = message.content[:40] + ("..." if len(message.content) > 40 else "")

    db.commit()

    chat_history = _get_email_chat_history(db, session_id, limit=10)

    # Streaming response
    async def generate():
        full_response = ""
        try:
            for chunk in get_email_rag_service().stream_answer(
                question=message.content,
                collection_id=account.collection_id,
                chat_history=chat_history,
            ):
                full_response += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            ai_msg = ChatMessage(
                id=str(uuid.uuid4()),
                session_id=session_id,
                role="assistant",
                content=full_response,
            )
            db.add(ai_msg)
            db.commit()

            yield f"data: {json.dumps({'done': True, 'message_id': ai_msg.id})}\n\n"

        except Exception as e:
            logger.error(f"Email chat streaming error: {e}", exc_info=True)
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
