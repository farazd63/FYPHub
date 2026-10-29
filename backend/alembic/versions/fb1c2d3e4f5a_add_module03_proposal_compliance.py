"""add Module 03 dynamic proposal compliance tables"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "fb1c2d3e4f5a"
down_revision = "fa0b1c2d3e4"
branch_labels = None
depends_on = None


def _jsonb(name, default="{}"):
    return sa.Column(name, postgresql.JSONB(), nullable=False, server_default=sa.text(f"'{default}'::jsonb"))


def upgrade():
    op.create_table("m03_reference_templates",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("template_type", sa.String(16), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False), sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False), sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False), sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("extraction_status", sa.String(24), nullable=False),
        _jsonb("extracted_rules"), _jsonb("extraction_warnings", "[]"), sa.Column("confidence", sa.String(24)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("uploaded_by_user_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("template_type", "version", name="uq_m03_reference_template_type_version"))
    op.create_index("ix_m03_reference_templates_active_type", "m03_reference_templates", ["template_type", "is_active"])
    op.create_table("m03_template_rule_sets",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("reference_template_id", sa.Integer(), nullable=False), sa.Column("rule_key", sa.String(128), nullable=False), _jsonb("rule_value"), sa.Column("source", sa.String(255), nullable=False), sa.Column("confidence", sa.String(24), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_m03_template_rule_sets_template", "m03_template_rule_sets", ["reference_template_id"])
    op.create_table("m03_proposal_documents",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("proposal_id", sa.String(128), nullable=False), sa.Column("proposal_type", sa.String(16), nullable=False), sa.Column("owner_user_id", sa.String(128), nullable=False), sa.Column("team_id", sa.String(128)), sa.Column("filename", sa.String(255), nullable=False), sa.Column("storage_key", sa.String(512), nullable=False), sa.Column("sha256", sa.String(64), nullable=False), sa.Column("mime_type", sa.String(100), nullable=False), sa.Column("file_size", sa.Integer(), nullable=False), sa.Column("content", sa.LargeBinary(), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.Column("extraction_status", sa.String(24), nullable=False), _jsonb("ast"), _jsonb("extraction_warnings", "[]"), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("proposal_id", "version", name="uq_m03_proposal_document_version"))
    op.create_index("ix_m03_proposal_documents_owner", "m03_proposal_documents", ["owner_user_id", "is_active"])
    op.create_table("m03_compliance_reports",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("report_id", sa.String(128), unique=True, nullable=False), sa.Column("proposal_id", sa.String(128), nullable=False), sa.Column("proposal_document_id", sa.String(128), nullable=False), sa.Column("baseline_template_id", sa.String(128), nullable=False), sa.Column("proposal_type", sa.String(16), nullable=False), sa.Column("report_version", sa.Integer(), nullable=False), sa.Column("status", sa.String(32), nullable=False), _jsonb("check_1"), _jsonb("check_2"), _jsonb("check_3"), _jsonb("severity_counts"), _jsonb("remediation", "[]"), sa.Column("advisory_summary", sa.Text(), nullable=False), _jsonb("runtime_metadata"), sa.Column("generated_by_user_id", sa.String(128), nullable=False), sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("proposal_id", "report_version", name="uq_m03_report_proposal_version"))
    op.create_index("ix_m03_compliance_reports_proposal", "m03_compliance_reports", ["proposal_id", "report_version"])
    op.create_table("m03_compliance_findings",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("report_id", sa.String(128), nullable=False), sa.Column("check_name", sa.String(64), nullable=False), sa.Column("severity", sa.String(16), nullable=False), sa.Column("rule_reference", sa.String(255), nullable=False), _jsonb("student_value"), _jsonb("baseline_value"), _jsonb("evidence"), sa.Column("remediation", sa.Text(), nullable=False), sa.Column("confidence", sa.String(24), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_m03_findings_report", "m03_compliance_findings", ["report_id"])
    op.create_table("m03_ai_runs",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("proposal_id", sa.String(128), nullable=False), sa.Column("report_id", sa.String(128)), sa.Column("check_name", sa.String(64), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("runtime", sa.String(128), nullable=False), sa.Column("model", sa.String(128)), _jsonb("result"), sa.Column("error_message", sa.Text()), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("finished_at", sa.DateTime(timezone=True)))
    op.create_index("ix_m03_ai_runs_proposal", "m03_ai_runs", ["proposal_id"])


def downgrade():
    op.drop_index("ix_m03_ai_runs_proposal", table_name="m03_ai_runs"); op.drop_table("m03_ai_runs")
    op.drop_index("ix_m03_findings_report", table_name="m03_compliance_findings"); op.drop_table("m03_compliance_findings")
    op.drop_index("ix_m03_compliance_reports_proposal", table_name="m03_compliance_reports"); op.drop_table("m03_compliance_reports")
    op.drop_index("ix_m03_proposal_documents_owner", table_name="m03_proposal_documents"); op.drop_table("m03_proposal_documents")
    op.drop_index("ix_m03_template_rule_sets_template", table_name="m03_template_rule_sets"); op.drop_table("m03_template_rule_sets")
    op.drop_index("ix_m03_reference_templates_active_type", table_name="m03_reference_templates"); op.drop_table("m03_reference_templates")
