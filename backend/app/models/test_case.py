"""
TestCase model for PolyPilot.
Stores sample, manual, boundary, and generator-produced test cases for problems.
"""
import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Text, Boolean, Integer, DateTime, ForeignKey, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class TestCase(Base):
    __tablename__ = "test_cases"
    __test__ = False  # not a pytest test class

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
    test_type: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    input_data: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # is_valid is True only after the sandboxed validator accepted the input.
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(20), default="unchecked", server_default="unchecked", nullable=False)  # unchecked|valid|invalid|error
    validation_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generator_cmd: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    generation_meta: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    input_bytes: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False
    )

    problem: Mapped["Problem"] = relationship("Problem", foreign_keys=[problem_id])  # type: ignore[name-defined]

