"""add slack_user_id to user

Revision ID: 003
Revises: 002
Create Date: 2026-04-12
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('user', sa.Column('slack_user_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('user', 'slack_user_id')
