"""initial tables

Revision ID: 0001_initial_tables
Revises: 
Create Date: 2026-10-24 01:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001_initial_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. problems table
    op.create_table(
        'problems',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('idea', sa.Text(), nullable=True),
        sa.Column('algorithm', sa.String(length=255), nullable=True),
        sa.Column('constraints_text', sa.Text(), nullable=True),
        sa.Column('input_format', sa.Text(), nullable=True),
        sa.Column('output_format', sa.Text(), nullable=True),
        sa.Column('time_limit_seconds', sa.Numeric(precision=5, scale=2), server_default='2.0', nullable=True),
        sa.Column('memory_limit_mb', sa.Integer(), server_default='256', nullable=True),
        sa.Column('difficulty', sa.String(length=100), nullable=True),
        sa.Column('language', sa.String(length=50), server_default='cpp', nullable=False),
        sa.Column('status', sa.String(length=50), server_default='draft', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_problems_slug'), 'problems', ['slug'], unique=True)

    # 2. problem_artifacts table
    op.create_table(
        'problem_artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('problem_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('problems.id', ondelete='CASCADE'), nullable=False),
        sa.Column('artifact_type', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('content', sa.Text(), server_default='', nullable=False),
        sa.Column('language', sa.String(length=50), nullable=True),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_problem_artifacts_problem_id'), 'problem_artifacts', ['problem_id'], unique=False)

    # 3. verification_runs table
    op.create_table(
        'verification_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('problem_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('problems.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_verification_runs_problem_id'), 'verification_runs', ['problem_id'], unique=False)

    # 4. problem_integrations table
    op.create_table(
        'problem_integrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('problem_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('problems.id', ondelete='CASCADE'), nullable=False),
        sa.Column('platform_name', sa.String(length=50), server_default='polygon', nullable=False),
        sa.Column('external_problem_id', sa.String(length=100), nullable=True),
        sa.Column('sync_status', sa.String(length=50), server_default='unlinked', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_problem_integrations_problem_id'), 'problem_integrations', ['problem_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_problem_integrations_problem_id'), table_name='problem_integrations')
    op.drop_table('problem_integrations')
    op.drop_index(op.f('ix_verification_runs_problem_id'), table_name='verification_runs')
    op.drop_table('verification_runs')
    op.drop_index(op.f('ix_problem_artifacts_problem_id'), table_name='problem_artifacts')
    op.drop_table('problem_artifacts')
    op.drop_index(op.f('ix_problems_slug'), table_name='problems')
    op.drop_table('problems')
