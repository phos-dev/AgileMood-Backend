"""add slack_webhook_url to team

Revision ID: 001
Revises:
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('team', sa.Column('slack_webhook_url', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('team', 'slack_webhook_url')
