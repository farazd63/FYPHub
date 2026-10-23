"""Add team compatibility preferences."""
from alembic import op
import sqlalchemy as sa
revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("team_match_preferences", sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), primary_key=True), sa.Column("opted_in", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("answers", sa.JSON(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))

def downgrade():
    op.drop_table("team_match_preferences")
