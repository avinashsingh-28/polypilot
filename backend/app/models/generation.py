"""
GenerationJob SQLAlchemy model.
Tracks the status and step-by-step log of a problem generation run.
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, DateTime, Uuid, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    problem_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Job lifecycle
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False
    )  # pending | running | completed | failed
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_steps: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    current_step_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Structured log: list of {step, name, status, started_at, completed_at, error?}
    steps_log: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship back to problem (no back_populates needed here)
    problem: Mapped["Problem"] = relationship("Problem", foreign_keys=[problem_id])  # type: ignore[name-defined]

