"""Add tenant keys to Module 6 supervisor review tables."""

from alembic import op
import sqlalchemy as sa


revision = "z7a1b2c3d4e5"
down_revision = "z7z0a1b2c3d4"
branch_labels = None
depends_on = None


TABLES = (
    "proposal_review_feedback",
    "proposal_revision_requests",
    "proposal_revision_messages",
    "proposal_revision_assessments",
    "proposal_revision_decisions",
)


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column(
                "institution_id",
                sa.Integer(),
                sa.ForeignKey("institutions.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index(f"ix_{table}_institution_id", table, ["institution_id"])


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_institution_id", table_name=table)
        op.drop_column(table, "institution_id")
