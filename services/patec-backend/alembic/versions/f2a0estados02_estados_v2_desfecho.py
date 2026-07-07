"""caso tecnico fase 2: estados v2, decisoes novas, desfecho do caso

Revision ID: f2a0estados02
Revises: f1a0caso0001
Create Date: 2026-06-10

Mudanças:
  - itens_parecer.estado: RESOLVIDO→ACEITO, ESCALONADO→PENDENTE_FORNECEDOR
    (escalonamento gerencial removido do fluxo); novos estados REPROVADO e
    DESATIVADO no CHECK
  - rodadas_avaliacao.decisao_humana: ATENDE/PARCIAL/NAO_ATENDE →
    ACEITAR/ESCLARECER/REJEITAR/REPROVAR_CASO (veredito_ia mantém o
    vocabulário antigo como sugestão da LLM)
  - pareceres: + desfecho (APROVADO/COM_PENDENCIA/REPROVADO), fechado_em,
    fechado_por, motivo_fechamento; − status_global, rodada_atual (derivados)
  - itens_parecer: + marcacao_revisao (NOVO/ALTERADO) para highlights da
    revisão de especificação
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a0estados02"
down_revision: Union[str, Sequence[str], None] = "f1a0caso0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ----------------------------------------------------- itens_parecer --
    op.drop_constraint("ck_item_estado", "itens_parecer", type_="check")
    op.execute("UPDATE itens_parecer SET estado = 'ACEITO' WHERE estado = 'RESOLVIDO'")
    op.execute(
        "UPDATE itens_parecer SET estado = 'PENDENTE_FORNECEDOR' WHERE estado = 'ESCALONADO'"
    )
    op.create_check_constraint(
        "ck_item_estado",
        "itens_parecer",
        "estado IN ('ABERTO','PENDENTE_FORNECEDOR','EM_REAVALIACAO',"
        "'ACEITO','REPROVADO','DESATIVADO')",
    )

    op.add_column(
        "itens_parecer",
        sa.Column("marcacao_revisao", sa.String(10), nullable=True),
    )
    op.create_check_constraint(
        "ck_item_marcacao_revisao",
        "itens_parecer",
        "marcacao_revisao IN ('NOVO','ALTERADO') OR marcacao_revisao IS NULL",
    )

    # -------------------------------------------------- rodadas_avaliacao --
    op.drop_constraint("ck_rodada_decisao_humana", "rodadas_avaliacao", type_="check")
    op.execute(
        "UPDATE rodadas_avaliacao SET decisao_humana = 'ACEITAR' WHERE decisao_humana = 'ATENDE'"
    )
    op.execute(
        "UPDATE rodadas_avaliacao SET decisao_humana = 'ESCLARECER' WHERE decisao_humana = 'PARCIAL'"
    )
    op.execute(
        "UPDATE rodadas_avaliacao SET decisao_humana = 'REJEITAR' WHERE decisao_humana = 'NAO_ATENDE'"
    )
    op.create_check_constraint(
        "ck_rodada_decisao_humana",
        "rodadas_avaliacao",
        "decisao_humana IN ('ACEITAR','ESCLARECER','REJEITAR','REPROVAR_CASO') "
        "OR decisao_humana IS NULL",
    )

    # ----------------------------------------------------------- pareceres --
    op.add_column("pareceres", sa.Column("desfecho", sa.String(20), nullable=True))
    op.create_check_constraint(
        "ck_parecer_desfecho",
        "pareceres",
        "desfecho IN ('APROVADO','COM_PENDENCIA','REPROVADO') OR desfecho IS NULL",
    )
    op.add_column("pareceres", sa.Column("fechado_em", sa.DateTime(), nullable=True))
    op.add_column("pareceres", sa.Column("fechado_por", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_pareceres_fechado_por", "pareceres", "usuarios", ["fechado_por"], ["id"]
    )
    op.add_column("pareceres", sa.Column("motivo_fechamento", sa.Text(), nullable=True))

    # status_global e rodada_atual passam a ser derivados (compute_resumo_ciclo
    # e rodadas do fornecedor) — colunas removidas.
    op.drop_column("pareceres", "status_global")
    op.drop_column("pareceres", "rodada_atual")


def downgrade() -> None:
    op.add_column(
        "pareceres",
        sa.Column("rodada_atual", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "pareceres",
        sa.Column("status_global", sa.String(25), nullable=False, server_default="EM_ANALISE"),
    )
    op.drop_column("pareceres", "motivo_fechamento")
    op.drop_constraint("fk_pareceres_fechado_por", "pareceres", type_="foreignkey")
    op.drop_column("pareceres", "fechado_por")
    op.drop_column("pareceres", "fechado_em")
    op.drop_constraint("ck_parecer_desfecho", "pareceres", type_="check")
    op.drop_column("pareceres", "desfecho")

    op.drop_constraint("ck_rodada_decisao_humana", "rodadas_avaliacao", type_="check")
    op.execute(
        "UPDATE rodadas_avaliacao SET decisao_humana = 'ATENDE' WHERE decisao_humana = 'ACEITAR'"
    )
    op.execute(
        "UPDATE rodadas_avaliacao SET decisao_humana = 'PARCIAL' WHERE decisao_humana = 'ESCLARECER'"
    )
    op.execute(
        "UPDATE rodadas_avaliacao SET decisao_humana = 'NAO_ATENDE' "
        "WHERE decisao_humana IN ('REJEITAR','REPROVAR_CASO')"
    )
    op.create_check_constraint(
        "ck_rodada_decisao_humana",
        "rodadas_avaliacao",
        "decisao_humana IN ('ATENDE','PARCIAL','NAO_ATENDE') OR decisao_humana IS NULL",
    )

    op.drop_constraint("ck_item_marcacao_revisao", "itens_parecer", type_="check")
    op.drop_column("itens_parecer", "marcacao_revisao")
    op.drop_constraint("ck_item_estado", "itens_parecer", type_="check")
    op.execute("UPDATE itens_parecer SET estado = 'RESOLVIDO' WHERE estado IN ('ACEITO')")
    op.execute(
        "UPDATE itens_parecer SET estado = 'PENDENTE_FORNECEDOR' "
        "WHERE estado IN ('REPROVADO','DESATIVADO')"
    )
    op.create_check_constraint(
        "ck_item_estado",
        "itens_parecer",
        "estado IN ('ABERTO','PENDENTE_FORNECEDOR','EM_REAVALIACAO','RESOLVIDO','ESCALONADO')",
    )
