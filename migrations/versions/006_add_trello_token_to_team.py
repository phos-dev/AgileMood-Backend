"""add trello_token to team

Revision ID: 004
Revises: 003
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('team', sa.Column('trello_token', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('team', 'trello_token')
