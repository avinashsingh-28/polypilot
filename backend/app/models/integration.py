import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class ProblemIntegration(Base):
    __tablename__ = "problem_integrations"

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
    sync_status: Mapped[str] = mapped_column(String(50), default="unlinked", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    problem: Mapped["Problem"] = relationship("Problem", back_populates="integrations")
