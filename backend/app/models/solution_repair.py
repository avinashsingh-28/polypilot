"""
SolutionRepair model for PolyPilot.
Tracks AI-proposed code fixes for failing solutions and user acceptance status.
"""
import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class SolutionRepair(Base):
    __tablename__ = "solution_repairs"

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
    verification_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("verification_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("problem_artifacts.id", ondelete="SET NULL"), nullable=True)
    counterexample_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("counterexamples.id", ondelete="SET NULL"), nullable=True)
    retest_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("verification_runs.id", ondelete="SET NULL"), nullable=True)
    language: Mapped[str] = mapped_column(String(50), default="cpp", server_default="cpp", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    suspected_bug: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    original_code: Mapped[str] = mapped_column(Text, nullable=False)
    repaired_code: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="proposed", nullable=False)  # proposed, accepted, rejected

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False
    )

    verification_run: Mapped[Optional["VerificationRun"]] = relationship("VerificationRun", back_populates="repairs", foreign_keys=[verification_run_id])  # type: ignore[name-defined]

