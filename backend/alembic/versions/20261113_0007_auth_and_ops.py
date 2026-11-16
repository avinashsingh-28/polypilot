"""Alembic migration 0007: authentication, ownership, worker heartbeats, AI usage (Phase 6)

Revision ID: 0007_auth_and_ops
Revises: 0006_polygon_integration
Create Date: 2026-11-13 18:00:00.000000

Non-destructive:
  * problems.owner_id is added as NULLable; existing problems stay unowned (not visible to any
    user) until claimed with `python -m app.cli claim-problems --email you@example.com`.
  * polygon_accounts gains user_id; existing rows keep user_id NULL (ignored by the API).
  * Relaxes pre-existing NOT NULL drift on problems.idea/difficulty/time_limit_seconds/
    memory_limit_mb so the database matches the ORM model (no data is changed).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0007_auth_and_ops"
down_revision: Union[str, None] = "0006_polygon_integration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _now():
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _now(),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "user_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        _now(),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("user_agent", sa.String(200)),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])

    op.add_column("problems", sa.Column("owner_id", UUID(as_uuid=True),
                                        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True))
    op.create_index("ix_problems_owner_id", "problems", ["owner_id"])
    for col, typ in (("idea", sa.Text()), ("difficulty", sa.String(100)),
                     ("time_limit_seconds", sa.Numeric(5, 2)), ("memory_limit_mb", sa.Integer())):
        op.alter_column("problems", col, existing_type=typ, nullable=True)

    op.add_column("polygon_accounts", sa.Column("user_id", UUID(as_uuid=True),
                                                sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True))
    op.drop_constraint("polygon_accounts_source_key", "polygon_accounts", type_="unique")
    op.create_index("ix_polygon_accounts_user_id", "polygon_accounts", ["user_id"])
    op.create_index("uq_polygon_accounts_user_source", "polygon_accounts", ["user_id", "source"], unique=True)

    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(120), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("state", sa.String(30), nullable=False, server_default="idle"),
        sa.Column("current_run_id", sa.String(64)),
        sa.Column("sandbox_available", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("jobs_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_failed", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "ai_usage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("problem_id", UUID(as_uuid=True), sa.ForeignKey("problems.id", ondelete="SET NULL")),
        sa.Column("purpose", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("prompt_chars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("response_chars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_kind", sa.String(50)),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        _now(),
    )
    op.create_index("ix_ai_usage_user_id", "ai_usage", ["user_id"])
    op.create_index("ix_ai_usage_created_at", "ai_usage", ["created_at"])
    # Frequently filtered columns
    op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_generation_jobs_status", table_name="generation_jobs", if_exists=True)
    op.drop_table("ai_usage")
    op.drop_table("worker_heartbeats")
    op.drop_index("uq_polygon_accounts_user_source", table_name="polygon_accounts")
    op.drop_index("ix_polygon_accounts_user_id", table_name="polygon_accounts")
    op.create_unique_constraint("polygon_accounts_source_key", "polygon_accounts", ["source"])
    op.drop_column("polygon_accounts", "user_id")
    op.drop_index("ix_problems_owner_id", table_name="problems")
    op.drop_column("problems", "owner_id")
    # NOT NULL drift on problems.* is intentionally not re-applied.
    op.drop_table("user_sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
