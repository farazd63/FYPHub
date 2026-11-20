"""Add independent messages for the general student AI assistant."""

from alembic import op
import sqlalchemy as sa


revision = "v1a2b3c4e5f60"
down_revision = "v1a2b3c4d5e70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_ai_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_kind", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_student_ai_messages_user_created", "student_ai_messages", ["user_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_student_ai_messages_user_created", table_name="student_ai_messages")
    op.drop_table("student_ai_messages")
