"""add verificacao flag + nota to itens_parecer

Verificacao cruzada (estagio pos-cache): um detector deterministico marca itens
suspeitos (ex.: mesmo valor do fornecedor reaproveitado em requisitos distintos)
em `verificacao_flag`; um modelo mais forte (Gemini Pro) revisa SO esses itens e
grava o veredito/correcao em `verificacao_nota`.

Revision ID: f8a0verif08
Revises: f7a0comp07
Create Date: 2026-06-22
"""

import sqlalchemy as sa
from alembic import op

revision = "f8a0verif08"
down_revision = "f7a0comp07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "itens_parecer",
        sa.Column("verificacao_flag", sa.Text(), nullable=True),
    )
    op.add_column(
        "itens_parecer",
        sa.Column("verificacao_nota", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("itens_parecer", "verificacao_nota")
    op.drop_column("itens_parecer", "verificacao_flag")
