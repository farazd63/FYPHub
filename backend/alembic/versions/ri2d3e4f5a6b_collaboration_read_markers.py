"""Add per-user read markers to the existing private collaboration participants."""
from alembic import op
import sqlalchemy as sa

revision = "ri2d3e4f5a6b"
down_revision = "rh1c2d3e4f5a"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("collaboration_participants", sa.Column("last_read_message_id", sa.Integer(), nullable=True))
    op.add_column("collaboration_participants", sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_collaboration_participant_last_read", "collaboration_participants", "collaboration_messages", ["last_read_message_id"], ["id"], ondelete="SET NULL")

def downgrade():
    op.drop_constraint("fk_collaboration_participant_last_read", "collaboration_participants", type_="foreignkey")
    op.drop_column("collaboration_participants", "last_read_at")
    op.drop_column("collaboration_participants", "last_read_message_id")
