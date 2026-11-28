"""Module 6 proposal review, revision tracking, and discussion records.

The records in this module deliberately sit beside Module 3 proposal
compliance records.  Module 3 answers whether a document matches a university
baseline; Module 6 records what the assigned supervisor asked the group to
change and whether the supervisor accepted that change.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ProposalReviewFeedback(Base):
    __tablename__ = "proposal_review_feedback"
    __table_args__ = (
        Index("ix_proposal_review_feedback_submission", "submission_id", "created_at"),
        Index("ix_proposal_review_feedback_team_status", "team_id", "publication_status"),
        Index("ix_proposal_review_feedback_institution_id", "institution_id"),
        UniqueConstraint("submission_id", "marker_number", name="uq_proposal_review_feedback_submission_marker"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    submission_id: Mapped[int] = mapped_column(ForeignKey("proposal_compliance_submissions.id", ondelete="RESTRICT"), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    marker_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    feedback_level: Mapped[str] = mapped_column(String(24), nullable=False, server_default="FULL_PROPOSAL")
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
    publication_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="PUBLISHED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True)


class ProposalReviewFeedbackMessage(Base):
    __tablename__ = "proposal_review_feedback_messages"
    __table_args__ = (
        Index("ix_proposal_review_feedback_messages_feedback_created", "feedback_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("proposal_review_feedback.id", ondelete="CASCADE"), nullable=False)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProposalReviewFeedbackRevision(Base):
    __tablename__ = "proposal_review_feedback_revisions"
    __table_args__ = (
        Index("ix_proposal_review_feedback_revisions_feedback_created", "feedback_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("proposal_review_feedback.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    before_state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    after_state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProposalRevisionRequest(Base):
    __tablename__ = "proposal_revision_requests"
    __table_args__ = (
        UniqueConstraint("revision_code", name="uq_proposal_revision_requests_code"),
        Index("ix_proposal_revision_requests_team_status", "team_id", "status"),
        Index("ix_proposal_revision_requests_source", "source_submission_id"),
        Index("ix_proposal_revision_requests_latest", "latest_submission_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    revision_code: Mapped[str] = mapped_column(String(32), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    proposal_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_submission_id: Mapped[int] = mapped_column(ForeignKey("proposal_compliance_submissions.id", ondelete="RESTRICT"), nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    latest_submission_id: Mapped[int | None] = mapped_column(ForeignKey("proposal_compliance_submissions.id", ondelete="RESTRICT"), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    target_level: Mapped[str] = mapped_column(String(24), nullable=False, server_default="FULL_PROPOSAL")
    target_locator: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    expected_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, server_default="MEDIUM")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="OPEN")
    student_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_reopen_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ProposalRevisionMessage(Base):
    __tablename__ = "proposal_revision_messages"
    __table_args__ = (Index("ix_proposal_revision_messages_request_created", "revision_request_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    revision_request_id: Mapped[int] = mapped_column(ForeignKey("proposal_revision_requests.id", ondelete="CASCADE"), nullable=False)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProposalRevisionAssessment(Base):
    __tablename__ = "proposal_revision_assessments"
    __table_args__ = (
        Index("ix_proposal_revision_assessments_request_created", "revision_request_id", "created_at"),
        UniqueConstraint("revision_request_id", "current_submission_id", name="uq_proposal_revision_assessment_run"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    revision_request_id: Mapped[int] = mapped_column(ForeignKey("proposal_revision_requests.id", ondelete="CASCADE"), nullable=False)
    source_submission_id: Mapped[int] = mapped_column(ForeignKey("proposal_compliance_submissions.id", ondelete="RESTRICT"), nullable=False)
    current_submission_id: Mapped[int] = mapped_column(ForeignKey("proposal_compliance_submissions.id", ondelete="RESTRICT"), nullable=False)
    classification: Mapped[str] = mapped_column(String(24), nullable=False)
    requirements: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    manual_verification_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="COMPLETED")
    source: Mapped[str] = mapped_column(String(32), nullable=False, server_default="DETERMINISTIC_FALLBACK")
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    raw_result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProposalRevisionDecision(Base):
    __tablename__ = "proposal_revision_decisions"
    __table_args__ = (Index("ix_proposal_revision_decisions_request_created", "revision_request_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    revision_request_id: Mapped[int] = mapped_column(ForeignKey("proposal_revision_requests.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    classification: Mapped[str | None] = mapped_column(String(24), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
