"""add sprint_name column to sprint table

Revision ID: 010
Revises: 009
Create Date: 2026-06-07
"""
from alembic import op
import sqlalchemy as sa

revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sprint', sa.Column('sprint_name', sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column('sprint', 'sprint_name')
