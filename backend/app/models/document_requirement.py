from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

class DocumentUploadRequirement(Base):
    __tablename__ = "document_upload_requirements"
    __table_args__ = (Index("ix_document_requirements_status_due", "status", "due_at"), Index("ix_document_requirements_assigned_user", "assigned_user_id"))
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    academic_cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id"), nullable=False)
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
    __table_args__ = (UniqueConstraint("requirement_id", "student_id", name="uq_document_submission_requirement_student"), Index("ix_document_submissions_student", "student_id"))
    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("document_upload_requirements.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=True)
    academic_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
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
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
