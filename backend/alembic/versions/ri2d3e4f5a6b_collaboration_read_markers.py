"""Add per-user read markers to the existing private collaboration participants."""
from alembic import op
import sqlalchemy as sa

revision = "ri2d3e4f5a6b"
down_revision = "rh1c2d3e4f5a"
branch_labels = None
depends_on = None

def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "collaboration_participants" not in tables:
        return
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("collaboration_participants")}
    if "last_read_message_id" not in columns:
        op.add_column("collaboration_participants", sa.Column("last_read_message_id", sa.Integer(), nullable=True))
    if "last_read_at" not in columns:
        op.add_column("collaboration_participants", sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True))
    fks = {fk["name"] for fk in sa.inspect(op.get_bind()).get_foreign_keys("collaboration_participants") if fk.get("name")}
    if "fk_collaboration_participant_last_read" not in fks and "collaboration_messages" in tables:
        op.create_foreign_key(
            "fk_collaboration_participant_last_read",
            "collaboration_participants",
            "collaboration_messages",
            ["last_read_message_id"],
            ["id"],
            ondelete="SET NULL",
        )

def downgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "collaboration_participants" not in tables:
        return
    fks = {fk["name"] for fk in sa.inspect(op.get_bind()).get_foreign_keys("collaboration_participants") if fk.get("name")}
    if "fk_collaboration_participant_last_read" in fks:
        op.drop_constraint("fk_collaboration_participant_last_read", "collaboration_participants", type_="foreignkey")
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("collaboration_participants")}
    if "last_read_at" in columns:
        op.drop_column("collaboration_participants", "last_read_at")
    if "last_read_message_id" in columns:
        op.drop_column("collaboration_participants", "last_read_message_id")
