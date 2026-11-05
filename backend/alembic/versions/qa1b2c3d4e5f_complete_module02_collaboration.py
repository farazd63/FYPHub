"""Complete Module 2 team lifecycle, matching and collaboration foundations."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "qa1b2c3d4e5f"
down_revision = "pa1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("academic_group_policies", sa.Column("min_group_size", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("academic_group_policies", sa.Column("formation_deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("academic_group_policies", sa.Column("matching_weights", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.create_check_constraint("ck_academic_group_policies_min_group_size_valid", "academic_group_policies", "min_group_size > 0 AND min_group_size <= max_group_size")

    op.add_column("teams", sa.Column("status", sa.String(length=16), nullable=False, server_default="forming"))
    op.add_column("teams", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("teams", sa.Column("lock_reason", sa.String(length=64), nullable=True))
    op.create_check_constraint("ck_teams_status", "teams", "status IN ('forming','complete','locked','dissolved')")
    op.add_column("proposal_compliance_submissions", sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=True))
    op.add_column("team_members", sa.Column("student_id", sa.Integer(), sa.ForeignKey("approved_students.id", ondelete="RESTRICT"), nullable=True))
    op.create_index("uq_active_team_member_student", "team_members", ["student_id", "academic_cycle_id"], unique=True, postgresql_where=sa.text("is_active AND student_id IS NOT NULL"))

    op.add_column("team_match_preferences", sa.Column("structured_answers", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("group_messages", sa.Column("thread_root_id", sa.Integer(), sa.ForeignKey("group_messages.id", ondelete="SET NULL"), nullable=True))
    op.add_column("group_messages", sa.Column("mentions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("group_messages", sa.Column("attachment_name", sa.String(length=255), nullable=True))
    op.add_column("group_messages", sa.Column("attachment_url", sa.String(length=500), nullable=True))

    op.add_column("join_requests", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))
    op.add_column("join_requests", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("ck_join_request_status", "join_requests", type_="check")
    op.create_check_constraint("ck_join_request_status", "join_requests", "status IN ('pending', 'accepted', 'rejected', 'cancelled', 'expired')")
    op.drop_constraint("ck_join_audit_action", "join_request_audit", type_="check")
    op.create_check_constraint("ck_join_audit_action", "join_request_audit", "action IN ('submitted', 'accepted', 'rejected', 'cancelled', 'expired')")

    op.add_column("team_invitations", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))
    op.add_column("team_invitations", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("ck_team_invitation_status", "team_invitations", type_="check")
    op.create_check_constraint("ck_team_invitation_status", "team_invitations", "status IN ('pending', 'accepted', 'rejected', 'cancelled', 'expired')")
    op.drop_constraint("ck_invitation_audit_action", "team_invitation_audit", type_="check")
    op.create_check_constraint("ck_invitation_audit_action", "team_invitation_audit", "action IN ('sent', 'queued', 'accepted', 'rejected', 'cancelled', 'expired')")

    op.create_table(
        "module2_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_module2_notifications_recipient_created", "module2_notifications", ["recipient_user_id", "created_at"])
    op.create_table(
        "module2_channel_reads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("last_read_message_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "team_id", "channel", name="uq_module2_channel_read"),
    )
    op.create_table(
        "module2_match_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.Integer(), sa.ForeignKey("match_chats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('open','reviewed','dismissed')", name="ck_module2_match_report_status"),
    )
    op.create_table(
        "module2_chatbot_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False, server_default="Group assistant"),
        sa.Column("context", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_module2_chatbot_sessions_team_created", "module2_chatbot_sessions", ["team_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_module2_chatbot_sessions_team_created", table_name="module2_chatbot_sessions")
    op.drop_table("module2_chatbot_sessions")
    op.drop_table("module2_match_reports")
    op.drop_table("module2_channel_reads")
    op.drop_index("ix_module2_notifications_recipient_created", table_name="module2_notifications")
    op.drop_table("module2_notifications")
    op.drop_constraint("ck_invitation_audit_action", "team_invitation_audit", type_="check")
    op.create_check_constraint("ck_invitation_audit_action", "team_invitation_audit", "action IN ('sent', 'queued', 'accepted', 'rejected')")
    op.drop_constraint("ck_team_invitation_status", "team_invitations", type_="check")
    op.create_check_constraint("ck_team_invitation_status", "team_invitations", "status IN ('pending', 'accepted', 'rejected')")
    op.drop_column("team_invitations", "expires_at")
    op.drop_column("team_invitations", "updated_at")
    op.drop_constraint("ck_join_audit_action", "join_request_audit", type_="check")
    op.create_check_constraint("ck_join_audit_action", "join_request_audit", "action IN ('submitted', 'accepted', 'rejected')")
    op.drop_constraint("ck_join_request_status", "join_requests", type_="check")
    op.create_check_constraint("ck_join_request_status", "join_requests", "status IN ('pending', 'accepted', 'rejected')")
    op.drop_column("join_requests", "expires_at")
    op.drop_column("join_requests", "updated_at")
    op.drop_column("group_messages", "attachment_url")
    op.drop_column("group_messages", "attachment_name")
    op.drop_column("group_messages", "mentions")
    op.drop_column("group_messages", "thread_root_id")
    op.drop_column("team_match_preferences", "structured_answers")
    op.drop_index("uq_active_team_member_student", table_name="team_members", postgresql_where=sa.text("is_active AND student_id IS NOT NULL"))
    op.drop_column("team_members", "student_id")
    op.drop_constraint("ck_teams_status", "teams", type_="check")
    op.drop_column("proposal_compliance_submissions", "team_id")
    op.drop_column("teams", "lock_reason")
    op.drop_column("teams", "locked_at")
    op.drop_column("teams", "status")
    op.drop_constraint("ck_academic_group_policies_min_group_size_valid", "academic_group_policies", type_="check")
    op.drop_column("academic_group_policies", "matching_weights")
    op.drop_column("academic_group_policies", "formation_deadline")
    op.drop_column("academic_group_policies", "min_group_size")
