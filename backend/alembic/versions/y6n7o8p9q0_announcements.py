"""Add centralized dashboard announcements and read markers."""

from alembic import op
import sqlalchemy as sa


revision = "y6n7o8p9q0"
down_revision = ("x5m6n7o8p9q0",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("author_role", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="NORMAL"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT"),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_role", sa.String(length=32), nullable=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("proposals.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("priority IN ('NORMAL','IMPORTANT','URGENT')", name="ck_announcements_priority"),
        sa.CheckConstraint("status IN ('DRAFT','PUBLISHED','ARCHIVED','EXPIRED')", name="ck_announcements_status"),
        sa.CheckConstraint("target_type IN ('ALL_USERS','ROLE','CYCLE','GROUP','PROJECT','ASSIGNED_STUDENTS','ASSIGNED_PANEL')", name="ck_announcements_target_type"),
        sa.CheckConstraint("expires_at IS NULL OR published_at IS NULL OR expires_at > published_at", name="ck_announcements_expiry_after_publish"),
    )
    op.create_index("ix_announcements_visibility_window", "announcements", ["status", "published_at", "expires_at"])
    op.create_index("ix_announcements_target_scope", "announcements", ["target_type", "target_role", "cycle_id", "group_id", "project_id"])
    op.create_index("ix_announcements_author", "announcements", ["author_id", "created_at"])
    op.create_table(
        "announcement_reads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("announcement_id", sa.Integer(), sa.ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("announcement_id", "user_id", name="uq_announcement_reads_announcement_user"),
    )
    op.create_index("ix_announcement_reads_user_read", "announcement_reads", ["user_id", "read_at"])


def downgrade() -> None:
    op.drop_index("ix_announcement_reads_user_read", table_name="announcement_reads")
    op.drop_table("announcement_reads")
    op.drop_index("ix_announcements_author", table_name="announcements")
    op.drop_index("ix_announcements_target_scope", table_name="announcements")
    op.drop_index("ix_announcements_visibility_window", table_name="announcements")
    op.drop_table("announcements")
