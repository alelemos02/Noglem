"""add idioma relatorio to pareceres

Revision ID: 9ef01ccda2b6
Revises: d4e5f6a7b8c9
Create Date: 2026-05-22 08:50:11.777372

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ef01ccda2b6'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "pareceres",
        sa.Column("idioma_relatorio", sa.String(10), nullable=False, server_default="pt"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("pareceres", "idioma_relatorio")
