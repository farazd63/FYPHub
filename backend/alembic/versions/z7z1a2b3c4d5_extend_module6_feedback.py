"""Add structured feedback fields and document-linked feedback messages."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "z7z1a2b3c4d5"
down_revision = "z7e6f7g8h9i0"
branch_labels = None
depends_on = None


def _json_default() -> sa.sql.elements.TextClause:
    return sa.text("'{}'::jsonb")


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.add_column("proposal_review_feedback", sa.Column("correction_action", sa.String(length=24), nullable=False, server_default="NONE"))
    op.add_column("proposal_review_feedback", sa.Column("destination_location", jsonb, nullable=True))
    op.add_column("proposal_review_feedback", sa.Column("expected_outcome", sa.Text(), nullable=True))
    op.add_column("proposal_review_feedback", sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("proposal_review_feedback", sa.Column("workflow_status", sa.String(length=24), nullable=False, server_default="OPEN"))
    op.create_table(
        "proposal_review_feedback_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("feedback_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["feedback_id"], ["proposal_review_feedback.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_proposal_review_feedback_messages_feedback_created",
        "proposal_review_feedback_messages",
        ["feedback_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_proposal_review_feedback_messages_feedback_created", table_name="proposal_review_feedback_messages")
    op.drop_table("proposal_review_feedback_messages")
    op.drop_column("proposal_review_feedback", "workflow_status")
    op.drop_column("proposal_review_feedback", "is_mandatory")
    op.drop_column("proposal_review_feedback", "expected_outcome")
    op.drop_column("proposal_review_feedback", "destination_location")
    op.drop_column("proposal_review_feedback", "correction_action")
