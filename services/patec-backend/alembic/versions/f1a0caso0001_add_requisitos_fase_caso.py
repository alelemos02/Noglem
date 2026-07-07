"""caso tecnico fase 1: tabela requisitos + fase_caso + requisito_id

Revision ID: f1a0caso0001
Revises: a1b2c3d4e5f6
Create Date: 2026-06-10

Mudanças:
  - Cria tabela `requisitos` (fonte única de verdade dos requisitos de engenharia,
    gravada na aprovação humana — operação W1)
  - Adiciona `pareceres.fase_caso` (SETUP/REQUISITOS/ANALISE/CICLO_FORNECEDOR/
    VERIFICACAO_FINAL/FECHADO)
  - Adiciona `itens_parecer.requisito_id` (FK nullable nesta fase)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a0caso0001"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "requisitos",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("parecer_id", sa.UUID(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("categoria", sa.String(100), nullable=True),
        sa.Column("descricao_requisito", sa.Text(), nullable=False),
        sa.Column("referencia_engenharia", sa.String(500), nullable=True),
        sa.Column("valor_requerido", sa.Text(), nullable=True),
        sa.Column("prioridade", sa.String(10), nullable=True),
        sa.Column("norma_referencia", sa.String(200), nullable=True),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("desativado_em", sa.DateTime(), nullable=True),
        sa.Column("desativado_motivo", sa.Text(), nullable=True),
        sa.Column("aprovado_por", sa.UUID(), nullable=True),
        sa.Column("aprovado_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parecer_id"], ["pareceres.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["aprovado_por"], ["usuarios.id"]),
        sa.CheckConstraint(
            "prioridade IN ('ALTA','MEDIA','BAIXA') OR prioridade IS NULL",
            name="ck_requisito_prioridade",
        ),
    )
    op.create_index("ix_requisitos_parecer_id", "requisitos", ["parecer_id"])

    op.add_column(
        "pareceres",
        sa.Column("fase_caso", sa.String(30), nullable=False, server_default="SETUP"),
    )
    op.create_check_constraint(
        "ck_parecer_fase_caso",
        "pareceres",
        "fase_caso IN ('SETUP','REQUISITOS','ANALISE','CICLO_FORNECEDOR',"
        "'VERIFICACAO_FINAL','FECHADO')",
    )

    op.add_column(
        "itens_parecer",
        sa.Column("requisito_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_itens_parecer_requisito_id",
        "itens_parecer",
        "requisitos",
        ["requisito_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_itens_parecer_requisito_id", "itens_parecer", ["requisito_id"])


def downgrade() -> None:
    op.drop_index("ix_itens_parecer_requisito_id", table_name="itens_parecer")
    op.drop_constraint("fk_itens_parecer_requisito_id", "itens_parecer", type_="foreignkey")
    op.drop_column("itens_parecer", "requisito_id")
    op.drop_constraint("ck_parecer_fase_caso", "pareceres", type_="check")
    op.drop_column("pareceres", "fase_caso")
    op.drop_index("ix_requisitos_parecer_id", table_name="requisitos")
    op.drop_table("requisitos")
