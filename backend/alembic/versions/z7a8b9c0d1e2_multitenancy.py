"""Complete institution tenancy for the compatibility schema and legacy data."""

from alembic import op
import sqlalchemy as sa


revision = "z7a8b9c0d1e2"
down_revision = ("z7o8p9q0r1s2",)
branch_labels = None
depends_on = None


# The compatibility migration added the tenant column to the ORM tables. These
# older tables are still present in deployed databases and need the same key.
LEGACY_TABLES = (
    "m03_ai_runs",
    "m03_compliance_findings",
    "m03_compliance_reports",
    "m03_proposal_access",
    "m03_proposal_change_summaries",
    "m03_proposal_documents",
    "m03_proposal_records",
    "m03_proposal_submissions",
    "m03_reference_templates",
    "m03_template_rule_sets",
    "team_member_verifications",
)

DATA_TABLES = (
    "academic_cycles", "academic_deadline_versions", "academic_deadlines", "academic_group_policies", "academic_rule_versions",
    "admin_audit_events", "announcement_reads", "archive_import_batches", "archived_project_documents", "archived_projects",
    "auth_sessions", "collaboration_channels", "collaboration_messages", "collaboration_participants", "dashboard_requirements",
    "defense_panel_members", "defense_schedules", "document_archive_review_queue", "document_requirement_sections",
    "document_submission_review_events", "document_submission_versions", "document_submissions", "document_upload_requirements",
    "evaluation_aggregation_configs", "evaluation_audit_events", "evaluation_corrections", "evaluation_records",
    "evaluation_rubric_criteria", "evaluation_rubric_versions", "evaluation_rubrics", "group_ai_document_chunks",
    "group_ai_responses", "group_messages", *LEGACY_TABLES, "matching_audit_logs", "matching_configurations",
    "module2_channel_reads", "module2_chatbot_sessions", "module2_notifications", "panel_evaluation_scores", "panel_evaluations",
    "password_reset_tokens", "profile_verification_records", "project_milestones", "project_tasks", "proposal_ai_review_runs",
    "proposal_analyses", "proposal_analysis_versions", "proposal_compliance_reports", "proposal_compliance_submissions",
    "proposal_reference_documents", "proposal_references", "proposal_version_comparisons", "proposal_versions", "proposals",
    "reminder_rule_versions", "reminder_rules", "student_ai_messages", "supervised_project_history", "supervision_agent_runs",
    "supervision_meetings", "supervisor_assignments", "supervisor_availability", "supervisor_capacity_policies",
    "supervisor_documents", "supervisor_expertise", "supervisor_match_results", "supervisor_profiles", "supervisor_request_documents",
    "supervisor_request_messages", "supervisor_request_status_history", "supervisor_request_submission_note_versions",
    "supervisor_requests", "supervisor_research_interests", "supervisor_skills", "team_members", "teams",
    "template_reference_versions", "template_references", "users",
)

APPEND_ONLY_TABLES = {
    "admin_audit_events",
    "supervisor_request_documents",
    "supervisor_request_messages",
    "supervisor_request_status_history",
    "supervisor_request_submission_note_versions",
}


def upgrade() -> None:
    for table_name in LEGACY_TABLES:
        op.add_column(
            table_name,
            sa.Column(
                "institution_id",
                sa.Integer(),
                sa.ForeignKey("institutions.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    for table_name in DATA_TABLES:
        op.create_index(f"ix_{table_name}_institution_id", table_name, ["institution_id"])

    op.create_index("uq_institutions_slug_normalized", "institutions", [sa.text("lower(slug)")], unique=True)
    op.create_index("ix_institution_domains_lookup", "institution_domains", ["domain", "is_verified", "is_active"])
    op.create_index("ix_institution_memberships_user_status", "institution_memberships", ["user_id", "status"])
    op.create_index("ix_institution_invitations_email_status", "institution_invitations", ["email", "status"])
    op.create_index("ix_email_verification_tokens_user_status", "email_verification_tokens", ["user_id", "verified_at"])

    op.create_check_constraint(
        "ck_institution_domains_normalized",
        "institution_domains",
        "domain = lower(btrim(domain)) AND domain <> ''",
    )
    op.create_check_constraint(
        "ck_institution_memberships_status",
        "institution_memberships",
        "status IN ('PENDING','INVITED','APPROVED','ACTIVE','DISABLED','REJECTED')",
    )
    op.create_check_constraint(
        "ck_institution_memberships_role",
        "institution_memberships",
        "membership_role IN ('MEMBER','INSTITUTION_ADMIN')",
    )
    op.create_check_constraint(
        "ck_institution_invitations_status",
        "institution_invitations",
        "status IN ('PENDING','ACCEPTED','EXPIRED','REVOKED')",
    )

    # The earlier compatibility migration intentionally left existing rows
    # nullable. Assign them to one explicit tenant without deleting or changing
    # their business records.
    op.execute(
        """
        INSERT INTO institutions (slug, name, status)
        VALUES ('legacy-default', 'Legacy Institution', 'ACTIVE')
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO institution_domains (institution_id, domain, is_verified, is_active, verified_at)
        SELECT (SELECT id FROM institutions WHERE slug = 'legacy-default'), domain, TRUE, TRUE, NOW()
        FROM (
            SELECT DISTINCT lower(split_part(email, '@', 2)) AS domain
            FROM users WHERE email LIKE '%@%'
            UNION
            SELECT DISTINCT lower(split_part(university_email, '@', 2)) AS domain
            FROM team_members WHERE university_email LIKE '%@%'
        ) existing_domains
        WHERE domain <> ''
        ON CONFLICT (domain) DO NOTHING
        """
    )
    for table_name in DATA_TABLES:
        if table_name in APPEND_ONLY_TABLES:
            # This legacy audit table is protected against UPDATE by a
            # database trigger. Tenant assignment is part of the one-time
            # migration, so temporarily suspend only user triggers here.
            op.execute(f"ALTER TABLE {table_name} DISABLE TRIGGER USER")
        op.execute(
            sa.text(
                f"UPDATE {table_name} SET institution_id = "
                "(SELECT id FROM institutions WHERE slug = 'legacy-default') "
                "WHERE institution_id IS NULL"
            )
        )
        if table_name in APPEND_ONLY_TABLES:
            op.execute(f"ALTER TABLE {table_name} ENABLE TRIGGER USER")

    op.execute(
        """
        UPDATE users
        SET email_verified_at = COALESCE(email_verified_at, NOW()),
            access_approved_at = COALESCE(access_approved_at, NOW())
        WHERE institution_id = (SELECT id FROM institutions WHERE slug = 'legacy-default')
        """
    )
    op.execute(
        """
        INSERT INTO institution_memberships
            (institution_id, user_id, membership_role, status, approved_at)
        SELECT institution_id,
               id,
               CASE WHEN role::text = 'ADMIN' THEN 'INSTITUTION_ADMIN' ELSE 'MEMBER' END,
               CASE WHEN is_active THEN 'ACTIVE' ELSE 'DISABLED' END,
               access_approved_at
        FROM users
        WHERE institution_id IS NOT NULL
        ON CONFLICT (institution_id, user_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_email_verification_tokens_user_status", table_name="email_verification_tokens")
    op.drop_index("ix_institution_invitations_email_status", table_name="institution_invitations")
    op.drop_index("ix_institution_memberships_user_status", table_name="institution_memberships")
    op.drop_index("ix_institution_domains_lookup", table_name="institution_domains")
    op.drop_index("uq_institutions_slug_normalized", table_name="institutions")
    for table_name in reversed(DATA_TABLES):
        op.drop_index(f"ix_{table_name}_institution_id", table_name=table_name)
    for table_name in reversed(LEGACY_TABLES):
        op.drop_column(table_name, "institution_id")
    op.drop_constraint("ck_institution_invitations_status", "institution_invitations", type_="check")
    op.drop_constraint("ck_institution_memberships_role", "institution_memberships", type_="check")
    op.drop_constraint("ck_institution_memberships_status", "institution_memberships", type_="check")
    op.drop_constraint("ck_institution_domains_normalized", "institution_domains", type_="check")
