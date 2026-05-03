"""add teams_user_id to user

Revision ID: 005
Revises: 004
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('user', sa.Column('teams_user_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('user', 'teams_user_id')
