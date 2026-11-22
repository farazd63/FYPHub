"""Add conversation threads to the student AI assistant."""

from alembic import op
import sqlalchemy as sa


revision = "z7k7f8g9h0i1"
down_revision = ("z7j6e7f8g9h0", "z7p8q9r0s1t2")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_ai_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False, server_default="New chat"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_student_ai_conversations_user_updated",
        "student_ai_conversations",
        ["user_id", "updated_at", "id"],
    )

    op.add_column(
        "student_ai_messages",
        sa.Column("conversation_id", sa.Integer(), nullable=True),
    )

    # Keep all existing messages visible in one legacy thread per student.
    op.execute(
        sa.text(
            """
            INSERT INTO student_ai_conversations (user_id, title, created_at, updated_at)
            SELECT user_id, 'Previous chat', MIN(created_at), MAX(created_at)
            FROM student_ai_messages
            GROUP BY user_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE student_ai_messages AS messages
            SET conversation_id = conversations.id
            FROM student_ai_conversations AS conversations
            WHERE conversations.user_id = messages.user_id
              AND conversations.title = 'Previous chat'
            """
        )
    )

    op.alter_column("student_ai_messages", "conversation_id", nullable=False)
    op.create_foreign_key(
        "fk_student_ai_messages_conversation_id",
        "student_ai_messages",
        "student_ai_conversations",
        ["conversation_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index("ix_student_ai_messages_user_created", table_name="student_ai_messages")
    op.create_index(
        "ix_student_ai_messages_conversation_created",
        "student_ai_messages",
        ["conversation_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_student_ai_messages_conversation_created", table_name="student_ai_messages")
    op.create_index(
        "ix_student_ai_messages_user_created",
        "student_ai_messages",
        ["user_id", "created_at", "id"],
    )
    op.drop_constraint("fk_student_ai_messages_conversation_id", "student_ai_messages", type_="foreignkey")
    op.drop_column("student_ai_messages", "conversation_id")
    op.drop_index("ix_student_ai_conversations_user_updated", table_name="student_ai_conversations")
    op.drop_table("student_ai_conversations")
