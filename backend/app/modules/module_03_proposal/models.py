"""Module 03 persistence. External entities intentionally use plain IDs."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Index, Integer, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ...database import Base


class M03ProposalType(StrEnum):
    SHORT = "SHORT"
    LONG = "LONG"


class M03ExtractionStatus(StrEnum):
    PENDING = "PENDING"
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"


class M03ReportStatus(StrEnum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    NEEDS_REVISION = "NEEDS_REVISION"
    UNAVAILABLE = "UNAVAILABLE"


class M03Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class M03ReferenceTemplate(Base):
    __tablename__ = "m03_reference_templates"
    __table_args__ = (UniqueConstraint("template_type", "version", name="uq_m03_reference_template_type_version"), Index("ix_m03_reference_templates_active_type", "template_type", "is_active"), Index("ix_m03_reference_templates_parent", "parent_template_id"))

    id: Mapped[int] = mapped_column(primary_key=True)
    template_type: Mapped[str] = mapped_column(String(16), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    version_kind: Mapped[str] = mapped_column(String(24), nullable=False, default="REFERENCE", server_default="REFERENCE")
    parent_template_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    template_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    provenance: Mapped[str] = mapped_column(String(64), nullable=False, default="Observed reference property", server_default="Observed reference property")
    extraction_status: Mapped[str] = mapped_column(String(24), nullable=False, default="EXTRACTED")
    extracted_rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    extraction_warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[str | None] = mapped_column(String(24), nullable=True)
    activation_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    uploaded_by_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class M03TemplateRule(Base):
    __tablename__ = "m03_template_rule_sets"
    __table_args__ = (Index("ix_m03_template_rule_sets_template", "reference_template_id"), Index("ix_m03_template_rule_sets_version", "reference_template_id", "rule_version"), UniqueConstraint("reference_template_id", "rule_version", "rule_key", name="uq_m03_template_rule_version_key"))

    id: Mapped[int] = mapped_column(primary_key=True)
    reference_template_id: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_key: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    provenance: Mapped[str] = mapped_column(String(64), nullable=False, default="Observed reference property", server_default="Observed reference property")
    confidence: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class M03ProposalDocument(Base):
    __tablename__ = "m03_proposal_documents"
    __table_args__ = (UniqueConstraint("proposal_id", "version", name="uq_m03_proposal_document_version"), Index("ix_m03_proposal_documents_owner", "owner_user_id", "is_active"))

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    proposal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    team_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    ast: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    extraction_warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class M03ComplianceReport(Base):
    __tablename__ = "m03_compliance_reports"
    __table_args__ = (UniqueConstraint("proposal_id", "report_version", name="uq_m03_report_proposal_version"), Index("ix_m03_compliance_reports_proposal", "proposal_id", "report_version"))

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    proposal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    proposal_document_id: Mapped[str] = mapped_column(String(128), nullable=False)
    baseline_template_id: Mapped[str] = mapped_column(String(128), nullable=False)
    proposal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    report_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    check_1: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    check_2: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    check_3: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    severity_counts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    remediation: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    advisory_summary: Mapped[str] = mapped_column(Text, nullable=False, default="AI findings are advisory only.")
    runtime_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    generated_by_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class M03ComplianceFinding(Base):
    __tablename__ = "m03_compliance_findings"
    __table_args__ = (Index("ix_m03_findings_report", "report_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[str] = mapped_column(String(128), nullable=False)
    check_name: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    student_value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    baseline_value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    remediation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class M03CheckRun(Base):
    __tablename__ = "m03_ai_runs"
    __table_args__ = (Index("ix_m03_ai_runs_proposal", "proposal_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    report_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    check_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    runtime: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
