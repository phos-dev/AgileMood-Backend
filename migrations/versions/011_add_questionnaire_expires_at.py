"""separate questionnaire_expires_at from sprint end_date

Revision ID: 011
Revises: 010
Create Date: 2026-06-07
"""
from alembic import op
import sqlalchemy as sa

revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sprint', sa.Column('questionnaire_expires_at', sa.DateTime, nullable=True))
    # Backfill: existing rows used end_date as the 48h questionnaire window
    op.execute("UPDATE sprint SET questionnaire_expires_at = end_date WHERE questionnaire_expires_at IS NULL")
    # Fix end_date for existing rows: it was set to start_date+48h, reset to start_date (≈ close time)
    op.execute("UPDATE sprint SET end_date = start_date WHERE end_date IS NOT NULL")


def downgrade() -> None:
    op.drop_column('sprint', 'questionnaire_expires_at')
