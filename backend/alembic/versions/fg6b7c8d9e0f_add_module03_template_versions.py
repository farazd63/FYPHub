"""add immutable Module 03 template metadata and rule version provenance"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "fg6b7c8d9e0f"
down_revision = "ff5a6b7c8d9e"
# Table is created on the parallel Module-03 branch; require it before altering.
depends_on = ("fb1c2d3e4f5a",)
branch_labels = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}


def _constraints(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    names = {item["name"] for item in inspector.get_unique_constraints(table)}
    names.update(item["name"] for item in inspector.get_check_constraints(table) if item.get("name"))
    return names


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "m03_reference_templates" not in tables or "m03_template_rule_sets" not in tables:
        # depends_on should prevent this; skip rather than fail a partial history.
        return

    template_columns = _columns("m03_reference_templates")
    if "version_kind" not in template_columns:
        op.add_column(
            "m03_reference_templates",
            sa.Column("version_kind", sa.String(24), nullable=False, server_default="REFERENCE"),
        )
    if "parent_template_id" not in template_columns:
        op.add_column("m03_reference_templates", sa.Column("parent_template_id", sa.Integer(), nullable=True))
    if "template_metadata" not in template_columns:
        op.add_column(
            "m03_reference_templates",
            sa.Column("template_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        )
    if "provenance" not in template_columns:
        op.add_column(
            "m03_reference_templates",
            sa.Column("provenance", sa.String(64), nullable=False, server_default="Observed reference property"),
        )
    if "ix_m03_reference_templates_parent" not in _indexes("m03_reference_templates"):
        op.create_index("ix_m03_reference_templates_parent", "m03_reference_templates", ["parent_template_id"])

    rule_columns = _columns("m03_template_rule_sets")
    if "rule_version" not in rule_columns:
        op.add_column(
            "m03_template_rule_sets",
            sa.Column("rule_version", sa.Integer(), nullable=False, server_default="1"),
        )
    if "content_hash" not in rule_columns:
        op.add_column(
            "m03_template_rule_sets",
            sa.Column("content_hash", sa.String(64), nullable=False, server_default=""),
        )
    if "provenance" not in rule_columns:
        op.add_column(
            "m03_template_rule_sets",
            sa.Column("provenance", sa.String(64), nullable=False, server_default="Observed reference property"),
        )
    if "ix_m03_template_rule_sets_version" not in _indexes("m03_template_rule_sets"):
        op.create_index(
            "ix_m03_template_rule_sets_version",
            "m03_template_rule_sets",
            ["reference_template_id", "rule_version"],
        )
    if "uq_m03_template_rule_version_key" not in _constraints("m03_template_rule_sets"):
        op.create_unique_constraint(
            "uq_m03_template_rule_version_key",
            "m03_template_rule_sets",
            ["reference_template_id", "rule_version", "rule_key"],
        )


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "m03_template_rule_sets" in tables:
        op.drop_constraint("uq_m03_template_rule_version_key", "m03_template_rule_sets", type_="unique")
        op.drop_index("ix_m03_template_rule_sets_version", table_name="m03_template_rule_sets")
        op.drop_column("m03_template_rule_sets", "provenance")
        op.drop_column("m03_template_rule_sets", "content_hash")
        op.drop_column("m03_template_rule_sets", "rule_version")
    if "m03_reference_templates" in tables:
        op.drop_index("ix_m03_reference_templates_parent", table_name="m03_reference_templates")
        op.drop_column("m03_reference_templates", "provenance")
        op.drop_column("m03_reference_templates", "template_metadata")
        op.drop_column("m03_reference_templates", "parent_template_id")
        op.drop_column("m03_reference_templates", "version_kind")
