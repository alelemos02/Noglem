"""fix idioma_relatorio column if not exists

Revision ID: a1b2c3d4e5f6
Revises: 9ef01ccda2b6
Create Date: 2026-05-22 10:00:00.000000

Garante que a coluna idioma_relatorio existe, independente do estado da migration anterior.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '9ef01ccda2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE pareceres
        ADD COLUMN IF NOT EXISTS idioma_relatorio VARCHAR(10) NOT NULL DEFAULT 'pt'
    """)


def downgrade() -> None:
    pass
