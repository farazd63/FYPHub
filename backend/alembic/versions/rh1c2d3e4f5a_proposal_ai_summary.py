"""Store advisory AI summaries separately from extracted proposal content."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "rh1c2d3e4f5a"
down_revision = "rg0b1c2d3e4f"
branch_labels = None
depends_on = None

def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("supervisor_requests")}
    if "ai_summary" not in columns:
        op.add_column("supervisor_requests", sa.Column("ai_summary", JSONB(), nullable=True))

def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("supervisor_requests")}
    if "ai_summary" in columns:
        op.drop_column("supervisor_requests", "ai_summary")
