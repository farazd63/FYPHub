"""Store a group-confirmed final project title separately from proposals."""

from alembic import op
import sqlalchemy as sa


revision = "z7e6f7g8h9i0"
down_revision = "z7d5e6f7g8h9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("final_project_title", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("teams", "final_project_title")
