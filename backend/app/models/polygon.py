"""Phase 5 Polygon integration models. No plaintext secrets are ever stored."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid_pk():
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created():
    return mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False)


class PolygonAccount(Base):
    """Credential source + connection status. Secrets are Fernet-encrypted (source='stored') or
    live only in environment variables (source='env', encrypted columns NULL)."""
    __tablename__ = "polygon_accounts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    __table_args__ = (Index("uq_polygon_accounts_user_source", "user_id", "source", unique=True),)

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # env | stored
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    api_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_hint: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    last_test_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_ok: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    last_test_kind: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_test_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    accessible_problems: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(),
                                                 onupdate=func.now(), nullable=False)


class PolygonSyncRun(Base):
    __tablename__ = "polygon_sync_runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    problem_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("problems.id", ondelete="CASCADE"),
                                                  nullable=False, index=True)
    integration_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("problem_integrations.id", ondelete="SET NULL"), nullable=True)
    # dry_run | sync | commit | build | create | link | working_copy
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    # planned | running | completed | partial | failed | unknown
    status: Mapped[str] = mapped_column(String(30), default="planned", nullable=False)
    scope: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    plan: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _created()
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class PolygonOperation(Base):
    """One Polygon API request (secret-free)."""
    __tablename__ = "polygon_operations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    problem_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("problems.id", ondelete="CASCADE"), nullable=True, index=True)
    sync_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("polygon_sync_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    method: Mapped[str] = mapped_column(String(80), nullable=False)
    write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    params: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)  # ok | failed | ambiguous
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_kind: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _created()


class PolygonItemState(Base):
    """Last confirmed remote state of one local item (artifact, statement, test, setting)."""
    __tablename__ = "polygon_item_states"
    __table_args__ = (Index("uq_polygon_item_states_key", "integration_id", "item_key", unique=True),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    problem_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("problems.id", ondelete="CASCADE"),
                                                  nullable=False, index=True)
    integration_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("problem_integrations.id", ondelete="CASCADE"), nullable=False)
    item_key: Mapped[str] = mapped_column(String(200), nullable=False)
    item_type: Mapped[str] = mapped_column(String(30), nullable=False)
    local_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    local_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    local_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    remote_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    remote_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    remote_meta: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)  # uploaded|failed|unknown|pending
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(),
                                                 onupdate=func.now(), nullable=False)
