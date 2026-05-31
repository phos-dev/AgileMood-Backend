"""add planner_subscription_id to team

Revision ID: 008
Revises: 007
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('team', sa.Column('planner_subscription_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('team', 'planner_subscription_id')
