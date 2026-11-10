"""add assignment-scoped private Module 2 collaboration channels"""

from alembic import op
import sqlalchemy as sa

revision = "fc6b7c8d9e0f"
down_revision = "r678a003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collaboration_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("academic_year", sa.Integer(), nullable=False),
        sa.Column("session", sa.String(length=16), nullable=False),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("supervisor_assignments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("uq_collaboration_channel_active_assignment", "collaboration_channels", ["team_id", "supervisor_id", "assignment_id"], unique=True, postgresql_where=sa.text("status = 'ACTIVE'"))
    op.create_index("ix_collaboration_channels_supervisor_status", "collaboration_channels", ["supervisor_id", "status"])
    op.create_table(
        "collaboration_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("collaboration_channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("team_member_id", sa.Integer(), sa.ForeignKey("team_members.id", ondelete="CASCADE"), nullable=True),
        sa.Column("participant_role", sa.String(length=24), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("channel_id", "user_id", name="uq_collaboration_participant_user"),
    )
    op.create_index("ix_collaboration_participants_channel_active", "collaboration_participants", ["channel_id", "is_active"])
    op.create_table(
        "collaboration_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("collaboration_channels.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("attachment_reference", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_collaboration_messages_channel_created", "collaboration_messages", ["channel_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_collaboration_messages_channel_created", table_name="collaboration_messages")
    op.drop_table("collaboration_messages")
    op.drop_index("ix_collaboration_participants_channel_active", table_name="collaboration_participants")
    op.drop_table("collaboration_participants")
    op.drop_index("ix_collaboration_channels_supervisor_status", table_name="collaboration_channels")
    op.drop_index("uq_collaboration_channel_active_assignment", table_name="collaboration_channels")
    op.drop_table("collaboration_channels")
