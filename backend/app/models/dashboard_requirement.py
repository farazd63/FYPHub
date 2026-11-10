"""Role-scoped dashboard deadline and requirement records."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

class DashboardRequirement(Base):
    __tablename__ = "dashboard_requirements"
    __table_args__ = (Index("ix_dashboard_requirements_cycle", "academic_cycle_id"), Index("ix_dashboard_requirements_user", "assigned_user_id"), Index("ix_dashboard_requirements_status_due", "status", "due_at"))
    id: Mapped[int] = mapped_column(primary_key=True)
    academic_deadline_id: Mapped[int | None] = mapped_column(ForeignKey("academic_deadlines.id", ondelete="RESTRICT"), nullable=True)
    academic_cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    requirement_type: Mapped[str] = mapped_column(String(24), nullable=False)
    module: Mapped[str] = mapped_column(String(120), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, server_default="MEDIUM")
    role_visibility: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assigned_group_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completion_percent: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="UPCOMING")
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
