"""add rodadas_avaliacao e ciclo iterativo

Revision ID: d4e5f6a7b8c9
Revises: c2d9e1f83a47
Create Date: 2026-05-20

Mudanças:
  - Adiciona coluna `estado` em itens_parecer
  - Adiciona colunas `rodada_atual` e `status_global` em pareceres
  - Cria tabela rodadas_avaliacao (append-only, histórico imutável)
  - Data migration: converte análises existentes na Rodada 1 de cada item
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c2d9e1f83a47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ DDL --

    op.add_column(
        "itens_parecer",
        sa.Column(
            "estado",
            sa.String(25),
            nullable=False,
            server_default="ABERTO",
        ),
    )
    op.create_check_constraint(
        "ck_item_estado",
        "itens_parecer",
        "estado IN ('ABERTO','PENDENTE_FORNECEDOR','EM_REAVALIACAO','RESOLVIDO','ESCALONADO')",
    )

    op.add_column(
        "pareceres",
        sa.Column("rodada_atual", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "pareceres",
        sa.Column(
            "status_global",
            sa.String(25),
            nullable=False,
            server_default="EM_ANALISE",
        ),
    )

    op.create_table(
        "rodadas_avaliacao",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("numero_rodada", sa.Integer(), nullable=False),
        sa.Column("origem", sa.String(30), nullable=False),
        sa.Column("conteudo", sa.Text(), nullable=True),
        sa.Column("anexo_ref", sa.String(500), nullable=True),
        sa.Column("classificacao_ia", sa.String(1), nullable=True),
        sa.Column("veredito_ia", sa.String(15), nullable=True),
        sa.Column("justificativa_ia", sa.Text(), nullable=True),
        sa.Column("acao_requerida", sa.Text(), nullable=True),
        sa.Column("decisao_humana", sa.String(15), nullable=True),
        sa.Column("revisor", sa.String(200), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["item_id"], ["itens_parecer.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "origem IN ('PROPOSTA_INICIAL','RESPOSTA_FORNECEDOR','COMENTARIO_ENGENHARIA')",
            name="ck_rodada_origem",
        ),
        sa.CheckConstraint(
            "classificacao_ia IN ('A','B','C','D','E') OR classificacao_ia IS NULL",
            name="ck_rodada_classificacao_ia",
        ),
        sa.CheckConstraint(
            "veredito_ia IN ('ATENDE','PARCIAL','NAO_ATENDE') OR veredito_ia IS NULL",
            name="ck_rodada_veredito_ia",
        ),
        sa.CheckConstraint(
            "decisao_humana IN ('ATENDE','PARCIAL','NAO_ATENDE') OR decisao_humana IS NULL",
            name="ck_rodada_decisao_humana",
        ),
    )
    op.create_index("ix_rodadas_avaliacao_item_id", "rodadas_avaliacao", ["item_id"])

    # --------------------------------------------------------- DATA MIGRATION --

    conn = op.get_bind()
    now = datetime.utcnow()

    # Busca todos os pareceres com análise concluída
    pareceres = conn.execute(
        sa.text(
            "SELECT id FROM pareceres WHERE status_processamento = 'completo'"
        )
    ).fetchall()

    for (parecer_id,) in pareceres:
        itens = conn.execute(
            sa.text(
                """
                SELECT id, status, justificativa_tecnica, acao_requerida
                FROM itens_parecer
                WHERE parecer_id = :pid
                ORDER BY numero
                """
            ),
            {"pid": parecer_id},
        ).fetchall()

        item_estados = []
        for (item_id, status, justificativa, acao) in itens:
            # Determina o estado inicial com base na classificação da IA
            estado = "RESOLVIDO" if status == "A" else "PENDENTE_FORNECEDOR"
            item_estados.append(estado)

            # Atualiza o estado do item
            conn.execute(
                sa.text(
                    "UPDATE itens_parecer SET estado = :estado WHERE id = :id"
                ),
                {"estado": estado, "id": item_id},
            )

            # Cria a Rodada 1 (PROPOSTA_INICIAL) para este item
            conn.execute(
                sa.text(
                    """
                    INSERT INTO rodadas_avaliacao
                        (id, item_id, numero_rodada, origem, conteudo,
                         classificacao_ia, justificativa_ia, acao_requerida, criado_em)
                    VALUES
                        (:id, :item_id, 1, 'PROPOSTA_INICIAL', :conteudo,
                         :classificacao_ia, :justificativa_ia, :acao_requerida, :criado_em)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "item_id": str(item_id),
                    "conteudo": justificativa,
                    "classificacao_ia": status,
                    "justificativa_ia": justificativa,
                    "acao_requerida": acao,
                    "criado_em": now,
                },
            )

        # Computa status_global do parecer
        estado_set = set(item_estados)
        if not estado_set:
            status_global = "EM_ANALISE"
        elif estado_set <= {"RESOLVIDO", "ESCALONADO"}:
            status_global = "CONCLUIDO"
        elif "EM_REAVALIACAO" in estado_set:
            status_global = "EM_REAVALIACAO"
        elif "PENDENTE_FORNECEDOR" in estado_set:
            status_global = "AGUARDANDO_FORNECEDOR"
        else:
            status_global = "EM_ANALISE"

        conn.execute(
            sa.text(
                "UPDATE pareceres SET status_global = :sg WHERE id = :id"
            ),
            {"sg": status_global, "id": parecer_id},
        )


def downgrade() -> None:
    op.drop_index("ix_rodadas_avaliacao_item_id", table_name="rodadas_avaliacao")
    op.drop_table("rodadas_avaliacao")
    op.drop_column("pareceres", "status_global")
    op.drop_column("pareceres", "rodada_atual")
    op.drop_constraint("ck_item_estado", "itens_parecer", type_="check")
    op.drop_column("itens_parecer", "estado")
