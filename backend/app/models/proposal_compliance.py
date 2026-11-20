"""Stored Module 3 proposal submissions and compliance report snapshots."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ProposalComplianceSubmission(Base):
    __tablename__ = "proposal_compliance_submissions"
    __table_args__ = (
        UniqueConstraint("proposal_key", "version", name="uq_proposal_compliance_submission_version"),
        CheckConstraint("version > 0", name="ck_proposal_compliance_submission_version_positive"),
        CheckConstraint("proposal_type IN ('SHORT','LONG')", name="ck_proposal_compliance_submission_type"),
        Index("ix_proposal_compliance_submission_owner", "owner_user_id", "created_at"),
        Index("ix_proposal_compliance_submission_key", "proposal_key", "version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_key: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=True)
    proposal_type: Mapped[str] = mapped_column(String(5), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUBMITTED", server_default="SUBMITTED")
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED", server_default="QUEUED")
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    template_reference_version_id: Mapped[int | None] = mapped_column(ForeignKey("template_reference_versions.id", ondelete="RESTRICT"), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ProposalComplianceReport(Base):
    __tablename__ = "proposal_compliance_reports"
    __table_args__ = (
        UniqueConstraint("submission_id", name="uq_proposal_compliance_report_submission"),
        Index("ix_proposal_compliance_report_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("proposal_compliance_submissions.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    total_checks: Mapped[int] = mapped_column(Integer, nullable=False)
    report: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProposalVersionComparison(Base):
    """Stored comparison snapshot between two audited versions."""

    __tablename__ = "proposal_version_comparisons"
    __table_args__ = (
        UniqueConstraint("current_submission_id", name="uq_proposal_version_comparison_current"),
        UniqueConstraint("previous_submission_id", "current_submission_id", name="uq_proposal_version_comparison_pair"),
        Index("ix_proposal_version_comparison_current_created", "current_submission_id", "created_at"),
        Index("ix_proposal_version_comparison_previous", "previous_submission_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    previous_submission_id: Mapped[int] = mapped_column(ForeignKey("proposal_compliance_submissions.id", ondelete="RESTRICT"), nullable=False)
    current_submission_id: Mapped[int] = mapped_column(ForeignKey("proposal_compliance_submissions.id", ondelete="RESTRICT"), nullable=False)
    previous_report_id: Mapped[int] = mapped_column(ForeignKey("proposal_compliance_reports.id", ondelete="RESTRICT"), nullable=False)
    current_report_id: Mapped[int] = mapped_column(ForeignKey("proposal_compliance_reports.id", ondelete="RESTRICT"), nullable=False)
    previous_version: Mapped[int] = mapped_column(Integer, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_difference: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_result: Mapped[str] = mapped_column(String(16), nullable=False)
    previous_issue_count: Mapped[int] = mapped_column(Integer, nullable=False)
    current_issue_count: Mapped[int] = mapped_column(Integer, nullable=False)
    fixed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_count: Mapped[int] = mapped_column(Integer, nullable=False)
    new_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unchanged_count: Mapped[int] = mapped_column(Integer, nullable=False)
    net_issue_change: Mapped[int] = mapped_column(Integer, nullable=False)
    different_template_versions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    comparison: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ai_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    ai_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
