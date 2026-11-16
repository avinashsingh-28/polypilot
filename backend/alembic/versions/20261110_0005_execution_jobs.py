"""Alembic migration 0005: execution job management, test metadata, repair versioning

Revision ID: 0005_execution_jobs
Revises: 0004_verification_suite
Create Date: 2026-11-10 20:00:00.000000

Additive only: no existing rows are modified except test_cases.is_valid default
(which only affects new rows; validation_status starts as 'unchecked').
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0005_execution_jobs"
down_revision: Union[str, None] = "0004_verification_suite"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # verification_runs: job management
    op.add_column("verification_runs", sa.Column("progress", JSONB, nullable=True))
    op.add_column("verification_runs", sa.Column("logs", sa.Text(), nullable=True))
    op.add_column("verification_runs", sa.Column("cancel_requested", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("verification_runs", sa.Column("idempotency_key", sa.String(100), nullable=True))
    op.add_column("verification_runs", sa.Column("worker_id", sa.String(100), nullable=True))
    op.add_column("verification_runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("uq_verification_runs_idempotency", "verification_runs",
                    ["problem_id", "idempotency_key"], unique=True)
    op.create_index("ix_verification_runs_status", "verification_runs", ["status"])

    # test_cases: validation state + generation metadata
    op.add_column("test_cases", sa.Column("validation_status", sa.String(20), server_default="unchecked", nullable=False))
    op.add_column("test_cases", sa.Column("generation_meta", JSONB, nullable=True))
    op.add_column("test_cases", sa.Column("input_bytes", sa.Integer(), server_default="0", nullable=False))
    op.alter_column("test_cases", "is_valid", server_default=sa.text("false"))

    # counterexamples: failure classification
    op.add_column("counterexamples", sa.Column("kind", sa.String(50), server_default="mismatch", nullable=False))
    op.add_column("counterexamples", sa.Column("details", JSONB, nullable=True))

    # solution_repairs: links + versioning
    op.add_column("solution_repairs", sa.Column("artifact_id", UUID(as_uuid=True),
                  sa.ForeignKey("problem_artifacts.id", ondelete="SET NULL"), nullable=True))
    op.add_column("solution_repairs", sa.Column("counterexample_id", UUID(as_uuid=True),
                  sa.ForeignKey("counterexamples.id", ondelete="SET NULL"), nullable=True))
    op.add_column("solution_repairs", sa.Column("retest_run_id", UUID(as_uuid=True),
                  sa.ForeignKey("verification_runs.id", ondelete="SET NULL"), nullable=True))
    op.add_column("solution_repairs", sa.Column("language", sa.String(50), server_default="cpp", nullable=False))
    op.add_column("solution_repairs", sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    op.add_column("solution_repairs", sa.Column("suspected_bug", sa.Text(), nullable=True))


def downgrade() -> None:
    for col in ("suspected_bug", "version", "language", "retest_run_id", "counterexample_id", "artifact_id"):
        op.drop_column("solution_repairs", col)
    op.drop_column("counterexamples", "details")
    op.drop_column("counterexamples", "kind")
    op.alter_column("test_cases", "is_valid", server_default=sa.text("true"))
    for col in ("input_bytes", "generation_meta", "validation_status"):
        op.drop_column("test_cases", col)
    op.drop_index("ix_verification_runs_status", table_name="verification_runs")
    op.drop_index("uq_verification_runs_idempotency", table_name="verification_runs")
    for col in ("heartbeat_at", "worker_id", "idempotency_key", "cancel_requested", "logs", "progress"):
        op.drop_column("verification_runs", col)
