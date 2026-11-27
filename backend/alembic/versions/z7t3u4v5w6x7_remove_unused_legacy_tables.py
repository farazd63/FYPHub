"""Remove database objects that are no longer part of the active application flows."""

from alembic import op


revision = "z7t3u4v5w6x7"
down_revision = "z7s2t3u4v5w6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # These tables belonged to retired AI, proposal-version, matching-index,
    # and Module 3 implementations.  They are not mapped or queried by the
    # current application.  The explicit order keeps this cleanup safe even
    # on databases that still have the historical child-table constraints.
    for table in (
        "group_ai_responses",
        "group_ai_document_chunks",
        "knowledge_document_chunks",
        "module2_chatbot_sessions",
        "proposal_versions",
        "m03_ai_runs",
        "m03_compliance_findings",
        "m03_compliance_reports",
        "m03_proposal_access",
        "m03_proposal_change_summaries",
        "m03_proposal_documents",
        "m03_proposal_submissions",
        "m03_template_rule_sets",
        "m03_reference_templates",
        "m03_proposal_records",
        "team_member_verifications",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")


def downgrade() -> None:
    # The removed objects contained retired data and were intentionally not
    # recreated.  Historical migrations remain available for fresh installs.
    pass
