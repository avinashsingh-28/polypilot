import uuid
from typing import Optional, List
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Uuid, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class VerificationRun(Base):
    __tablename__ = "verification_runs"
    __table_args__ = (
        Index("uq_verification_runs_idempotency", "problem_id", "idempotency_key", unique=True),
        Index("ix_verification_runs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    problem_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    test_type: Mapped[str] = mapped_column(String(50), default="full", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config_params: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Phase 4 job management
    progress: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    worker_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    problem: Mapped["Problem"] = relationship("Problem", back_populates="verification_runs")  # type: ignore[name-defined]
    counterexamples: Mapped[List["Counterexample"]] = relationship(  # type: ignore[name-defined]
        "Counterexample",
        back_populates="verification_run",
        cascade="all, delete-orphan",
        order_by="Counterexample.created_at.desc()"
    )
    repairs: Mapped[List["SolutionRepair"]] = relationship(  # type: ignore[name-defined]
        "SolutionRepair",
        back_populates="verification_run",
        cascade="all, delete-orphan",
        foreign_keys="SolutionRepair.verification_run_id",
        order_by="SolutionRepair.created_at.desc()"
    )

