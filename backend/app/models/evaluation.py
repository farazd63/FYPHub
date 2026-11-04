"""Persisted role-owned FYP evaluation records and result audit history."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class EvaluationRecord(Base):
    __tablename__ = "evaluation_records"
    __table_args__ = (
        CheckConstraint(
            "(student_id IS NOT NULL AND group_id IS NULL) OR (student_id IS NULL AND group_id IS NOT NULL)",
            name="ck_evaluation_one_target",
        ),
        CheckConstraint(
            "evaluation_category IN ('FINAL_PRESENTATION','MID_REVIEW','SUPERVISOR_EVALUATION','PROJECT_DOCUMENTATION','PROPOSAL')",
            name="ck_evaluation_category",
        ),
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','RETURNED','APPROVED','PUBLISHED')",
            name="ck_evaluation_status",
        ),
        CheckConstraint(
            "obtained_marks IS NULL OR (obtained_marks >= 0 AND obtained_marks <= maximum_marks)",
            name="ck_evaluation_marks_range",
        ),
        CheckConstraint("maximum_marks IN (30, 10, 20)", name="ck_evaluation_maximum"),
        UniqueConstraint("student_id", "evaluation_category", "evaluator_id", name="uq_evaluation_student_category_evaluator"),
        UniqueConstraint("group_id", "evaluation_category", "evaluator_id", name="uq_evaluation_group_category_evaluator"),
        Index("ix_evaluation_records_category_status", "evaluation_category", "status"),
        Index("ix_evaluation_records_evaluator", "evaluator_id", "status"),
        Index("ix_evaluation_records_student", "student_id"),
        Index("ix_evaluation_records_group", "group_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=True)
    evaluator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    evaluator_role: Mapped[str] = mapped_column(String(32), nullable=False)
    evaluation_category: Mapped[str] = mapped_column(String(32), nullable=False)
    maximum_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    obtained_marks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT", server_default="DRAFT")
    returned_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class EvaluationAuditEvent(Base):
    __tablename__ = "evaluation_audit_events"
    __table_args__ = (Index("ix_evaluation_audit_record_created", "evaluation_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("evaluation_records.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    previous_marks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_marks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_values: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EvaluationCorrection(Base):
    __tablename__ = "evaluation_corrections"
    __table_args__ = (Index("ix_evaluation_corrections_evaluation", "evaluation_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("evaluation_records.id", ondelete="RESTRICT"), nullable=False)
    authorized_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    previous_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    new_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EvaluationAggregationConfig(Base):
    __tablename__ = "evaluation_aggregation_configs"
    __table_args__ = (
        CheckConstraint("evaluation_category IN ('FINAL_PRESENTATION','MID_REVIEW')", name="ck_evaluation_aggregation_category"),
        CheckConstraint("method IN ('AVERAGE','MAXIMUM','MEDIAN')", name="ck_evaluation_aggregation_method"),
        UniqueConstraint("evaluation_category", name="uq_evaluation_aggregation_category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_category: Mapped[str] = mapped_column(String(32), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="AVERAGE", server_default="AVERAGE")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
