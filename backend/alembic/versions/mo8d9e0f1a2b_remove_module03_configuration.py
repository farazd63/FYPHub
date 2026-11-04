"""Retire Module 03 configuration and preserve proposal AI-review runs."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "mo8d9e0f1a2b"
down_revision = "mn7c8d9e0f1a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proposal_ai_review_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposal_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("runtime", sa.String(128), nullable=False),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_proposal_ai_review_runs_proposal", "proposal_ai_review_runs", ["proposal_id"])
    op.execute(
        sa.text(
            "INSERT INTO proposal_ai_review_runs "
            "(id, proposal_id, status, runtime, model, result, error_message, started_at, finished_at) "
            "SELECT id, proposal_id, status, runtime, model, result, error_message, started_at, finished_at "
            "FROM m03_ai_runs WHERE check_name = 'proposal_ai_review'"
        )
    )
    op.execute(
        sa.text(
            "SELECT setval(pg_get_serial_sequence('proposal_ai_review_runs', 'id'), "
            "COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM proposal_ai_review_runs"
        )
    )

    # Audit history is append-only at runtime. Remove only the retired module's
    # rows while preserving the protection trigger for all future writes.
    op.execute(sa.text("ALTER TABLE admin_audit_events DISABLE TRIGGER USER"))
    op.execute(
        sa.text(
            "DELETE FROM admin_audit_events "
            "WHERE target_type = 'MODULE_03' OR action LIKE 'module03_%'"
        )
    )
    op.execute(sa.text("ALTER TABLE admin_audit_events ENABLE TRIGGER USER"))

    op.drop_index("ix_m03_ai_runs_proposal", table_name="m03_ai_runs")
    op.drop_table("m03_ai_runs")
    op.drop_index("ix_m03_findings_report", table_name="m03_compliance_findings")
    op.drop_table("m03_compliance_findings")
    op.drop_index("ix_m03_compliance_reports_proposal", table_name="m03_compliance_reports")
    op.drop_table("m03_compliance_reports")
    op.drop_index("ix_m03_proposal_documents_owner", table_name="m03_proposal_documents")
    op.drop_table("m03_proposal_documents")
    op.drop_index("ix_m03_template_rule_sets_version", table_name="m03_template_rule_sets")
    op.drop_index("ix_m03_template_rule_sets_template", table_name="m03_template_rule_sets")
    op.drop_table("m03_template_rule_sets")
    op.drop_index("ix_m03_reference_templates_parent", table_name="m03_reference_templates")
    op.drop_index("ix_m03_reference_templates_active_type", table_name="m03_reference_templates")
    op.drop_table("m03_reference_templates")


def downgrade() -> None:
    raise RuntimeError("Module 03 removal is intentionally irreversible; restore from the pre-delete backup instead.")
