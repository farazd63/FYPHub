"""Student supervisor-selection request records and append-only history."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, LargeBinary, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class SupervisorRequestStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class SupervisorRequestExtractionStatus(StrEnum):
    PENDING = "PENDING"
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"
    CONFIRMED = "CONFIRMED"


class SupervisorRequest(Base):
    __tablename__ = "supervisor_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "academic_cycle_id"],
            ["teams.id", "teams.academic_cycle_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("revision > 0", name="ck_supervisor_requests_revision_positive"),
        CheckConstraint("title IS NULL OR (title = btrim(title) AND title <> '')", name="ck_supervisor_requests_title_nonblank"),
        CheckConstraint("summary IS NULL OR (summary = btrim(summary) AND summary <> '')", name="ck_supervisor_requests_summary_nonblank"),
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','CHANGES_REQUESTED','ACCEPTED','REJECTED','WITHDRAWN')",
            name="ck_supervisor_requests_status",
        ),
        CheckConstraint("extraction_status IN ('PENDING','EXTRACTED','FAILED','CONFIRMED')", name="ck_supervisor_requests_extraction_status"),
        Index("ix_supervisor_requests_cycle_status", "academic_cycle_id", "status"),
        Index("ix_supervisor_requests_supervisor_status", "supervisor_id", "status"),
        Index("ix_supervisor_requests_extraction_status", "extraction_status"),
        Index(
            "uq_supervisor_requests_active_owner_supervisor",
            "academic_cycle_id",
            "requester_user_id",
            "supervisor_id",
            unique=True,
            postgresql_where=text("status IN ('DRAFT','SUBMITTED','CHANGES_REQUESTED','ACCEPTED')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False)
    requester_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    team_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supervisor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    proposal_type: Mapped[str] = mapped_column(String(5), nullable=False, default="SHORT", server_default="SHORT")
    problem_statement: Mapped[str | None] = mapped_column(Text, nullable=True)
    objectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    methodology: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("supervisor_assignments.id", ondelete="RESTRICT"), nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("supervisor_request_documents.id", ondelete="RESTRICT", use_alter=True), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    submission_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(16), nullable=False, default=SupervisorRequestExtractionStatus.PENDING.value, server_default=SupervisorRequestExtractionStatus.PENDING.value)
    extraction_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extraction_confirmed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=SupervisorRequestStatus.DRAFT.value, server_default=SupervisorRequestStatus.DRAFT.value)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)


class SupervisorRequestDocument(Base):
    __tablename__ = "supervisor_request_documents"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_supervisor_request_documents_version_positive"),
        CheckConstraint("file_size > 0", name="ck_supervisor_request_documents_file_size_positive"),
        CheckConstraint("page_count > 0", name="ck_supervisor_request_documents_page_count_positive"),
        CheckConstraint("extraction_status IN ('PENDING','EXTRACTED','FAILED','CONFIRMED')", name="ck_supervisor_request_documents_extraction_status"),
        Index("uq_supervisor_request_document_version", "request_id", "version", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("supervisor_requests.id", ondelete="RESTRICT"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_fields: Mapped[dict] = mapped_column(JSONB, nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(16), nullable=False)
    extraction_runtime: Mapped[str] = mapped_column(String(100), nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SupervisorRequestStatusHistory(Base):
    __tablename__ = "supervisor_request_status_history"
    __table_args__ = (
        CheckConstraint(
            "to_status IN ('DRAFT','SUBMITTED','CHANGES_REQUESTED','ACCEPTED','REJECTED','WITHDRAWN')",
            name="ck_supervisor_request_history_to_status",
        ),
        Index("ix_supervisor_request_history_request_created", "request_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("supervisor_requests.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SupervisorRequestSubmissionNoteVersion(Base):
    """Immutable snapshots of notes submitted with a supervisor request."""

    __tablename__ = "supervisor_request_submission_note_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_supervisor_request_note_version_positive"),
        CheckConstraint("body = btrim(body) AND body <> ''", name="ck_supervisor_request_note_body_nonblank"),
        Index("uq_supervisor_request_note_version", "request_id", "version", unique=True),
        Index("ix_supervisor_request_note_request", "request_id", "submitted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("supervisor_requests.id", ondelete="RESTRICT"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
