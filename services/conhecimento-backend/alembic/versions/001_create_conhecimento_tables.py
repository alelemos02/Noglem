"""Create conhecimento tables

Revision ID: 001_conhecimento
Revises:
Create Date: 2026-03-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_conhecimento"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension exists (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Collections
    op.create_table(
        "con_collections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False, index=True),
        sa.Column("user_id", sa.String(200), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Documents
    op.create_table(
        "con_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "collection_id",
            sa.String(36),
            sa.ForeignKey("con_collections.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(10), server_default="pdf"),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=True),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), server_default="processing"),
        sa.Column("has_ocr", sa.Boolean, server_default=sa.text("false")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Document Chunks with pgvector embeddings
    op.execute("""
        CREATE TABLE con_document_chunks (
            id UUID PRIMARY KEY,
            document_id VARCHAR(36) NOT NULL REFERENCES con_documents(id) ON DELETE CASCADE,
            collection_id VARCHAR(36) NOT NULL REFERENCES con_collections(id) ON DELETE CASCADE,
            conteudo TEXT NOT NULL,
            embedding vector(768) NOT NULL,
            page_number INTEGER,
            chunk_index INTEGER NOT NULL,
            chunk_type VARCHAR(20) DEFAULT 'text',
            nome_arquivo VARCHAR(500),
            created_at TIMESTAMP DEFAULT now()
        )
    """)

    op.create_index("ix_con_chunks_document", "con_document_chunks", ["document_id"])
    op.create_index("ix_con_chunks_collection", "con_document_chunks", ["collection_id"])

    # HNSW index for fast cosine similarity search
    op.execute("""
        CREATE INDEX ix_con_chunks_embedding ON con_document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # Chat Sessions
    op.create_table(
        "con_chat_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "collection_id",
            sa.String(36),
            sa.ForeignKey("con_collections.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(500), server_default="New Chat"),
        sa.Column("user_id", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Chat Messages
    op.create_table(
        "con_chat_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("con_chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("con_chat_messages")
    op.drop_table("con_chat_sessions")
    op.execute("DROP INDEX IF EXISTS ix_con_chunks_embedding")
    op.drop_table("con_document_chunks")
    op.drop_table("con_documents")
    op.drop_table("con_collections")
