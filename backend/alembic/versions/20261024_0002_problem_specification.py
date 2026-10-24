"""add problem_specifications table

Revision ID: 002_problem_specification
Revises: 0001_initial_tables
Create Date: 2026-10-24 02:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '002_problem_specification'
down_revision: Union[str, None] = '0001_initial_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'problem_specifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'problem_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('problems.id', ondelete='CASCADE'),
            nullable=False
        ),
        sa.Column('specification_json', sa.JSON(), nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False
        ),
    )
    op.create_index(
        op.f('ix_problem_specifications_problem_id'),
        'problem_specifications',
        ['problem_id'],
        unique=True
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_problem_specifications_problem_id'),
        table_name='problem_specifications'
    )
    op.drop_table('problem_specifications')
