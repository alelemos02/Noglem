"""resize embedding vector from 768 to 3072 for gemini-embedding-001

Revision ID: c8d3e5f72a14
Revises: b7e2f4a91c03
Create Date: 2026-03-17 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c8d3e5f72a14"
down_revision: Union[str, None] = "b7e2f4a91c03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the HNSW index first (it's tied to the vector dimension)
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")

    # Truncate existing chunks (they have wrong dimensions anyway)
    op.execute("TRUNCATE TABLE documento_chunks")

    # Alter vector column from 768 to 3072 dimensions
    op.execute(
        "ALTER TABLE documento_chunks "
        "ALTER COLUMN embedding TYPE vector(3072) USING embedding::vector(3072)"
    )

    # Recreate HNSW index with new dimensions
    op.execute(
        "CREATE INDEX idx_chunks_embedding ON documento_chunks "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")
    op.execute("TRUNCATE TABLE documento_chunks")
    op.execute(
        "ALTER TABLE documento_chunks "
        "ALTER COLUMN embedding TYPE vector(768) USING embedding::vector(768)"
    )
    op.execute(
        "CREATE INDEX idx_chunks_embedding ON documento_chunks "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )
