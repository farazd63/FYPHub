"""add immutable Module 03 template metadata and rule version provenance"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "fg6b7c8d9e0f"
down_revision = "ff5a6b7c8d9e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("m03_reference_templates", sa.Column("version_kind", sa.String(24), nullable=False, server_default="REFERENCE"))
    op.add_column("m03_reference_templates", sa.Column("parent_template_id", sa.Integer(), nullable=True))
    op.add_column("m03_reference_templates", sa.Column("template_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("m03_reference_templates", sa.Column("provenance", sa.String(64), nullable=False, server_default="Observed reference property"))
    op.create_index("ix_m03_reference_templates_parent", "m03_reference_templates", ["parent_template_id"])
    op.add_column("m03_template_rule_sets", sa.Column("rule_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("m03_template_rule_sets", sa.Column("content_hash", sa.String(64), nullable=False, server_default=""))
    op.add_column("m03_template_rule_sets", sa.Column("provenance", sa.String(64), nullable=False, server_default="Observed reference property"))
    op.create_index("ix_m03_template_rule_sets_version", "m03_template_rule_sets", ["reference_template_id", "rule_version"])
    op.create_unique_constraint("uq_m03_template_rule_version_key", "m03_template_rule_sets", ["reference_template_id", "rule_version", "rule_key"])


def downgrade() -> None:
    op.drop_constraint("uq_m03_template_rule_version_key", "m03_template_rule_sets", type_="unique")
    op.drop_index("ix_m03_template_rule_sets_version", table_name="m03_template_rule_sets")
    op.drop_column("m03_template_rule_sets", "provenance")
    op.drop_column("m03_template_rule_sets", "content_hash")
    op.drop_column("m03_template_rule_sets", "rule_version")
    op.drop_index("ix_m03_reference_templates_parent", table_name="m03_reference_templates")
    op.drop_column("m03_reference_templates", "provenance")
    op.drop_column("m03_reference_templates", "template_metadata")
    op.drop_column("m03_reference_templates", "parent_template_id")
    op.drop_column("m03_reference_templates", "version_kind")
