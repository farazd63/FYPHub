"""Add temporary match chats and retained messages."""
from alembic import op
import sqlalchemy as sa
revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("match_chats", sa.Column("id",sa.Integer(),primary_key=True), sa.Column("team_a_id",sa.Integer(),sa.ForeignKey("teams.id",ondelete="RESTRICT"),nullable=False), sa.Column("team_b_id",sa.Integer(),sa.ForeignKey("teams.id",ondelete="RESTRICT"),nullable=False), sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False), sa.Column("closed_at",sa.DateTime(timezone=True)), sa.CheckConstraint("team_a_id < team_b_id",name="ck_match_chats_team_order"), sa.UniqueConstraint("team_a_id","team_b_id",name="uq_match_chats_pair"))
    op.create_table("match_messages", sa.Column("id",sa.Integer(),primary_key=True), sa.Column("chat_id",sa.Integer(),sa.ForeignKey("match_chats.id",ondelete="RESTRICT"),nullable=False), sa.Column("team_id",sa.Integer(),sa.ForeignKey("teams.id",ondelete="RESTRICT"),nullable=False), sa.Column("body",sa.Text(),nullable=False), sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_match_messages_chat_id","match_messages",["chat_id","id"])

def downgrade():
    op.drop_table("match_messages")
    op.drop_table("match_chats")
