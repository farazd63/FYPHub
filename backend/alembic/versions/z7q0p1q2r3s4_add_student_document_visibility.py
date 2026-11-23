"""Keep student-hidden document versions available to reviewers and admins."""

from alembic import op
import sqlalchemy as sa


revision = "z7q0p1q2r3s4"
down_revision = "z7o0p1q2r3s4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_submission_versions",
        sa.Column("student_hidden_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_submission_versions", "student_hidden_at")
