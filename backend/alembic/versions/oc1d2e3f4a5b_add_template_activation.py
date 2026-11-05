"""Compatibility migration for the existing template activation state."""

from alembic import op
import sqlalchemy as sa


revision = "oc1d2e3f4a5b"
down_revision = "ob1c2d3e4f5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("template_reference_versions", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("template_reference_versions", sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("template_reference_versions", sa.Column("activated_by_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_template_reference_versions_activated_by", "template_reference_versions", "users", ["activated_by_id"], ["id"], ondelete="RESTRICT")


def downgrade() -> None:
    op.drop_constraint("fk_template_reference_versions_activated_by", "template_reference_versions", type_="foreignkey")
    op.drop_column("template_reference_versions", "activated_by_id")
    op.drop_column("template_reference_versions", "activated_at")
    op.drop_column("template_reference_versions", "is_active")
