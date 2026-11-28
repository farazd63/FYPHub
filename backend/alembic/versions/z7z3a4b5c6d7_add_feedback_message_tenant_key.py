"""Add the shared tenant key to document feedback replies."""

from alembic import op
import sqlalchemy as sa


revision = "z7z3a4b5c6d7"
down_revision = "z7z2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proposal_review_feedback_messages",
        sa.Column(
            "institution_id",
            sa.Integer(),
            sa.ForeignKey("institutions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_proposal_review_feedback_messages_institution_id",
        "proposal_review_feedback_messages",
        ["institution_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_proposal_review_feedback_messages_institution_id", table_name="proposal_review_feedback_messages")
    op.drop_column("proposal_review_feedback_messages", "institution_id")
