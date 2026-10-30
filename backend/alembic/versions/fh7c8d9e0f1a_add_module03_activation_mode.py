"""Persist complete or partial Module 03 baseline activation mode."""

from alembic import op
import sqlalchemy as sa


revision = "fh7c8d9e0f1a"
down_revision = "fg6b7c8d9e0f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("m03_reference_templates", sa.Column("activation_mode", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("m03_reference_templates", "activation_mode")
