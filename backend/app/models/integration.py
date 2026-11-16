import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import Boolean, String, DateTime, ForeignKey, Index, Integer, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class ProblemIntegration(Base):
    __tablename__ = "problem_integrations"
    __table_args__ = (
        Index("uq_problem_integrations_problem_platform", "problem_id", "platform_name", unique=True),
        Index("uq_problem_integrations_external", "platform_name", "external_problem_id", unique=True),
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
    platform_name: Mapped[str] = mapped_column(String(50), default="polygon", nullable=False)
    external_problem_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # unlinked | creating | create_unknown | linked | syncing | synced | partial | failed
    sync_status: Mapped[str] = mapped_column(String(50), default="unlinked", nullable=False)

    # Phase 5: remote problem metadata (from problems.list / problem.info responses)
    remote_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    remote_owner: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    access_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    remote_revision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    working_copy_revision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    remote_modified: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    link_mode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # created | linked
    pending_create: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    last_remote_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_commit: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    last_build: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

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
    problem: Mapped["Problem"] = relationship("Problem", back_populates="integrations")
