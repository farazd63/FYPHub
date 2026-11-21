"""Supervisor expertise, proposal analysis, and explainable matching records."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint, Float, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class SupervisorProfile(Base):
    __tablename__ = "supervisor_profiles"
    __table_args__ = (
        CheckConstraint("profile_status IN ('DRAFT','PENDING_VERIFICATION','VERIFIED','REJECTED','ARCHIVED')", name="ck_supervisor_profiles_status"),
        CheckConstraint("visibility_status IN ('PRIVATE','PUBLIC')", name="ck_supervisor_profiles_visibility"),
        Index("ix_supervisor_profiles_status_visibility", "profile_status", "visibility_status"),
        Index("ix_supervisor_profiles_department_program", "department", "program"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supervisor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    program: Mapped[str | None] = mapped_column(String(255), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    biography: Mapped[str | None] = mapped_column(Text, nullable=True)
    degree: Mapped[str | None] = mapped_column(String(255), nullable=True)
    specialization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_categories: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    publications: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    profile_status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT", server_default="DRAFT")
    visibility_status: Mapped[str] = mapped_column(String(16), nullable=False, default="PRIVATE", server_default="PRIVATE")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    extracted_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class SupervisorExpertise(Base):
    __tablename__ = "supervisor_expertise"
    __table_args__ = (UniqueConstraint("profile_id", "name", name="uq_supervisor_expertise_name"), Index("ix_supervisor_expertise_profile", "profile_id"))

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1")
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class SupervisorSkill(Base):
    __tablename__ = "supervisor_skills"
    __table_args__ = (UniqueConstraint("profile_id", "category", "name", name="uq_supervisor_skill_name"), Index("ix_supervisor_skills_profile", "profile_id"))

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False, default="technical", server_default="technical")
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1")
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class SupervisorResearchInterest(Base):
    __tablename__ = "supervisor_research_interests"
    __table_args__ = (UniqueConstraint("profile_id", "name", name="uq_supervisor_research_interest_name"), Index("ix_supervisor_research_interests_profile", "profile_id"))

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1")
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class SupervisorDocument(Base):
    __tablename__ = "supervisor_documents"
    __table_args__ = (Index("ix_supervisor_documents_profile_status", "profile_id", "extraction_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    extracted_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    extraction_status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING", server_default="PENDING")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SupervisedProjectHistory(Base):
    __tablename__ = "supervised_project_history"
    __table_args__ = (
        Index("ix_supervised_project_history_profile", "profile_id"),
        Index("ix_supervised_project_history_cycle", "academic_cycle_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False)
    project_title: Mapped[str] = mapped_column(String(255), nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_domain: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    problem_area: Mapped[str | None] = mapped_column(Text, nullable=True)
    methodology: Mapped[str | None] = mapped_column(Text, nullable=True)
    technologies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    keywords: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    academic_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("academic_cycles.id", ondelete="SET NULL"), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supervisor_role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    project_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    public_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="DERIVED", server_default="DERIVED")
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_document_id: Mapped[int | None] = mapped_column(ForeignKey("supervisor_documents.id", ondelete="SET NULL"), nullable=True)
    source_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class KnowledgeDocument(Base):
    """Metadata-first document registry for the future shared vector index."""

    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_knowledge_documents_source"),
        Index("ix_knowledge_documents_scope", "academic_cycle_id", "team_id", "supervisor_id"),
        Index("ix_knowledge_documents_permissions", "student_user_id", "supervisor_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    academic_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("academic_cycles.id", ondelete="SET NULL"), nullable=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    student_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    supervisor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    project_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    access_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KnowledgeDocumentChunk(Base):
    """Reserved chunk contract; embeddings can be populated by a later indexer."""

    __tablename__ = "knowledge_document_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_document_chunk"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    chunk_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SupervisorAvailability(Base):
    __tablename__ = "supervisor_availability"
    __table_args__ = (UniqueConstraint("profile_id", "academic_cycle_id", name="uq_supervisor_availability_cycle"), Index("ix_supervisor_availability_cycle", "academic_cycle_id", "available"))

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False)
    academic_cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id", ondelete="CASCADE"), nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    maximum_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    current_active_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ProposalAnalysis(Base):
    __tablename__ = "proposal_analyses"
    __table_args__ = (UniqueConstraint("submission_id", name="uq_proposal_analysis_submission"), Index("ix_proposal_analyses_status", "status"))

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("proposal_compliance_submissions.id", ondelete="CASCADE"), nullable=False)
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING", server_default="PENDING")
    preliminary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ProposalAnalysisVersion(Base):
    __tablename__ = "proposal_analysis_versions"
    __table_args__ = (UniqueConstraint("analysis_id", "proposal_version", name="uq_proposal_analysis_version"), Index("ix_proposal_analysis_versions_submission", "submission_id", "proposal_version"))

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("proposal_analyses.id", ondelete="CASCADE"), nullable=False)
    submission_id: Mapped[int] = mapped_column(ForeignKey("proposal_compliance_submissions.id", ondelete="CASCADE"), nullable=False)
    proposal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="COMPLETED", server_default="COMPLETED")
    fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    confidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    source_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MatchingConfiguration(Base):
    __tablename__ = "matching_configurations"
    __table_args__ = (UniqueConstraint("academic_cycle_id", name="uq_matching_configuration_cycle"), Index("ix_matching_configurations_active", "is_active"))

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("academic_cycles.id", ondelete="CASCADE"), nullable=True)
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    eligibility_rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False, default="supervisor-matching-v1", server_default="supervisor-matching-v1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class SupervisorMatchResult(Base):
    __tablename__ = "supervisor_match_results"
    __table_args__ = (
        UniqueConstraint("analysis_version_id", "profile_id", "academic_cycle_id", "algorithm_version", name="uq_supervisor_match_cache"),
        Index("ix_supervisor_match_results_score", "academic_cycle_id", "final_score"),
        Index("ix_supervisor_match_results_profile", "profile_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_version_id: Mapped[int] = mapped_column(ForeignKey("proposal_analysis_versions.id", ondelete="CASCADE"), nullable=False)
    profile_id: Mapped[int] = mapped_column(ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False)
    academic_cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id", ondelete="CASCADE"), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    score_components: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    explanation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    proposal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProfileVerificationRecord(Base):
    __tablename__ = "profile_verification_records"
    __table_args__ = (Index("ix_profile_verification_profile_created", "profile_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    to_status: Mapped[str] = mapped_column(String(24), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MatchingAuditLog(Base):
    __tablename__ = "matching_audit_logs"
    __table_args__ = (Index("ix_matching_audit_logs_created", "created_at"), Index("ix_matching_audit_logs_event", "event_type"))

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    proposal_analysis_version_id: Mapped[int | None] = mapped_column(ForeignKey("proposal_analysis_versions.id", ondelete="SET NULL"), nullable=True)
    match_result_id: Mapped[int | None] = mapped_column(ForeignKey("supervisor_match_results.id", ondelete="SET NULL"), nullable=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("supervisor_requests.id", ondelete="SET NULL"), nullable=True)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
