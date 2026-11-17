"""Phase 6: users, server-side sessions, worker heartbeats and AI usage records."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _pk():
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created():
    return mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)  # stored lowercase
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)                  # argon2id, never returned
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_at: Mapped[datetime] = _created()
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSession(Base):
    """Opaque session token (only its SHA-256 is stored). Revocable; idle + absolute expiry."""
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = _created()
    last_seen_at: Mapped[datetime] = _created()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    started_at: Mapped[datetime] = _created()
    last_seen_at: Mapped[datetime] = _created()
    state: Mapped[str] = mapped_column(String(30), default="idle", nullable=False)   # idle | busy | stopping
    current_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sandbox_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    jobs_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AIUsage(Base):
    """One AI provider call. Stores sizes and outcome only — never prompt or response content."""
    __tablename__ = "ai_usage"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
                                                         nullable=True, index=True)
    problem_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("problems.id", ondelete="SET NULL"),
                                                            nullable=True)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_chars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_chars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)       # ok | error
    error_kind: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = _created()


class PasswordResetToken(Base):
    """Single-use, short-lived password reset token. Only SHA-256(token) is stored."""
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = _created()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
