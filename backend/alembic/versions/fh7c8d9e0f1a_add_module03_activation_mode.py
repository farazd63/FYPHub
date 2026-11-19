"""Persist complete or partial Module 03 baseline activation mode."""

from alembic import op
import sqlalchemy as sa


revision = "fh7c8d9e0f1a"
down_revision = "fg6b7c8d9e0f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "m03_reference_templates" not in tables:
        return
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("m03_reference_templates")}
    if "activation_mode" not in columns:
        op.add_column("m03_reference_templates", sa.Column("activation_mode", sa.String(16), nullable=True))


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "m03_reference_templates" not in tables:
        return
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("m03_reference_templates")}
    if "activation_mode" in columns:
        op.drop_column("m03_reference_templates", "activation_mode")
