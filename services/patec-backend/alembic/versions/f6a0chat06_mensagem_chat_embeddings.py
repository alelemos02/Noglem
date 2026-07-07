"""chat semantic memory embeddings

Revision ID: f6a0chat06
Revises: f5a0spec05
Create Date: 2026-06-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f6a0chat06"
down_revision: Union[str, Sequence[str], None] = "f5a0spec05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "mensagens_chat_embeddings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("mensagem_id", sa.UUID(), nullable=False),
        sa.Column("parecer_id", sa.UUID(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["mensagem_id"], ["mensagens_chat.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parecer_id"], ["pareceres.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("mensagem_id", name="uq_mensagens_chat_embeddings_mensagem_id"),
    )
    op.execute(
        "ALTER TABLE mensagens_chat_embeddings "
        "ALTER COLUMN embedding TYPE vector(768) USING embedding::vector(768)"
    )
    op.create_index(
        "ix_mensagens_chat_embeddings_mensagem_id",
        "mensagens_chat_embeddings",
        ["mensagem_id"],
    )
    op.create_index(
        "ix_mensagens_chat_embeddings_parecer_id",
        "mensagens_chat_embeddings",
        ["parecer_id"],
    )
    op.execute(
        "CREATE INDEX idx_mensagens_chat_embeddings_embedding "
        "ON mensagens_chat_embeddings "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.drop_index("idx_mensagens_chat_embeddings_embedding", table_name="mensagens_chat_embeddings")
    op.drop_index("ix_mensagens_chat_embeddings_parecer_id", table_name="mensagens_chat_embeddings")
    op.drop_index("ix_mensagens_chat_embeddings_mensagem_id", table_name="mensagens_chat_embeddings")
    op.drop_table("mensagens_chat_embeddings")
