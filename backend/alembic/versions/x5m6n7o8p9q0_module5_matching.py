"""Add Module 5 supervisor expertise matching records."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector


revision = "x5m6n7o8p9q0"
down_revision = ("v1a2b3c4e5f60", "vl1m2n3o4p5q")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supervisor_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("department", sa.String(255)), sa.Column("program", sa.String(255)), sa.Column("designation", sa.String(255)),
        sa.Column("biography", sa.Text()), sa.Column("preferred_categories", JSONB(), nullable=False, server_default="[]"),
        sa.Column("profile_status", sa.String(24), nullable=False, server_default="DRAFT"),
        sa.Column("visibility_status", sa.String(16), nullable=False, server_default="PRIVATE"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("profile_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("extracted_summary", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("profile_status IN ('DRAFT','PENDING_VERIFICATION','VERIFIED','REJECTED','ARCHIVED')", name="ck_supervisor_profiles_status"),
        sa.CheckConstraint("visibility_status IN ('PRIVATE','PUBLIC')", name="ck_supervisor_profiles_visibility"),
    )
    op.create_index("ix_supervisor_profiles_status_visibility", "supervisor_profiles", ["profile_status", "visibility_status"])
    op.create_index("ix_supervisor_profiles_department_program", "supervisor_profiles", ["department", "program"])

    op.create_table(
        "supervisor_expertise",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("profile_id", sa.Integer(), sa.ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False), sa.Column("evidence", sa.Text()), sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("profile_id", "name", name="uq_supervisor_expertise_name"),
    )
    op.create_index("ix_supervisor_expertise_profile", "supervisor_expertise", ["profile_id"])
    op.create_table(
        "supervisor_skills",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("profile_id", sa.Integer(), sa.ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(48), nullable=False, server_default="technical"), sa.Column("name", sa.String(160), nullable=False), sa.Column("evidence", sa.Text()),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1"), sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("profile_id", "category", "name", name="uq_supervisor_skill_name"),
    )
    op.create_index("ix_supervisor_skills_profile", "supervisor_skills", ["profile_id"])
    op.create_table(
        "supervisor_research_interests",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("profile_id", sa.Integer(), sa.ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False), sa.Column("evidence", sa.Text()), sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("profile_id", "name", name="uq_supervisor_research_interest_name"),
    )
    op.create_index("ix_supervisor_research_interests_profile", "supervisor_research_interests", ["profile_id"])

    op.create_table(
        "supervisor_documents",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("profile_id", sa.Integer(), sa.ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False), sa.Column("content_type", sa.String(100), nullable=False), sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False), sa.Column("content", sa.LargeBinary(), nullable=False), sa.Column("extracted_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("extracted_fields", JSONB(), nullable=False, server_default="{}"), sa.Column("extraction_status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_supervisor_documents_profile_status", "supervisor_documents", ["profile_id", "extraction_status"])

    op.create_table(
        "supervised_project_history",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("profile_id", sa.Integer(), sa.ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_title", sa.String(255), nullable=False), sa.Column("abstract", sa.Text()), sa.Column("research_domain", JSONB(), nullable=False, server_default="[]"),
        sa.Column("problem_area", sa.Text()), sa.Column("methodology", sa.Text()), sa.Column("technologies", JSONB(), nullable=False, server_default="[]"), sa.Column("keywords", JSONB(), nullable=False, server_default="[]"),
        sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="SET NULL")), sa.Column("year", sa.Integer()), sa.Column("supervisor_role", sa.String(120)), sa.Column("project_status", sa.String(80)), sa.Column("public_summary", sa.Text()),
        sa.Column("source_document_id", sa.Integer(), sa.ForeignKey("supervisor_documents.id", ondelete="SET NULL")), sa.Column("source_verified", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("embedding", Vector(384)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_supervised_project_history_profile", "supervised_project_history", ["profile_id"])
    op.create_index("ix_supervised_project_history_cycle", "supervised_project_history", ["academic_cycle_id"])
    op.execute("CREATE INDEX ix_supervised_project_history_embedding ON supervised_project_history USING hnsw (embedding vector_cosine_ops)")

    op.create_table(
        "supervisor_availability",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("profile_id", sa.Integer(), sa.ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="CASCADE"), nullable=False), sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("maximum_capacity", sa.Integer(), nullable=False, server_default="0"), sa.Column("current_active_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("profile_id", "academic_cycle_id", name="uq_supervisor_availability_cycle"),
    )
    op.create_index("ix_supervisor_availability_cycle", "supervisor_availability", ["academic_cycle_id", "available"])

    op.create_table(
        "proposal_analyses",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("submission_id", sa.Integer(), sa.ForeignKey("proposal_compliance_submissions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("current_version_id", sa.Integer()), sa.Column("status", sa.String(24), nullable=False, server_default="PENDING"), sa.Column("preliminary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("error_message", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_proposal_analyses_status", "proposal_analyses", ["status"])
    op.create_table(
        "proposal_analysis_versions",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("proposal_analyses.id", ondelete="CASCADE"), nullable=False), sa.Column("submission_id", sa.Integer(), sa.ForeignKey("proposal_compliance_submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposal_version", sa.Integer(), nullable=False), sa.Column("status", sa.String(24), nullable=False, server_default="COMPLETED"), sa.Column("fields", JSONB(), nullable=False, server_default="{}"), sa.Column("confidence", JSONB(), nullable=False, server_default="{}"), sa.Column("evidence", JSONB(), nullable=False, server_default="{}"), sa.Column("embedding", Vector(384)),
        sa.Column("source_text_hash", sa.String(64), nullable=False), sa.Column("model", sa.String(160)), sa.Column("provider", sa.String(64)), sa.Column("error_message", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("analysis_id", "proposal_version", name="uq_proposal_analysis_version"),
    )
    op.create_index("ix_proposal_analysis_versions_submission", "proposal_analysis_versions", ["submission_id", "proposal_version"])
    op.execute("CREATE INDEX ix_proposal_analysis_versions_embedding ON proposal_analysis_versions USING hnsw (embedding vector_cosine_ops)")

    op.create_table(
        "matching_configurations",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="CASCADE")), sa.Column("weights", JSONB(), nullable=False, server_default="{}"), sa.Column("eligibility_rules", JSONB(), nullable=False, server_default="{}"),
        sa.Column("algorithm_version", sa.String(64), nullable=False, server_default="module5-v1"), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("academic_cycle_id", name="uq_matching_configuration_cycle"),
    )
    op.create_index("ix_matching_configurations_active", "matching_configurations", ["is_active"])

    op.create_table(
        "supervisor_match_results",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("analysis_version_id", sa.Integer(), sa.ForeignKey("proposal_analysis_versions.id", ondelete="CASCADE"), nullable=False), sa.Column("profile_id", sa.Integer(), sa.ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False), sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False), sa.Column("final_score", sa.Float(), nullable=False), sa.Column("score_components", JSONB(), nullable=False, server_default="{}"), sa.Column("explanation", JSONB(), nullable=False, server_default="{}"), sa.Column("proposal_version", sa.Integer(), nullable=False), sa.Column("profile_version", sa.Integer(), nullable=False), sa.Column("algorithm_version", sa.String(64), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("analysis_version_id", "profile_id", "academic_cycle_id", "algorithm_version", name="uq_supervisor_match_cache"),
    )
    op.create_index("ix_supervisor_match_results_score", "supervisor_match_results", ["academic_cycle_id", "final_score"])
    op.create_index("ix_supervisor_match_results_profile", "supervisor_match_results", ["profile_id"])

    op.create_table(
        "profile_verification_records",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("profile_id", sa.Integer(), sa.ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False), sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("from_status", sa.String(24)), sa.Column("to_status", sa.String(24), nullable=False), sa.Column("comment", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_profile_verification_profile_created", "profile_verification_records", ["profile_id", "created_at"])

    op.create_table(
        "matching_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("event_type", sa.String(80), nullable=False), sa.Column("proposal_analysis_version_id", sa.Integer(), sa.ForeignKey("proposal_analysis_versions.id", ondelete="SET NULL")), sa.Column("match_result_id", sa.Integer(), sa.ForeignKey("supervisor_match_results.id", ondelete="SET NULL")), sa.Column("request_id", sa.Integer(), sa.ForeignKey("supervisor_requests.id", ondelete="SET NULL")), sa.Column("metadata", JSONB(), nullable=False, server_default="{}"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_matching_audit_logs_created", "matching_audit_logs", ["created_at"])
    op.create_index("ix_matching_audit_logs_event", "matching_audit_logs", ["event_type"])

    op.add_column("supervisor_requests", sa.Column("proposal_submission_id", sa.Integer(), sa.ForeignKey("proposal_compliance_submissions.id", ondelete="SET NULL")))
    op.add_column("supervisor_requests", sa.Column("proposal_version_number", sa.Integer()))
    op.add_column("supervisor_requests", sa.Column("match_result_id", sa.Integer(), sa.ForeignKey("supervisor_match_results.id", ondelete="SET NULL")))
    op.add_column("supervisor_requests", sa.Column("match_score", sa.Float()))
    op.add_column("supervisor_requests", sa.Column("match_explanation", JSONB()))
    op.add_column("supervisor_requests", sa.Column("matching_algorithm_version", sa.String(64)))
    op.create_index("ix_supervisor_requests_proposal_match", "supervisor_requests", ["proposal_submission_id", "match_result_id"])


def downgrade() -> None:
    op.drop_index("ix_supervisor_requests_proposal_match", table_name="supervisor_requests")
    op.drop_column("supervisor_requests", "matching_algorithm_version")
    op.drop_column("supervisor_requests", "match_explanation")
    op.drop_column("supervisor_requests", "match_score")
    op.drop_column("supervisor_requests", "match_result_id")
    op.drop_column("supervisor_requests", "proposal_version_number")
    op.drop_column("supervisor_requests", "proposal_submission_id")
    op.drop_table("matching_audit_logs")
    op.drop_table("profile_verification_records")
    op.drop_table("supervisor_match_results")
    op.drop_table("matching_configurations")
    op.drop_table("proposal_analysis_versions")
    op.drop_table("proposal_analyses")
    op.drop_table("supervisor_availability")
    op.drop_table("supervised_project_history")
    op.drop_table("supervisor_documents")
    op.drop_table("supervisor_research_interests")
    op.drop_table("supervisor_skills")
    op.drop_table("supervisor_expertise")
    op.drop_table("supervisor_profiles")
