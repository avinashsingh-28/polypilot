"""Alembic migration 0010: users' own AI provider keys

Revision ID: 0010_ai_credentials
Revises: 0009_google_sign_in
Create Date: 2026-11-22 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0010_ai_credentials"
down_revision: Union[str, None] = "0009_google_sign_in"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("ai_provider", sa.String(30), nullable=True))
    op.create_table(
        "ai_credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("key_hint", sa.String(20), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_test_ok", sa.Boolean()),
        sa.Column("last_tested_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(300)),
        sa.UniqueConstraint("user_id", "provider", name="uq_ai_credentials_user_provider"),
    )
    op.create_index("ix_ai_credentials_user_id", "ai_credentials", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_credentials_user_id", table_name="ai_credentials")
    op.drop_table("ai_credentials")
    op.drop_column("users", "ai_provider")
