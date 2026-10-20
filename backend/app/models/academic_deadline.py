"""Non-operational academic deadline configuration models."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class AcademicDeadline(Base):
    """Stable deadline identity fixed to one academic cycle."""

    __tablename__ = "academic_deadlines"

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    versions: Mapped[list["AcademicDeadlineVersion"]] = relationship(back_populates="deadline")


class AcademicDeadlineVersion(Base):
    """An immutable recorded deadline configuration."""

    __tablename__ = "academic_deadline_versions"
    __table_args__ = (
        UniqueConstraint("academic_deadline_id", "version_number", name="uq_academic_deadline_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_deadline_id: Mapped[int] = mapped_column(ForeignKey("academic_deadlines.id", ondelete="RESTRICT"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    time_zone: Mapped[str] = mapped_column(String(100), nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deadline: Mapped[AcademicDeadline] = relationship(back_populates="versions")
