"""Add Module 6 supervisor proposal review workflow."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "z7y9z0a1b2c3"
down_revision = "z7x8y9z0a1b2"
branch_labels = None
depends_on = None


def _json_default() -> sa.sql.elements.TextClause:
    return sa.text("'{}'::jsonb")


def _json_list_default() -> sa.sql.elements.TextClause:
    return sa.text("'[]'::jsonb")


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())

    op.create_table(
        "proposal_review_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("feedback_level", sa.String(length=24), nullable=False, server_default="FULL_PROPOSAL"),
        sa.Column("feedback_type", sa.String(length=32), nullable=False, server_default="GENERAL_COMMENT"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("suggested_text", sa.Text(), nullable=True),
        sa.Column("selected_text", sa.Text(), nullable=True),
        sa.Column("location", jsonb, nullable=False, server_default=_json_default()),
        sa.Column("publication_status", sa.String(length=16), nullable=False, server_default="PUBLISHED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submission_id"], ["proposal_compliance_submissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_proposal_review_feedback_submission", "proposal_review_feedback", ["submission_id", "created_at"])
    op.create_index("ix_proposal_review_feedback_team_status", "proposal_review_feedback", ["team_id", "publication_status"])

    op.create_table(
        "proposal_revision_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision_code", sa.String(length=32), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("proposal_key", sa.String(length=64), nullable=False),
        sa.Column("source_submission_id", sa.Integer(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("latest_submission_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("target_level", sa.String(length=24), nullable=False, server_default="FULL_PROPOSAL"),
        sa.Column("target_locator", jsonb, nullable=False, server_default=_json_default()),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("expected_outcome", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="MEDIUM"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="OPEN"),
        sa.Column("student_explanation", sa.Text(), nullable=True),
        sa.Column("last_reopen_reason", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_submission_id"], ["proposal_compliance_submissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["latest_submission_id"], ["proposal_compliance_submissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("revision_code", name="uq_proposal_revision_requests_code"),
    )
    op.create_index("ix_proposal_revision_requests_team_status", "proposal_revision_requests", ["team_id", "status"])
    op.create_index("ix_proposal_revision_requests_source", "proposal_revision_requests", ["source_submission_id"])
    op.create_index("ix_proposal_revision_requests_latest", "proposal_revision_requests", ["latest_submission_id"])

    op.create_table(
        "proposal_revision_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision_request_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["revision_request_id"], ["proposal_revision_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_proposal_revision_messages_request_created", "proposal_revision_messages", ["revision_request_id", "created_at"])

    op.create_table(
        "proposal_revision_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision_request_id", sa.Integer(), nullable=False),
        sa.Column("source_submission_id", sa.Integer(), nullable=False),
        sa.Column("current_submission_id", sa.Integer(), nullable=False),
        sa.Column("classification", sa.String(length=24), nullable=False),
        sa.Column("requirements", jsonb, nullable=False, server_default=_json_list_default()),
        sa.Column("evidence", jsonb, nullable=False, server_default=_json_list_default()),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("manual_verification_required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="COMPLETED"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="DETERMINISTIC_FALLBACK"),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=160), nullable=True),
        sa.Column("raw_result", jsonb, nullable=False, server_default=_json_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["revision_request_id"], ["proposal_revision_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_submission_id"], ["proposal_compliance_submissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["current_submission_id"], ["proposal_compliance_submissions.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("revision_request_id", "current_submission_id", name="uq_proposal_revision_assessment_run"),
    )
    op.create_index("ix_proposal_revision_assessments_request_created", "proposal_revision_assessments", ["revision_request_id", "created_at"])

    op.create_table(
        "proposal_revision_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision_request_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("classification", sa.String(length=24), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["revision_request_id"], ["proposal_revision_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_proposal_revision_decisions_request_created", "proposal_revision_decisions", ["revision_request_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_proposal_revision_decisions_request_created", table_name="proposal_revision_decisions")
    op.drop_table("proposal_revision_decisions")
    op.drop_index("ix_proposal_revision_assessments_request_created", table_name="proposal_revision_assessments")
    op.drop_table("proposal_revision_assessments")
    op.drop_index("ix_proposal_revision_messages_request_created", table_name="proposal_revision_messages")
    op.drop_table("proposal_revision_messages")
    op.drop_index("ix_proposal_revision_requests_latest", table_name="proposal_revision_requests")
    op.drop_index("ix_proposal_revision_requests_source", table_name="proposal_revision_requests")
    op.drop_index("ix_proposal_revision_requests_team_status", table_name="proposal_revision_requests")
    op.drop_table("proposal_revision_requests")
    op.drop_index("ix_proposal_review_feedback_team_status", table_name="proposal_review_feedback")
    op.drop_index("ix_proposal_review_feedback_submission", table_name="proposal_review_feedback")
    op.drop_table("proposal_review_feedback")
