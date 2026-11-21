"""Supervisor departure and administrator-led replacement records."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class SupervisorDeparture(Base):
    __tablename__ = "supervisor_departures"
    __table_args__ = (
        Index("uq_supervisor_departures_active", "supervisor_id", unique=True, postgresql_where=text("active = true")),
        Index("ix_supervisor_departures_supervisor_active", "supervisor_id", "active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supervisor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    marked_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    marked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)


class SupervisorReplacementCase(Base):
    __tablename__ = "supervisor_replacement_cases"
    __table_args__ = (
        Index("ix_supervisor_replacement_cases_status", "status", "opened_at"),
        Index("ix_supervisor_replacement_cases_team", "team_id", "academic_cycle_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    academic_cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False)
    previous_assignment_id: Mapped[int] = mapped_column(ForeignKey("supervisor_assignments.id", ondelete="RESTRICT"), nullable=False)
    previous_supervisor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    replacement_assignment_id: Mapped[int | None] = mapped_column(ForeignKey("supervisor_assignments.id", ondelete="SET NULL"), nullable=True)
    replacement_supervisor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNSUPERVISED", server_default="UNSUPERVISED")
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    assigned_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    reassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
