"""add condicoes_verificadas to itens_parecer

Coluna de auditoria do verificador de condicoes atomicas (ultimo gate do
pipeline de analise): JSON serializado com o veredito por condicao do requisito
(CONFIRMADA/NAO_MENCIONADA/DIVERGENTE + evidencia do fornecedor), o status
original e o eventual rebaixamento. Nasceu do caso "video wall": a acao_requerida
esquecia condicoes nao confirmadas (rack 19"). Nunca exportada no parecer.

Revision ID: fa0cond10
Revises: f9a0qaflag09
Create Date: 2026-07-13
"""

import sqlalchemy as sa
from alembic import op

revision = "fa0cond10"
down_revision = "f9a0qaflag09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "itens_parecer",
        sa.Column("condicoes_verificadas", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("itens_parecer", "condicoes_verificadas")
