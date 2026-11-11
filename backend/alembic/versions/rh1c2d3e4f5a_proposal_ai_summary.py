"""Store advisory AI summaries separately from extracted proposal content."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "rh1c2d3e4f5a"
down_revision = "rg0b1c2d3e4f"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("supervisor_requests", sa.Column("ai_summary", JSONB(), nullable=True))

def downgrade():
    op.drop_column("supervisor_requests", "ai_summary")
