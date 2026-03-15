"""add mensagens_chat table

Revision ID: a3f7c8e91d02
Revises: 1948b5233ff1
Create Date: 2026-02-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f7c8e91d02'
down_revision: Union[str, Sequence[str], None] = '1948b5233ff1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('mensagens_chat',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('parecer_id', sa.Uuid(), nullable=False),
        sa.Column('usuario_id', sa.Uuid(), nullable=True),
        sa.Column('papel', sa.String(length=20), nullable=False),
        sa.Column('conteudo', sa.Text(), nullable=False),
        sa.Column('ordem', sa.Integer(), nullable=False),
        sa.Column('tokens_entrada', sa.Integer(), nullable=True),
        sa.Column('tokens_saida', sa.Integer(), nullable=True),
        sa.Column('gerou_nova_tabela', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('criado_em', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['parecer_id'], ['pareceres.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mensagens_chat_parecer_id', 'mensagens_chat', ['parecer_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_mensagens_chat_parecer_id', table_name='mensagens_chat')
    op.drop_table('mensagens_chat')
