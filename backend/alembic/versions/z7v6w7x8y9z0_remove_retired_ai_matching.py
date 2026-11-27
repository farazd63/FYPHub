"""Remove the retired AI supervisor-matching storage and request fields."""

from alembic import op


revision = "z7v6w7x8y9z0"
down_revision = "z7u4v5w6x7y8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE supervisor_requests DROP CONSTRAINT IF EXISTS supervisor_requests_match_result_id_fkey")
    op.execute(
        "ALTER TABLE supervisor_requests "
        "DROP COLUMN IF EXISTS match_result_id, "
        "DROP COLUMN IF EXISTS match_score, "
        "DROP COLUMN IF EXISTS match_explanation, "
        "DROP COLUMN IF EXISTS matching_algorithm_version"
    )
    op.execute(
        "ALTER TABLE supervised_project_history "
        "DROP COLUMN IF EXISTS source_document_id, "
        "DROP COLUMN IF EXISTS embedding"
    )
    for table in (
        "matching_audit_logs",
        "supervisor_match_results",
        "proposal_analysis_versions",
        "proposal_analyses",
        "supervisor_documents",
        "profile_verification_records",
        "matching_configurations",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")


def downgrade() -> None:
    pass
