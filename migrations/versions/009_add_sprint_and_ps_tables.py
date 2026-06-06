"""add sprint and psychological safety tables

Revision ID: 009
Revises: 008
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sprint',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('team_id', sa.Integer, sa.ForeignKey('team.id'), nullable=False),
        sa.Column('sprint_number', sa.Integer, nullable=False),
        sa.Column('jira_sprint_id', sa.Text, nullable=True),
        sa.Column('start_date', sa.DateTime, nullable=True),
        sa.Column('end_date', sa.DateTime, nullable=True),
        sa.UniqueConstraint('team_id', 'sprint_number', name='uq_sprint_team_number'),
    )
    op.create_table(
        'ps_response',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('sprint_id', sa.Integer, sa.ForeignKey('sprint.id'), nullable=False),
        sa.Column('answers', sa.JSON, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        'ps_deduplication',
        sa.Column('user_id', sa.Integer, sa.ForeignKey('user.id'), nullable=False),
        sa.Column('sprint_id', sa.Integer, sa.ForeignKey('sprint.id'), nullable=False),
        sa.Column('answered_at', sa.DateTime, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('user_id', 'sprint_id', name='pk_ps_dedup'),
    )


def downgrade() -> None:
    op.drop_table('ps_deduplication')
    op.drop_table('ps_response')
    op.drop_table('sprint')
