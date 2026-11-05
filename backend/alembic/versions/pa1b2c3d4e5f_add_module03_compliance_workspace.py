"""Add the Module 3 proposal compliance workspace."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "pa1b2c3d4e5f"
down_revision = ("ob1c2d3e4f5a", "oc1d2e3f4a5b")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proposal_compliance_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposal_key", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("proposal_type", sa.String(length=5), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="SUBMITTED"),
        sa.Column("processing_status", sa.String(length=32), nullable=False, server_default="QUEUED"),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("extracted_fields", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("template_reference_version_id", sa.Integer(), sa.ForeignKey("template_reference_versions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("proposal_key", "version", name="uq_proposal_compliance_submission_version"),
        sa.CheckConstraint("version > 0", name="ck_proposal_compliance_submission_version_positive"),
        sa.CheckConstraint("proposal_type IN ('SHORT','LONG')", name="ck_proposal_compliance_submission_type"),
    )
    op.create_index("ix_proposal_compliance_submission_owner", "proposal_compliance_submissions", ["owner_user_id", "created_at"])
    op.create_index("ix_proposal_compliance_submission_key", "proposal_compliance_submissions", ["proposal_key", "version"])
    op.create_table(
        "proposal_compliance_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("proposal_compliance_submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("total_checks", sa.Integer(), nullable=False),
        sa.Column("report", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("submission_id", name="uq_proposal_compliance_report_submission"),
    )
    op.create_index("ix_proposal_compliance_report_created", "proposal_compliance_reports", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_proposal_compliance_report_created", table_name="proposal_compliance_reports")
    op.drop_table("proposal_compliance_reports")
    op.drop_index("ix_proposal_compliance_submission_key", table_name="proposal_compliance_submissions")
    op.drop_index("ix_proposal_compliance_submission_owner", table_name="proposal_compliance_submissions")
    op.drop_table("proposal_compliance_submissions")
