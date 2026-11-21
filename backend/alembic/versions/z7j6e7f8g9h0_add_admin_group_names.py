"""Store administrator-assigned names for shared group portal accounts."""

from alembic import op
import sqlalchemy as sa


revision = "z7j6e7f8g9h0"
down_revision = "z7i5d6e7f8g9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("group_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("teams", "group_name")
