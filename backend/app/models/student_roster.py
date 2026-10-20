"""Approved roster import provenance and cycle-scoped student records."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

class RosterImport(Base):
    __tablename__ = "roster_imports"
    id: Mapped[int] = mapped_column(primary_key=True)
    academic_cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False)
    imported_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    confirmation_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class ApprovedStudent(Base):
    __tablename__ = "approved_students"
    __table_args__ = (Index("uq_approved_student_cycle_registration", "academic_cycle_id", text("lower(registration_number)"), unique=True), UniqueConstraint("academic_cycle_id", "university_email", name="uq_approved_student_cycle_email"), CheckConstraint("semester IN (7, 8)", name="ck_approved_student_semester"))
    id: Mapped[int] = mapped_column(primary_key=True)
    academic_cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False)
    import_id: Mapped[int] = mapped_column(ForeignKey("roster_imports.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    registration_number: Mapped[str] = mapped_column(String(100), nullable=False)
    university_email: Mapped[str] = mapped_column(String(320), nullable=False)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    group_code: Mapped[str] = mapped_column(String(100), nullable=False)
    project_topic: Mapped[str | None] = mapped_column(Text)
