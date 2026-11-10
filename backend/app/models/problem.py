import uuid
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Text, Integer, Numeric, DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    idea: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    algorithm: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    constraints_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_format: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_format: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    time_limit_seconds: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), default=Decimal("2.0"), nullable=True)
    memory_limit_mb: Mapped[Optional[int]] = mapped_column(Integer, default=256, nullable=True)
    difficulty: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language: Mapped[str] = mapped_column(String(50), default="cpp", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    artifacts: Mapped[List["ProblemArtifact"]] = relationship(
        "ProblemArtifact",
        back_populates="problem",
        cascade="all, delete-orphan",
        order_by="ProblemArtifact.version.desc()"
    )
    verification_runs: Mapped[List["VerificationRun"]] = relationship(
        "VerificationRun",
        back_populates="problem",
        cascade="all, delete-orphan",
        order_by="VerificationRun.created_at.desc()"
    )
    integrations: Mapped[List["ProblemIntegration"]] = relationship(
        "ProblemIntegration",
        back_populates="problem",
        cascade="all, delete-orphan"
    )
