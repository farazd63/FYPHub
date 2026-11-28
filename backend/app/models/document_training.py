"""Supervisor-led document training and guidance sessions."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class DocumentTrainingSession(Base):
    __tablename__ = "document_training_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('SCHEDULED','COMPLETED','CANCELLED')",
            name="ck_document_training_sessions_status",
        ),
        CheckConstraint(
            "duration_minutes >= 15 AND duration_minutes <= 480",
            name="ck_document_training_sessions_duration",
        ),
        Index("ix_document_training_sessions_team_schedule", "team_id", "scheduled_at"),
        Index("ix_document_training_sessions_requirement", "requirement_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    supervisor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    requirement_id: Mapped[int | None] = mapped_column(ForeignKey("document_upload_requirements.id", ondelete="SET NULL"), nullable=True)
    submission_id: Mapped[int | None] = mapped_column(ForeignKey("document_submissions.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default="60")
    meeting_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="SCHEDULED", server_default="SCHEDULED")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
