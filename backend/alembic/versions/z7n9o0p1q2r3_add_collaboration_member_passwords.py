"""Add password-gated member identities to collaboration channels."""

from alembic import op
import sqlalchemy as sa


revision = "z7n9o0p1q2r3"
down_revision = "z7m8n9o0p1q2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collaboration_member_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("collaboration_channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_member_id", sa.Integer(), sa.ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("channel_id", "team_member_id", name="uq_collaboration_member_credential"),
    )
    op.create_index(
        "ix_collaboration_member_credentials_channel",
        "collaboration_member_credentials",
        ["channel_id"],
    )

    op.create_table(
        "collaboration_member_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("auth_session_id", sa.Integer(), sa.ForeignKey("auth_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("collaboration_channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_member_id", sa.Integer(), sa.ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("auth_session_id", "channel_id", name="uq_collaboration_member_session"),
    )
    op.create_index(
        "ix_collaboration_member_sessions_lookup",
        "collaboration_member_sessions",
        ["auth_session_id", "channel_id", "expires_at"],
    )

    op.create_table(
        "collaboration_password_reset_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("collaboration_channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_member_id", sa.Integer(), sa.ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
    )
    op.create_index(
        "uq_collaboration_password_reset_pending",
        "collaboration_password_reset_requests",
        ["channel_id", "team_member_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.create_index(
        "ix_collaboration_password_reset_requests_status",
        "collaboration_password_reset_requests",
        ["status", "requested_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_collaboration_password_reset_requests_status", table_name="collaboration_password_reset_requests")
    op.drop_index("uq_collaboration_password_reset_pending", table_name="collaboration_password_reset_requests")
    op.drop_table("collaboration_password_reset_requests")
    op.drop_index("ix_collaboration_member_sessions_lookup", table_name="collaboration_member_sessions")
    op.drop_table("collaboration_member_sessions")
    op.drop_index("ix_collaboration_member_credentials_channel", table_name="collaboration_member_credentials")
    op.drop_table("collaboration_member_credentials")
