"""add jira fields to team

Revision ID: 007
Revises: 006
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('team', sa.Column('jira_token', sa.String(), nullable=True))
    op.add_column('team', sa.Column('jira_cloud_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('team', 'jira_cloud_id')
    op.drop_column('team', 'jira_token')
