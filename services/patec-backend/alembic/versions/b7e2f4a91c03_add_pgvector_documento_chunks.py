"""add pgvector extension and documento_chunks table

Revision ID: b7e2f4a91c03
Revises: a3f7c8e91d02
Create Date: 2026-03-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7e2f4a91c03"
down_revision: Union[str, None] = "a3f7c8e91d02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documento_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "documento_id",
            sa.Uuid(),
            sa.ForeignKey("documentos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parecer_id",
            sa.Uuid(),
            sa.ForeignKey("pareceres.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("conteudo", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),  # will be altered to vector below
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_type", sa.String(20), server_default="text"),
        sa.Column("nome_arquivo", sa.String(500), nullable=True),
        sa.Column("tipo_documento", sa.String(20), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("now()")),
    )

    # Alter column to proper vector type (pgvector)
    op.execute("ALTER TABLE documento_chunks ALTER COLUMN embedding TYPE vector(768) USING embedding::vector(768)")

    # Create indexes
    op.create_index("idx_chunks_parecer_id", "documento_chunks", ["parecer_id"])
    op.create_index("idx_chunks_documento_id", "documento_chunks", ["documento_id"])
    op.execute(
        "CREATE INDEX idx_chunks_embedding ON documento_chunks "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.drop_table("documento_chunks")
    op.execute("DROP EXTENSION IF EXISTS vector")
