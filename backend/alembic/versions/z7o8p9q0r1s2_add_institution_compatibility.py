"""Bring the pending institution/tenant model changes in line with the database."""

from alembic import op
import sqlalchemy as sa


revision = "z7o8p9q0r1s2"
down_revision = "y6n7o8p9q0"
branch_labels = None
depends_on = None


DATA_TABLES = (
    "academic_cycles", "academic_deadline_versions", "academic_deadlines", "academic_group_policies", "academic_rule_versions",
    "admin_audit_events", "announcement_reads", "announcements", "archive_import_batches", "archived_project_documents",
    "archived_projects", "auth_sessions", "collaboration_channels", "collaboration_messages", "collaboration_participants",
    "dashboard_requirements", "defense_panel_members", "defense_schedules", "document_archive_review_queue",
    "document_requirement_sections", "document_submission_review_events", "document_submission_versions", "document_submissions",
    "document_upload_requirements", "evaluation_aggregation_configs", "evaluation_audit_events", "evaluation_corrections",
    "evaluation_records", "evaluation_rubric_criteria", "evaluation_rubric_versions", "evaluation_rubrics",
    "group_ai_document_chunks", "group_ai_responses", "group_messages", "matching_audit_logs", "matching_configurations",
    "module2_channel_reads", "module2_chatbot_sessions", "module2_notifications", "panel_evaluation_scores", "panel_evaluations",
    "password_reset_tokens", "profile_verification_records", "project_milestones", "project_tasks", "proposal_ai_review_runs",
    "proposal_analyses", "proposal_analysis_versions", "proposal_compliance_reports", "proposal_compliance_submissions",
    "proposal_reference_documents", "proposal_references", "proposal_version_comparisons", "proposal_versions", "proposals",
    "reminder_rule_versions", "reminder_rules", "student_ai_messages", "supervised_project_history", "supervision_agent_runs",
    "supervision_meetings", "supervisor_assignments", "supervisor_availability", "supervisor_capacity_policies", "supervisor_documents",
    "supervisor_expertise", "supervisor_match_results", "supervisor_profiles", "supervisor_request_documents", "supervisor_request_messages",
    "supervisor_request_status_history", "supervisor_request_submission_note_versions", "supervisor_requests", "supervisor_research_interests",
    "supervisor_skills", "team_members", "teams", "template_reference_versions", "template_references", "users",
)


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'PLATFORM_ADMIN'")
    op.create_table(
        "institutions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('ACTIVE','DISABLED')", name="ck_institutions_status"),
        sa.UniqueConstraint("slug", name="uq_institutions_slug"),
    )
    op.create_table(
        "institution_domains",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("institution_id", "domain", name="uq_institution_domains_institution_domain"),
        sa.UniqueConstraint("domain", name="uq_institution_domains_domain"),
    )
    op.create_table(
        "institution_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("membership_role", sa.String(32), nullable=False, server_default="MEMBER"),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("invited_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("institution_id", "user_id", name="uq_institution_memberships_institution_user"),
    )
    op.create_table(
        "institution_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("invited_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for table_name in DATA_TABLES:
        op.add_column(table_name, sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True))
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("access_approved_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("users", "access_approved_at")
    op.drop_column("users", "email_verified_at")
    for table_name in reversed(DATA_TABLES):
        op.drop_column(table_name, "institution_id")
    op.drop_table("email_verification_tokens")
    op.drop_table("institution_invitations")
    op.drop_table("institution_memberships")
    op.drop_table("institution_domains")
    op.drop_table("institutions")
