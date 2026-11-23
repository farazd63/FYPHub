"""Store the selected group-member identity on collaboration messages."""

from alembic import op
import sqlalchemy as sa


revision = "z7m8n9o0p1q2"
down_revision = "z7l8m9n0o1p2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "collaboration_messages",
        sa.Column(
            "sender_team_member_id",
            sa.Integer(),
            sa.ForeignKey("team_members.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_collaboration_messages_sender_team_member",
        "collaboration_messages",
        ["sender_team_member_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_collaboration_messages_sender_team_member", table_name="collaboration_messages")
    op.drop_column("collaboration_messages", "sender_team_member_id")
