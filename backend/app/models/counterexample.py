"""
Counterexample model for PolyPilot.
Records failing test cases discovered during differential and stress testing.
"""
import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Counterexample(Base):
    __tablename__ = "counterexamples"

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
    input_data: Mapped[str] = mapped_column(Text, nullable=False)
    ref_output: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_output: Mapped[str] = mapped_column(Text, nullable=False)
    seed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    minimized_input: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # mismatch | candidate_failure | reference_failure | brute_failure
    kind: Mapped[str] = mapped_column(String(50), default="mismatch", server_default="mismatch", nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False
    )

    verification_run: Mapped[Optional["VerificationRun"]] = relationship("VerificationRun", back_populates="counterexamples")  # type: ignore[name-defined]

