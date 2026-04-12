"""replace slack_webhook_url with slack_bot_token on team

Revision ID: 002
Revises: 001
Create Date: 2026-04-12
"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('team', 'slack_webhook_url')
    op.add_column('team', sa.Column('slack_bot_token', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('team', 'slack_bot_token')
    op.add_column('team', sa.Column('slack_webhook_url', sa.String(), nullable=True))
