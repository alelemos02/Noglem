"""add flag_consistencia + nota_revisao to itens_parecer

Mantém os flags internos de QA FORA da justificativa_tecnica (que e exportada ao
cliente). `flag_consistencia`: termo do requisito encontrado no texto do
fornecedor apesar de o item ter sido classificado como nao-conforme (rede
anti-falso-negativo). `nota_revisao`: correcao aplicada pelo self-review (segunda
IA) quando o status foi alterado. Ambos exibidos so como badge interno na UI —
nunca no parecer.

Revision ID: f9a0qaflag09
Revises: f8a0verif08
Create Date: 2026-07-02
"""

import sqlalchemy as sa
from alembic import op

revision = "f9a0qaflag09"
down_revision = "f8a0verif08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "itens_parecer",
        sa.Column("flag_consistencia", sa.Text(), nullable=True),
    )
    op.add_column(
        "itens_parecer",
        sa.Column("nota_revisao", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("itens_parecer", "nota_revisao")
    op.drop_column("itens_parecer", "flag_consistencia")
