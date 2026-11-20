from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, synonym
from ..database import Base

class DocumentUploadRequirement(Base):
    __tablename__ = "document_upload_requirements"
    __table_args__ = (
        Index("ix_document_requirements_status_due", "status", "due_at"),
        Index("ix_document_requirements_assigned_user", "assigned_user_id"),
        Index("ix_document_requirements_cycle_section", "academic_cycle_id", "section_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    academic_cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id"), nullable=False)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("document_requirement_sections.id", ondelete="RESTRICT"), nullable=True)
    module: Mapped[str] = mapped_column(String(120), nullable=False)
    visible_to_roles: Mapped[list] = mapped_column(JSONB, nullable=False, default=lambda: ["STUDENT"])
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    assigned_group_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    allowed_file_types: Mapped[list] = mapped_column(JSONB, nullable=False, default=lambda: ["pdf"])
    max_file_size_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reminder_days_before: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT", server_default="DRAFT")
    late_upload_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class DocumentSubmission(Base):
    __tablename__ = "document_submissions"
    __table_args__ = (
        UniqueConstraint("requirement_id", "student_id", name="uq_document_submission_requirement_student"),
        Index("ix_document_submissions_student", "student_id"),
        Index("ix_document_submissions_archive_scope", "academic_cycle_id", "group_id", "project_id"),
        Index("ix_document_submissions_requirement_status", "requirement_id", "status"),
        Index("ix_document_submissions_uploaded_at", "uploaded_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("document_upload_requirements.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=True)
    academic_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("supervisor_requests.id", ondelete="RESTRICT"), nullable=True)
    requirement_section_id: Mapped[int | None] = mapped_column(ForeignKey("document_requirement_sections.id", ondelete="RESTRICT"), nullable=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    uploader_id = synonym("uploaded_by_id")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="UPLOADED")
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    review_comment: Mapped[str | None] = mapped_column(Text)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class DocumentSubmissionVersion(Base):
    __tablename__ = "document_submission_versions"
    __table_args__ = (UniqueConstraint("submission_id", "version_number", name="uq_document_submission_version"), Index("ix_document_versions_submission", "submission_id"))
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("document_submissions.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    uploader_id = synonym("uploaded_by_id")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DocumentRequirementSection(Base):
    __tablename__ = "document_requirement_sections"
    __table_args__ = (
        UniqueConstraint("academic_cycle_id", "code", name="uq_document_requirement_section_cycle_code"),
        Index("ix_document_requirement_sections_cycle_order", "academic_cycle_id", "display_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DocumentSubmissionReviewEvent(Base):
    __tablename__ = "document_submission_review_events"
    __table_args__ = (
        Index("ix_document_review_events_submission_created", "submission_id", "created_at"),
        Index("ix_document_review_events_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("document_submissions.id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[int | None] = mapped_column(ForeignKey("document_submission_versions.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DocumentArchiveReviewQueue(Base):
    __tablename__ = "document_archive_review_queue"
    __table_args__ = (
        Index("ix_document_archive_review_queue_status_created", "status", "created_at"),
        Index("ix_document_archive_review_queue_submission", "submission_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int | None] = mapped_column(ForeignKey("document_submissions.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="OPEN", server_default="OPEN")
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
