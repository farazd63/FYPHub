"""Add stable feedback markers and contextual priority/deadline fields."""

from alembic import op
import sqlalchemy as sa


revision = "z7z4a5b6c7d8"
down_revision = "z7z3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proposal_review_feedback", sa.Column("marker_number", sa.Integer(), nullable=True))
    op.add_column("proposal_review_feedback", sa.Column("priority", sa.String(length=16), nullable=False, server_default="MEDIUM"))
    op.add_column("proposal_review_feedback", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        sa.text(
            """
            WITH numbered AS (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY submission_id ORDER BY created_at, id) AS marker_number
                FROM proposal_review_feedback
            )
            UPDATE proposal_review_feedback AS feedback
            SET marker_number = numbered.marker_number
            FROM numbered
            WHERE feedback.id = numbered.id
            """
        )
    )
    op.alter_column("proposal_review_feedback", "marker_number", nullable=False)
    op.create_unique_constraint(
        "uq_proposal_review_feedback_submission_marker",
        "proposal_review_feedback",
        ["submission_id", "marker_number"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_proposal_review_feedback_submission_marker", "proposal_review_feedback", type_="unique")
    op.drop_column("proposal_review_feedback", "due_at")
    op.drop_column("proposal_review_feedback", "priority")
    op.drop_column("proposal_review_feedback", "marker_number")
