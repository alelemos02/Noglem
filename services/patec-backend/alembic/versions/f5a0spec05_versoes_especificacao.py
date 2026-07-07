"""caso tecnico fase 5: revisao da especificacao (R4/W7)

Revision ID: f5a0spec05
Revises: f4a0verif04
Create Date: 2026-06-10

Mudanças:
  - Cria tabela `versoes_especificacao` (caminho lateral, blocos 35-41)
  - requisitos: + origem_versao_spec_id, alterado_versao_spec_id (FKs)
  - pareceres: + revisao_spec_em_andamento (trava do caminho lateral)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f5a0spec05"
down_revision: Union[str, Sequence[str], None] = "f4a0verif04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "versoes_especificacao",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("parecer_id", sa.UUID(), nullable=False),
        sa.Column("numero_versao", sa.Integer(), nullable=False),
        sa.Column("documento_id", sa.UUID(), nullable=True),
        sa.Column("resumo_diff", sa.JSON(), nullable=True),
        sa.Column("cenario", sa.String(1), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="EM_COMPARACAO"),
        sa.Column("erro_detalhe", sa.String(500), nullable=True),
        sa.Column("fase_caso_anterior", sa.String(30), nullable=True),
        sa.Column("aplicado_por", sa.UUID(), nullable=True),
        sa.Column("aplicado_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parecer_id"], ["pareceres.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["documento_id"], ["documentos.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["aplicado_por"], ["usuarios.id"]),
        sa.CheckConstraint(
            "cenario IN ('A','B','C') OR cenario IS NULL",
            name="ck_versao_spec_cenario",
        ),
        sa.CheckConstraint(
            "status IN ('EM_COMPARACAO','AGUARDANDO_DECISAO','APLICADA','DESCARTADA','ERRO')",
            name="ck_versao_spec_status",
        ),
    )
    op.create_index(
        "ix_versoes_especificacao_parecer_id", "versoes_especificacao", ["parecer_id"]
    )

    op.add_column(
        "requisitos", sa.Column("origem_versao_spec_id", sa.UUID(), nullable=True)
    )
    op.add_column(
        "requisitos", sa.Column("alterado_versao_spec_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "fk_requisitos_origem_versao_spec",
        "requisitos", "versoes_especificacao",
        ["origem_versao_spec_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_requisitos_alterado_versao_spec",
        "requisitos", "versoes_especificacao",
        ["alterado_versao_spec_id"], ["id"], ondelete="SET NULL",
    )

    op.add_column(
        "pareceres",
        sa.Column(
            "revisao_spec_em_andamento", sa.Boolean(), nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("pareceres", "revisao_spec_em_andamento")
    op.drop_constraint("fk_requisitos_alterado_versao_spec", "requisitos", type_="foreignkey")
    op.drop_constraint("fk_requisitos_origem_versao_spec", "requisitos", type_="foreignkey")
    op.drop_column("requisitos", "alterado_versao_spec_id")
    op.drop_column("requisitos", "origem_versao_spec_id")
    op.drop_index("ix_versoes_especificacao_parecer_id", table_name="versoes_especificacao")
    op.drop_table("versoes_especificacao")
