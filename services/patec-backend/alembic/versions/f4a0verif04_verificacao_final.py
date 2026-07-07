"""caso tecnico fase 4: verificacao final (R3/W5)

Revision ID: f4a0verif04
Revises: f3a0rodadas03
Create Date: 2026-06-10

Cria a tabela `verificacoes_finais` (blocos 29-33 do fluxo): bifurcacao do
Tipo 1 (ia_dispensada), resultado da verificacao LLM contra os acordos do BD
(R3) e validacao humana (W5).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f4a0verif04"
down_revision: Union[str, Sequence[str], None] = "f3a0rodadas03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "verificacoes_finais",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("parecer_id", sa.UUID(), nullable=False),
        sa.Column("rodada_fornecedor_id", sa.UUID(), nullable=True),
        sa.Column("ia_dispensada", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDENTE"),
        sa.Column("resultado_ia", sa.JSON(), nullable=True),
        sa.Column("resultado_validado", sa.String(30), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("validado_por", sa.UUID(), nullable=True),
        sa.Column("validado_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parecer_id", name="uq_verificacao_parecer"),
        sa.ForeignKeyConstraint(["parecer_id"], ["pareceres.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["rodada_fornecedor_id"], ["rodadas_fornecedor.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["validado_por"], ["usuarios.id"]),
        sa.CheckConstraint(
            "resultado_validado IN ('CONFORME','CONFORME_COM_PENDENCIA','NAO_CONFORME') "
            "OR resultado_validado IS NULL",
            name="ck_verificacao_resultado_validado",
        ),
    )


def downgrade() -> None:
    op.drop_table("verificacoes_finais")
