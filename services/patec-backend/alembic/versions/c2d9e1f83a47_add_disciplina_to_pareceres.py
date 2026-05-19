"""add disciplina to pareceres

Revision ID: c2d9e1f83a47
Revises: a3f7c8e91d02
Create Date: 2026-05-19

"""
from alembic import op
import sqlalchemy as sa

revision = 'c2d9e1f83a47'
down_revision = 'b7e2f4a91c03'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'pareceres',
        sa.Column('disciplina', sa.String(30), nullable=False, server_default='instrumentacao'),
    )


def downgrade() -> None:
    op.drop_column('pareceres', 'disciplina')
