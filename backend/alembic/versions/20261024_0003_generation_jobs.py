"""
Alembic migration 0003: generation_jobs table
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0003_generation_jobs"
down_revision = "002_problem_specification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "problem_id",
            UUID(as_uuid=True),
            sa.ForeignKey("problems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("current_step", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_steps", sa.Integer, nullable=False, server_default="7"),
        sa.Column("current_step_name", sa.String(100), nullable=True),
        sa.Column("steps_log", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_generation_jobs_problem_id",
        "generation_jobs",
        ["problem_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_generation_jobs_problem_id", table_name="generation_jobs")
    op.drop_table("generation_jobs")
