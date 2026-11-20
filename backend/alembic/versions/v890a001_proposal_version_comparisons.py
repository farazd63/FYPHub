"""Store structured Module 3 proposal version comparisons."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "v890a001"
down_revision = "sj3k4l5m6n7o"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proposal_version_comparisons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("previous_submission_id", sa.Integer(), nullable=False),
        sa.Column("current_submission_id", sa.Integer(), nullable=False),
        sa.Column("previous_report_id", sa.Integer(), nullable=False),
        sa.Column("current_report_id", sa.Integer(), nullable=False),
        sa.Column("previous_version", sa.Integer(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("previous_score", sa.Integer(), nullable=True),
        sa.Column("current_score", sa.Integer(), nullable=True),
        sa.Column("score_difference", sa.Integer(), nullable=True),
        sa.Column("overall_result", sa.String(length=16), nullable=False),
        sa.Column("previous_issue_count", sa.Integer(), nullable=False),
        sa.Column("current_issue_count", sa.Integer(), nullable=False),
        sa.Column("fixed_count", sa.Integer(), nullable=False),
        sa.Column("remaining_count", sa.Integer(), nullable=False),
        sa.Column("new_count", sa.Integer(), nullable=False),
        sa.Column("unchanged_count", sa.Integer(), nullable=False),
        sa.Column("net_issue_change", sa.Integer(), nullable=False),
        sa.Column("different_template_versions", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("comparison", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("ai_status", sa.String(length=32), nullable=True),
        sa.Column("ai_source", sa.String(length=64), nullable=True),
        sa.Column("ai_model", sa.String(length=160), nullable=True),
        sa.Column("ai_provider", sa.String(length=64), nullable=True),
        sa.Column("ai_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["previous_submission_id"], ["proposal_compliance_submissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["current_submission_id"], ["proposal_compliance_submissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["previous_report_id"], ["proposal_compliance_reports.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["current_report_id"], ["proposal_compliance_reports.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("current_submission_id", name="uq_proposal_version_comparison_current"),
        sa.UniqueConstraint("previous_submission_id", "current_submission_id", name="uq_proposal_version_comparison_pair"),
    )
    op.create_index("ix_proposal_version_comparison_current_created", "proposal_version_comparisons", ["current_submission_id", "created_at"])
    op.create_index("ix_proposal_version_comparison_previous", "proposal_version_comparisons", ["previous_submission_id"])


def downgrade() -> None:
    op.drop_index("ix_proposal_version_comparison_previous", table_name="proposal_version_comparisons")
    op.drop_index("ix_proposal_version_comparison_current_created", table_name="proposal_version_comparisons")
    op.drop_table("proposal_version_comparisons")
