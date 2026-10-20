"""Non-operational reminder and escalation rule snapshots."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

class ReminderRule(Base):
    __tablename__ = "reminder_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    academic_cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class ReminderRuleVersion(Base):
    __tablename__ = "reminder_rule_versions"
    __table_args__ = (UniqueConstraint("rule_id", "version_number", name="uq_reminder_rule_version"), CheckConstraint("elapsed_minutes > 0", name="ck_reminder_rule_minutes"), CheckConstraint("category IN ('REMINDER', 'ESCALATION')", name="ck_reminder_rule_category"), CheckConstraint("direction IN ('BEFORE', 'AFTER')", name="ck_reminder_rule_direction"))
    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("reminder_rules.id", ondelete="RESTRICT"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline_version_id: Mapped[int] = mapped_column(ForeignKey("academic_deadline_versions.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    direction: Mapped[str] = mapped_column(String(6), nullable=False)
    elapsed_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
