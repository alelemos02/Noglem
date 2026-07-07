"""caso tecnico fase 3: rodadas do fornecedor (tipos 1-4) e vinculacao

Revision ID: f3a0rodadas03
Revises: f2a0estados02
Create Date: 2026-06-10

Mudanças:
  - Cria tabela `rodadas_fornecedor` (resposta do fornecedor no nível do caso,
    bloco 22 do fluxo: tipos PROPOSTA_REVISADA / RESPOSTA_ITENS /
    RESPOSTA_ITENS_PROPOSTA_POSTERIOR / EMAIL_AVULSO)
  - rodadas_avaliacao: + rodada_fornecedor_id (FK), trecho_vinculado,
    vinculo_confianca, vinculo_metodo; CHECK de origem ganha
    VERIFICACAO_FINAL e REVISAO_SPEC
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a0rodadas03"
down_revision: Union[str, Sequence[str], None] = "f2a0estados02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rodadas_fornecedor",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("parecer_id", sa.UUID(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("texto_colado", sa.Text(), nullable=True),
        sa.Column("documento_id", sa.UUID(), nullable=True),
        sa.Column("proposta_final", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(30), nullable=False, server_default="RECEBIDA"),
        sa.Column("erro_detalhe", sa.Text(), nullable=True),
        sa.Column("criado_por", sa.UUID(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parecer_id"], ["pareceres.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["documento_id"], ["documentos.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["criado_por"], ["usuarios.id"]),
        sa.CheckConstraint(
            "tipo IN ('PROPOSTA_REVISADA','RESPOSTA_ITENS',"
            "'RESPOSTA_ITENS_PROPOSTA_POSTERIOR','EMAIL_AVULSO')",
            name="ck_rodada_fornecedor_tipo",
        ),
        sa.CheckConstraint(
            "status IN ('RECEBIDA','VINCULACAO_SUGERIDA','VINCULACAO_CONFIRMADA',"
            "'AVALIADA','ERRO')",
            name="ck_rodada_fornecedor_status",
        ),
    )
    op.create_index(
        "ix_rodadas_fornecedor_parecer_id", "rodadas_fornecedor", ["parecer_id"]
    )

    op.add_column(
        "rodadas_avaliacao",
        sa.Column("rodada_fornecedor_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_rodadas_avaliacao_rodada_fornecedor",
        "rodadas_avaliacao",
        "rodadas_fornecedor",
        ["rodada_fornecedor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_rodadas_avaliacao_rodada_fornecedor_id",
        "rodadas_avaliacao",
        ["rodada_fornecedor_id"],
    )
    op.add_column("rodadas_avaliacao", sa.Column("trecho_vinculado", sa.Text(), nullable=True))
    op.add_column(
        "rodadas_avaliacao", sa.Column("vinculo_confianca", sa.String(10), nullable=True)
    )
    op.add_column(
        "rodadas_avaliacao", sa.Column("vinculo_metodo", sa.String(15), nullable=True)
    )
    op.create_check_constraint(
        "ck_rodada_vinculo_confianca",
        "rodadas_avaliacao",
        "vinculo_confianca IN ('ALTA','MEDIA','BAIXA') OR vinculo_confianca IS NULL",
    )
    op.create_check_constraint(
        "ck_rodada_vinculo_metodo",
        "rodadas_avaliacao",
        "vinculo_metodo IN ('LLM','MANUAL','DETERMINISTICO') OR vinculo_metodo IS NULL",
    )

    op.drop_constraint("ck_rodada_origem", "rodadas_avaliacao", type_="check")
    op.create_check_constraint(
        "ck_rodada_origem",
        "rodadas_avaliacao",
        "origem IN ('PROPOSTA_INICIAL','RESPOSTA_FORNECEDOR','COMENTARIO_ENGENHARIA',"
        "'VERIFICACAO_FINAL','REVISAO_SPEC')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_rodada_origem", "rodadas_avaliacao", type_="check")
    op.create_check_constraint(
        "ck_rodada_origem",
        "rodadas_avaliacao",
        "origem IN ('PROPOSTA_INICIAL','RESPOSTA_FORNECEDOR','COMENTARIO_ENGENHARIA')",
    )
    op.drop_constraint("ck_rodada_vinculo_metodo", "rodadas_avaliacao", type_="check")
    op.drop_constraint("ck_rodada_vinculo_confianca", "rodadas_avaliacao", type_="check")
    op.drop_column("rodadas_avaliacao", "vinculo_metodo")
    op.drop_column("rodadas_avaliacao", "vinculo_confianca")
    op.drop_column("rodadas_avaliacao", "trecho_vinculado")
    op.drop_index(
        "ix_rodadas_avaliacao_rodada_fornecedor_id", table_name="rodadas_avaliacao"
    )
    op.drop_constraint(
        "fk_rodadas_avaliacao_rodada_fornecedor", "rodadas_avaliacao", type_="foreignkey"
    )
    op.drop_column("rodadas_avaliacao", "rodada_fornecedor_id")
    op.drop_index("ix_rodadas_fornecedor_parecer_id", table_name="rodadas_fornecedor")
    op.drop_table("rodadas_fornecedor")
