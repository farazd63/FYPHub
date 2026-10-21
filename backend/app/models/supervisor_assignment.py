from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, func, text
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

class SupervisorAssignment(Base):
    __tablename__ = "supervisor_assignments"
    __table_args__ = (
        ForeignKeyConstraint(["team_id", "academic_cycle_id"], ["teams.id", "teams.academic_cycle_id"], ondelete="RESTRICT"),
        Index("uq_supervisor_assignment_active_team", "team_id", unique=True, postgresql_where=text("ended_at IS NULL")),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(Integer, nullable=False)
    academic_cycle_id: Mapped[int] = mapped_column(Integer, nullable=False)
    supervisor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    assigned_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
