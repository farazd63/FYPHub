"""Add retained team channel messages."""
from alembic import op
import sqlalchemy as sa
revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("group_messages", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False), sa.Column("channel", sa.String(32), nullable=False), sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("author_kind", sa.String(16), nullable=False), sa.Column("body", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_group_messages_team_channel_id", "group_messages", ["team_id", "channel", "id"])

def downgrade():
    op.drop_table("group_messages")
