import json
import logging
from datetime import datetime, timedelta
from typing import Set
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.models.email_models import (
    EmailAccount,
    EmailMessage,
    EmailSyncJob,
    EmailSyncStatus,
    EmailAccountStatus,
)
from app.models.rag_models import Collection
from app.services.email.microsoft_graph import get_graph_service
from app.services.email.email_vector_store import get_email_vector_store_service

logger = logging.getLogger(__name__)

email_text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def strip_html(html_content: str) -> str:
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = (line.strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def _ensure_token_valid(account: EmailAccount, db: Session) -> str:
    buffer = timedelta(minutes=5)
    if account.token_expires_at and account.token_expires_at > (datetime.utcnow() + buffer):
        return account.access_token

    try:
        result = get_graph_service().refresh_access_token(account.refresh_token)
        account.access_token = result["access_token"]
        account.refresh_token = result.get("refresh_token", account.refresh_token)
        expires_in = result.get("expires_in", 3600)
        account.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        account.status = EmailAccountStatus.CONNECTED
        db.commit()
        return account.access_token
    except Exception as e:
        account.status = EmailAccountStatus.TOKEN_EXPIRED
        db.commit()
        raise Exception(f"Falha ao renovar token: {e}")


async def sync_emails(account_id: str, period_months: int, db: Session) -> EmailSyncJob:
    account = db.query(EmailAccount).filter(EmailAccount.id == account_id).first()
    if not account:
        raise Exception("Conta não encontrada")

    job = EmailSyncJob(
        account_id=account_id,
        status=EmailSyncStatus.SYNCING,
        period_months=period_months,
        started_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        access_token = _ensure_token_valid(account, db)

        # Criar collection se não existe
        if not account.collection_id:
            collection = Collection(
                name=f"Emails - {account.email_address or account.user_id}"
            )
            db.add(collection)
            db.commit()
            db.refresh(collection)
            account.collection_id = collection.id
            db.commit()

        # IDs existentes para dedup
        existing_ids: Set[str] = set(
            row[0]
            for row in db.query(EmailMessage.microsoft_message_id)
            .filter(EmailMessage.account_id == account_id)
            .all()
        )

        # Fetch emails do Graph API
        since_date = datetime.utcnow() - timedelta(days=period_months * 30)
        graph = get_graph_service()
        next_link = None
        all_new_messages = []

        while True:
            result = await graph.get_messages(access_token, since_date, next_link=next_link)
            messages = result["value"]

            for msg in messages:
                if msg["id"] not in existing_ids:
                    all_new_messages.append(msg)

            next_link = result.get("next_link")
            if not next_link or not messages:
                break

        job.total_emails = len(all_new_messages)
        db.commit()
        logger.info(f"Encontrados {len(all_new_messages)} emails novos para indexar")

        # Processar e indexar
        vector_chunks = []
        for msg in all_new_messages:
            try:
                subject = msg.get("subject", "(Sem assunto)")
                sender = msg.get("from", {}).get("emailAddress", {})
                sender_name = sender.get("name", "")
                sender_email = sender.get("address", "")
                recipients = [
                    {
                        "name": r.get("emailAddress", {}).get("name", ""),
                        "email": r.get("emailAddress", {}).get("address", ""),
                    }
                    for r in msg.get("toRecipients", [])
                ]
                received_at_str = msg.get("receivedDateTime", "")
                received_at = (
                    datetime.fromisoformat(received_at_str.replace("Z", "+00:00"))
                    if received_at_str
                    else None
                )

                body_html = msg.get("body", {}).get("content", "")
                body_text = strip_html(body_html)
                body_preview = msg.get("bodyPreview", "")[:200]

                email_record = EmailMessage(
                    account_id=account_id,
                    microsoft_message_id=msg["id"],
                    subject=subject,
                    sender_name=sender_name,
                    sender_email=sender_email,
                    recipients=json.dumps(recipients),
                    received_at=received_at,
                    body_preview=body_preview,
                    is_indexed=False,
                )
                db.add(email_record)
                db.commit()
                db.refresh(email_record)

                # Montar texto com header do email
                recipients_str = ", ".join(r["email"] for r in recipients if r["email"])
                date_str = received_at.strftime("%d/%m/%Y %H:%M") if received_at else "N/A"
                email_header = (
                    f"Assunto: {subject}\n"
                    f"De: {sender_name} <{sender_email}>\n"
                    f"Para: {recipients_str}\n"
                    f"Data: {date_str}\n"
                    f"---\n"
                )
                full_text = email_header + body_text

                if len(full_text.strip()) < 30:
                    job.processed_emails += 1
                    db.commit()
                    continue

                chunks = email_text_splitter.create_documents(
                    texts=[full_text],
                    metadatas=[
                        {
                            "document_id": email_record.id,
                            "collection_id": account.collection_id,
                            "source_type": "email",
                            "filename": f"Email: {subject}",
                            "page_number": 1,
                            "email_subject": subject,
                            "email_sender": f"{sender_name} <{sender_email}>",
                            "email_date": received_at.isoformat() if received_at else "",
                        }
                    ],
                )
                vector_chunks.extend(chunks)

                email_record.is_indexed = True
                job.processed_emails += 1
                job.indexed_emails += 1
                db.commit()

            except Exception as e:
                logger.error(f"Erro ao processar email {msg.get('id')}: {e}")
                job.processed_emails += 1
                db.commit()
                continue

        # Indexar no vector store
        if vector_chunks:
            get_email_vector_store_service().add_documents(vector_chunks)
            logger.info(
                f"Indexados {len(vector_chunks)} chunks de {job.indexed_emails} emails"
            )

        job.status = EmailSyncStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        logger.error(f"Sync falhou: {e}", exc_info=True)
        job.status = EmailSyncStatus.FAILED
        job.error_message = str(e)
        job.completed_at = datetime.utcnow()
        db.commit()
        raise

    return job
