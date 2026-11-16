"""Alembic migration 0006: Polygon integration (Phase 5)

Revision ID: 0006_polygon_integration
Revises: 0005_execution_jobs
Create Date: 2026-11-13 12:00:00.000000

Also repairs a pre-existing schema drift: some databases have problem_integrations.external_id
instead of external_problem_id (the column the model and migration 0001 define). The column is
renamed in place, preserving data.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0006_polygon_integration"
down_revision: Union[str, None] = "0005_execution_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    cols = _columns("problem_integrations")
    if "external_problem_id" not in cols and "external_id" in cols:
        op.alter_column("problem_integrations", "external_id", new_column_name="external_problem_id",
                        existing_type=sa.String(100))
    elif "external_problem_id" not in cols:
        op.add_column("problem_integrations", sa.Column("external_problem_id", sa.String(100), nullable=True))

    for name, typ in (("remote_name", sa.String(255)), ("remote_owner", sa.String(100)), ("access_type", sa.String(20)),
                      ("remote_revision", sa.Integer()), ("working_copy_revision", sa.Integer()),
                      ("remote_modified", sa.Boolean()), ("link_mode", sa.String(20)), ("pending_create", JSONB),
                      ("last_remote_check_at", sa.DateTime(timezone=True)), ("last_synced_at", sa.DateTime(timezone=True)),
                      ("last_commit", JSONB), ("last_build", JSONB)):
        op.add_column("problem_integrations", sa.Column(name, typ, nullable=True))
    op.create_index("uq_problem_integrations_problem_platform", "problem_integrations",
                    ["problem_id", "platform_name"], unique=True)
    op.create_index("uq_problem_integrations_external", "problem_integrations",
                    ["platform_name", "external_problem_id"], unique=True)

    ts = lambda n, nullable=True: sa.Column(n, sa.DateTime(timezone=True), nullable=nullable)  # noqa: E731
    op.create_table(
        "polygon_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(20), nullable=False, unique=True),
        sa.Column("api_key_encrypted", sa.Text()), sa.Column("api_secret_encrypted", sa.Text()),
        sa.Column("key_hint", sa.String(20)), ts("last_test_at"), sa.Column("last_test_ok", sa.Boolean()),
        sa.Column("last_test_kind", sa.String(50)), sa.Column("last_test_message", sa.Text()), ts("last_success_at"),
        sa.Column("accessible_problems", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "polygon_sync_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("problem_id", UUID(as_uuid=True), sa.ForeignKey("problems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_id", UUID(as_uuid=True), sa.ForeignKey("problem_integrations.id", ondelete="SET NULL")),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="planned"),
        sa.Column("scope", JSONB), sa.Column("plan", JSONB), sa.Column("result", JSONB), sa.Column("summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        ts("started_at"), ts("completed_at"),
    )
    op.create_index("ix_polygon_sync_runs_problem_id", "polygon_sync_runs", ["problem_id"])
    op.create_table(
        "polygon_operations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("problem_id", UUID(as_uuid=True), sa.ForeignKey("problems.id", ondelete="CASCADE")),
        sa.Column("sync_run_id", UUID(as_uuid=True), sa.ForeignKey("polygon_sync_runs.id", ondelete="CASCADE")),
        sa.Column("method", sa.String(80), nullable=False),
        sa.Column("write", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("params", JSONB), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("http_status", sa.Integer()), sa.Column("duration_ms", sa.Integer()),
        sa.Column("response_summary", sa.Text()), sa.Column("error_kind", sa.String(50)), sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_polygon_operations_problem_id", "polygon_operations", ["problem_id"])
    op.create_index("ix_polygon_operations_sync_run_id", "polygon_operations", ["sync_run_id"])
    op.create_table(
        "polygon_item_states",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("problem_id", UUID(as_uuid=True), sa.ForeignKey("problems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_id", UUID(as_uuid=True), sa.ForeignKey("problem_integrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_key", sa.String(200), nullable=False), sa.Column("item_type", sa.String(30), nullable=False),
        sa.Column("local_ref", sa.String(100)), sa.Column("local_version", sa.Integer()), sa.Column("local_hash", sa.String(64)),
        sa.Column("remote_name", sa.String(200)), sa.Column("remote_index", sa.Integer()), sa.Column("remote_meta", JSONB),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"), sa.Column("error", sa.Text()),
        ts("uploaded_at"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_polygon_item_states_problem_id", "polygon_item_states", ["problem_id"])
    op.create_index("uq_polygon_item_states_key", "polygon_item_states", ["integration_id", "item_key"], unique=True)


def downgrade() -> None:
    op.drop_table("polygon_item_states")
    op.drop_table("polygon_operations")
    op.drop_table("polygon_sync_runs")
    op.drop_table("polygon_accounts")
    op.drop_index("uq_problem_integrations_external", table_name="problem_integrations")
    op.drop_index("uq_problem_integrations_problem_platform", table_name="problem_integrations")
    for name in ("last_build", "last_commit", "last_synced_at", "last_remote_check_at", "pending_create", "link_mode",
                 "remote_modified", "working_copy_revision", "remote_revision", "access_type", "remote_owner", "remote_name"):
        op.drop_column("problem_integrations", name)
    # external_problem_id is kept (it is the column defined by migration 0001).
