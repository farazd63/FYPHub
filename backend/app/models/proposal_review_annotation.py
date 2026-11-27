"""Persistent, version-scoped annotations for the Module 6 review workspace."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ProposalReviewAnnotation(Base):
    __tablename__ = "proposal_review_annotations"
    __table_args__ = (
        Index("ix_proposal_review_annotations_submission_page", "submission_id", "page_number"),
        Index("ix_proposal_review_annotations_team_status", "team_id", "publication_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    submission_id: Mapped[int] = mapped_column(ForeignKey("proposal_compliance_submissions.id", ondelete="RESTRICT"), nullable=False)
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
    feedback_id: Mapped[int | None] = mapped_column(ForeignKey("proposal_review_feedback.id", ondelete="SET NULL"), nullable=True)
    revision_request_id: Mapped[int | None] = mapped_column(ForeignKey("proposal_revision_requests.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
