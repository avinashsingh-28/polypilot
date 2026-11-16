"""Alembic migration 0004: verification suite, test cases, counterexamples, repairs

Revision ID: 0004_verification_suite
Revises: 0003_generation_jobs
Create Date: 2026-11-10 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0004_verification_suite"
down_revision: Union[str, None] = "0003_generation_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update verification_runs with execution metadata
    op.add_column("verification_runs", sa.Column("test_type", sa.String(50), server_default="full", nullable=False))
    op.add_column("verification_runs", sa.Column("report", JSONB, nullable=True))
    op.add_column("verification_runs", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("verification_runs", sa.Column("config_params", JSONB, nullable=True))

    # 2. test_cases table
    op.create_table(
        "test_cases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "problem_id",
            UUID(as_uuid=True),
            sa.ForeignKey("problems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("test_type", sa.String(50), server_default="manual", nullable=False),
        sa.Column("input_data", sa.Text(), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=True),
        sa.Column("is_valid", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("validation_feedback", sa.Text(), nullable=True),
        sa.Column("generator_cmd", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_test_cases_problem_id", "test_cases", ["problem_id"], if_not_exists=True)

    # 3. counterexamples table
    op.create_table(
        "counterexamples",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "problem_id",
            UUID(as_uuid=True),
            sa.ForeignKey("problems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "verification_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("verification_runs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("input_data", sa.Text(), nullable=False),
        sa.Column("ref_output", sa.Text(), nullable=False),
        sa.Column("candidate_output", sa.Text(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("minimized_input", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_counterexamples_problem_id", "counterexamples", ["problem_id"], if_not_exists=True)
    op.create_index("ix_counterexamples_run_id", "counterexamples", ["verification_run_id"], if_not_exists=True)

    # 4. solution_repairs table
    op.create_table(
        "solution_repairs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "problem_id",
            UUID(as_uuid=True),
            sa.ForeignKey("problems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "verification_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("verification_runs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("original_code", sa.Text(), nullable=False),
        sa.Column("repaired_code", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(50), server_default="proposed", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_solution_repairs_problem_id", "solution_repairs", ["problem_id"], if_not_exists=True)
    op.create_index("ix_solution_repairs_run_id", "solution_repairs", ["verification_run_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_solution_repairs_run_id", table_name="solution_repairs")
    op.drop_index("ix_solution_repairs_problem_id", table_name="solution_repairs")
    op.drop_table("solution_repairs")

    op.drop_index("ix_counterexamples_run_id", table_name="counterexamples")
    op.drop_index("ix_counterexamples_problem_id", table_name="counterexamples")
    op.drop_table("counterexamples")

    op.drop_index("ix_test_cases_problem_id", table_name="test_cases")
    op.drop_table("test_cases")

    op.drop_column("verification_runs", "config_params")
    op.drop_column("verification_runs", "error_message")
    op.drop_column("verification_runs", "report")
    op.drop_column("verification_runs", "test_type")

