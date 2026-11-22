"""Add the shared institution tenant key to AI conversations."""

from alembic import op
import sqlalchemy as sa


revision = "z7l8m9n0o1p2"
down_revision = "z7k7f8g9h0i1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "student_ai_conversations",
        sa.Column(
            "institution_id",
            sa.Integer(),
            sa.ForeignKey("institutions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_student_ai_conversations_institution_id",
        "student_ai_conversations",
        ["institution_id"],
    )
    op.execute(
        sa.text(
            """
            UPDATE student_ai_conversations AS conversations
            SET institution_id = users.institution_id
            FROM users
            WHERE users.id = conversations.user_id
              AND conversations.institution_id IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_student_ai_conversations_institution_id",
        table_name="student_ai_conversations",
    )
    op.drop_column("student_ai_conversations", "institution_id")
