"""Version-scoped review records for admin-created document requirements.

Legacy proposal review records remain in their existing tables. These generic
records are deliberately keyed by document submission and version so a review
cannot accidentally display or modify another requirement's proposal.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class DocumentReviewFeedback(Base):
    __tablename__ = "document_review_feedback"
    __table_args__ = (
        Index("ix_document_review_feedback_submission", "submission_id", "created_at"),
        Index("ix_document_review_feedback_version", "version_id", "publication_status"),
        Index("ix_document_review_feedback_group", "group_id", "publication_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("document_submissions.id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[int] = mapped_column(ForeignKey("document_submission_versions.id", ondelete="CASCADE"), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    marker_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    feedback_level: Mapped[str] = mapped_column(String(24), nullable=False, server_default="FULL_DOCUMENT")
    feedback_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="GENERAL_COMMENT")
    correction_action: Mapped[str] = mapped_column(String(24), nullable=False, server_default="NONE")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    destination_location: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    expected_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, server_default="MEDIUM")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    workflow_status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="OPEN")
    publication_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentReviewFeedbackMessage(Base):
    __tablename__ = "document_review_feedback_messages"
    __table_args__ = (Index("ix_document_review_feedback_messages_feedback_created", "feedback_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("document_review_feedback.id", ondelete="CASCADE"), nullable=False)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentReviewAnnotation(Base):
    __tablename__ = "document_review_annotations"
    __table_args__ = (
        Index("ix_document_review_annotations_submission_page", "submission_id", "version_id", "page_number"),
        Index("ix_document_review_annotations_group_status", "group_id", "publication_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("document_submissions.id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[int] = mapped_column(ForeignKey("document_submission_versions.id", ondelete="CASCADE"), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    annotation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    geometry: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    drawing: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    selected_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(16), nullable=False, server_default="#F5C542")
    stroke_width: Mapped[float] = mapped_column(nullable=False, server_default="2")
    publication_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="DRAFT")
    feedback_id: Mapped[int | None] = mapped_column(ForeignKey("document_review_feedback.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
