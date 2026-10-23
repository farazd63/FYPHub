"""Allow new match conversations after mutual fresh consent."""
from alembic import op
import sqlalchemy as sa
revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None

def upgrade():
    op.drop_constraint("uq_match_chats_pair", "match_chats", type_="unique")
    op.create_index("uq_match_chats_open_pair", "match_chats", ["team_a_id", "team_b_id"], unique=True, postgresql_where=sa.text("closed_at IS NULL"))
    op.create_table("match_chat_consents",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("closed_chat_id",sa.Integer(),sa.ForeignKey("match_chats.id",ondelete="RESTRICT"),nullable=False),sa.Column("team_id",sa.Integer(),sa.ForeignKey("teams.id",ondelete="RESTRICT"),nullable=False),sa.UniqueConstraint("closed_chat_id","team_id",name="uq_match_chat_consent"))

def downgrade():
    op.drop_table("match_chat_consents")
    op.drop_index("uq_match_chats_open_pair",table_name="match_chats")
    op.create_unique_constraint("uq_match_chats_pair","match_chats",["team_a_id","team_b_id"])
