"""Preserve extracted proposal titles without a 200-character storage limit."""

from alembic import op
import sqlalchemy as sa

revision = "rg0b1c2d3e4f"
down_revision = "rf9a0b1c2d3e"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("supervisor_requests", "title", existing_type=sa.String(200), type_=sa.Text(), existing_nullable=True)


def downgrade():
    # Refuse a lossy downgrade when a stored title exceeds the old limit.
    op.alter_column("supervisor_requests", "title", existing_type=sa.Text(), type_=sa.String(200), existing_nullable=True)
