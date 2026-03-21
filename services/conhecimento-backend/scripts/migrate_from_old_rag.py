"""One-time migration script: Old RAG (SQLite + ChromaDB) → New RAG (PostgreSQL + pgvector).

Reads collections, documents, chats, and messages from the old SQLite database
and re-indexes documents with Gemini embeddings into PostgreSQL.

Usage:
    # Set environment variables first (DATABASE_URL, GEMINI_API_KEY)
    cd services/conhecimento-backend
    python -m scripts.migrate_from_old_rag --sqlite-path ../../backend/data/rag_app.db --uploads-dir ../../backend/uploads
"""

import argparse
import asyncio
import os
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine, async_session
from app.services.text_extractor import extract_text
from app.services.indexer import index_document


async def migrate(sqlite_path: str, old_uploads_dir: str, new_uploads_dir: str):
    """Run the full migration."""
    if not os.path.exists(sqlite_path):
        print(f"ERROR: SQLite database not found at {sqlite_path}")
        return

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row

    # Test PostgreSQL connection
    async with engine.begin() as pg_conn:
        result = await pg_conn.execute(text("SELECT 1"))
        print("PostgreSQL connection OK")

    # 1. Migrate collections
    old_collections = conn.execute("SELECT * FROM collections").fetchall()
    print(f"\nFound {len(old_collections)} collections to migrate")

    collection_id_map = {}  # old_id -> new_id (keeping same IDs for simplicity)

    async with async_session() as db:
        for col in old_collections:
            old_id = col["id"]
            # Check if already migrated
            result = await db.execute(
                text("SELECT id FROM con_collections WHERE id = :id"),
                {"id": old_id},
            )
            if result.scalar():
                print(f"  Collection '{col['name']}' already migrated, skipping")
                collection_id_map[old_id] = old_id
                continue

            await db.execute(
                text("""
                    INSERT INTO con_collections (id, name, created_at)
                    VALUES (:id, :name, :created_at)
                """),
                {
                    "id": old_id,
                    "name": col["name"],
                    "created_at": col["created_at"],
                },
            )
            collection_id_map[old_id] = old_id
            print(f"  Migrated collection: {col['name']}")

        await db.commit()

    # 2. Migrate documents (and re-index with Gemini embeddings)
    old_documents = conn.execute("SELECT * FROM documents").fetchall()
    print(f"\nFound {len(old_documents)} documents to migrate")

    async with async_session() as db:
        for doc in old_documents:
            old_id = doc["id"]
            collection_id = doc["collection_id"]

            if collection_id not in collection_id_map:
                print(f"  Skipping document {doc['filename']} (orphan collection)")
                continue

            # Check if already migrated
            result = await db.execute(
                text("SELECT id FROM con_documents WHERE id = :id"),
                {"id": old_id},
            )
            if result.scalar():
                print(f"  Document '{doc['filename']}' already migrated, skipping")
                continue

            # Copy file to new uploads dir
            old_path = doc["original_path"] or ""
            new_storage_path = ""

            if old_path and os.path.exists(old_path):
                new_collection_dir = os.path.join(new_uploads_dir, collection_id)
                os.makedirs(new_collection_dir, exist_ok=True)
                new_storage_path = os.path.join(
                    new_collection_dir, f"{old_id}_{doc['filename']}"
                )
                shutil.copy2(old_path, new_storage_path)
            else:
                # Try to find file in old uploads directory
                alt_path = os.path.join(old_uploads_dir, collection_id, f"{old_id}_{doc['filename']}")
                if os.path.exists(alt_path):
                    new_collection_dir = os.path.join(new_uploads_dir, collection_id)
                    os.makedirs(new_collection_dir, exist_ok=True)
                    new_storage_path = os.path.join(
                        new_collection_dir, f"{old_id}_{doc['filename']}"
                    )
                    shutil.copy2(alt_path, new_storage_path)

            # Insert document record
            status = doc["status"] if doc["status"] else "ready"
            await db.execute(
                text("""
                    INSERT INTO con_documents
                    (id, collection_id, filename, file_type, storage_path, status, has_ocr, error_message, created_at)
                    VALUES (:id, :collection_id, :filename, :file_type, :storage_path, :status, :has_ocr, :error_message, :created_at)
                """),
                {
                    "id": old_id,
                    "collection_id": collection_id,
                    "filename": doc["filename"],
                    "file_type": "pdf",  # Old RAG only supported PDF
                    "storage_path": new_storage_path,
                    "status": status,
                    "has_ocr": bool(doc.get("has_ocr", False)),
                    "error_message": doc.get("error_message"),
                    "created_at": doc.get("created_at"),
                },
            )
            await db.commit()

            # Re-index with Gemini embeddings if file exists and was ready
            if new_storage_path and os.path.exists(new_storage_path) and status == "ready":
                print(f"  Re-indexing document: {doc['filename']}...")
                try:
                    extracted_text, has_ocr = extract_text(new_storage_path, "pdf")
                    if extracted_text and extracted_text.strip():
                        # Create a minimal document object for the indexer
                        from app.models.document import Document
                        doc_obj = Document(
                            id=old_id,
                            collection_id=collection_id,
                            filename=doc["filename"],
                            storage_path=new_storage_path,
                        )
                        num_chunks = await index_document(doc_obj, extracted_text, db)
                        await db.commit()
                        print(f"    Indexed {num_chunks} chunks with Gemini embeddings")
                    else:
                        print(f"    No text extracted, skipping indexing")
                except Exception as e:
                    print(f"    ERROR indexing: {e}")
                    await db.rollback()
            else:
                print(f"  Migrated document (no file for re-indexing): {doc['filename']}")

    # 3. Migrate chat sessions
    old_chats = conn.execute("SELECT * FROM chat_sessions").fetchall()
    print(f"\nFound {len(old_chats)} chat sessions to migrate")

    async with async_session() as db:
        for chat in old_chats:
            old_id = chat["id"]

            # Check if already migrated
            result = await db.execute(
                text("SELECT id FROM con_chat_sessions WHERE id = :id"),
                {"id": old_id},
            )
            if result.scalar():
                continue

            collection_id = chat["collection_id"]
            if collection_id not in collection_id_map:
                continue

            await db.execute(
                text("""
                    INSERT INTO con_chat_sessions (id, collection_id, title, created_at)
                    VALUES (:id, :collection_id, :title, :created_at)
                """),
                {
                    "id": old_id,
                    "collection_id": collection_id,
                    "title": chat.get("title", "New Chat"),
                    "created_at": chat.get("created_at"),
                },
            )
            print(f"  Migrated chat: {chat.get('title', 'New Chat')}")

        await db.commit()

    # 4. Migrate chat messages
    old_messages = conn.execute("SELECT * FROM chat_messages").fetchall()
    print(f"\nFound {len(old_messages)} chat messages to migrate")

    async with async_session() as db:
        for msg in old_messages:
            old_id = msg["id"]

            # Check if already migrated
            result = await db.execute(
                text("SELECT id FROM con_chat_messages WHERE id = :id"),
                {"id": old_id},
            )
            if result.scalar():
                continue

            await db.execute(
                text("""
                    INSERT INTO con_chat_messages (id, session_id, role, content, created_at)
                    VALUES (:id, :session_id, :role, :content, :created_at)
                """),
                {
                    "id": old_id,
                    "session_id": msg["session_id"],
                    "role": msg["role"],
                    "content": msg["content"],
                    "created_at": msg.get("created_at"),
                },
            )

        await db.commit()
        print(f"  Migrated {len(old_messages)} messages")

    conn.close()

    print("\n=== Migration complete ===")
    print(f"Collections: {len(old_collections)}")
    print(f"Documents: {len(old_documents)}")
    print(f"Chat sessions: {len(old_chats)}")
    print(f"Chat messages: {len(old_messages)}")


def main():
    parser = argparse.ArgumentParser(description="Migrate old RAG data to new Conhecimento backend")
    parser.add_argument(
        "--sqlite-path",
        default="../../backend/data/rag_app.db",
        help="Path to the old SQLite database",
    )
    parser.add_argument(
        "--uploads-dir",
        default="../../backend/uploads",
        help="Path to the old uploads directory",
    )
    parser.add_argument(
        "--new-uploads-dir",
        default="./uploads",
        help="Path to the new uploads directory",
    )
    args = parser.parse_args()

    asyncio.run(migrate(args.sqlite_path, args.uploads_dir, args.new_uploads_dir))


if __name__ == "__main__":
    main()
