"""add complementares_resolvidos flag to pareceres

Gate conversacional de setup: o usuário resolve os documentos complementares
(anexa referências/normas OU declara que não tem) antes de a JULIA pedir a
proposta do fornecedor.

Revision ID: f7a0comp07
Revises: f6a0chat06
Create Date: 2026-06-18
"""

import sqlalchemy as sa
from alembic import op

revision = "f7a0comp07"
down_revision = "f6a0chat06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pareceres",
        sa.Column(
            "complementares_resolvidos",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("pareceres", "complementares_resolvidos")
