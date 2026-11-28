"""Preserve document feedback edit history."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "z7z6b7c8d9e0"
down_revision = "z7z5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proposal_review_feedback_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("feedback_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("before_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("after_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("institution_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["feedback_id"], ["proposal_review_feedback.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_proposal_review_feedback_revisions_feedback_created", "proposal_review_feedback_revisions", ["feedback_id", "created_at"])
    op.create_index("ix_proposal_review_feedback_revisions_institution_id", "proposal_review_feedback_revisions", ["institution_id"])


def downgrade() -> None:
    op.drop_index("ix_proposal_review_feedback_revisions_institution_id", table_name="proposal_review_feedback_revisions")
    op.drop_index("ix_proposal_review_feedback_revisions_feedback_created", table_name="proposal_review_feedback_revisions")
    op.drop_table("proposal_review_feedback_revisions")
