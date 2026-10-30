"""add safe administrative metadata for the FYP registry"""

from alembic import op
import sqlalchemy as sa


revision = "fd3e4f5a6b7c"
down_revision = "fc2d3e4f5a6b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fyp_registry_metadata",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("supervisor_requests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("department_section", sa.String(length=255), nullable=True),
        sa.Column("project_scope", sa.String(length=255), nullable=True),
        sa.Column("team_label", sa.String(length=255), nullable=True),
        sa.Column("administrative_notes", sa.Text(), nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("request_id", name="uq_fyp_registry_metadata_request"),
    )
    op.create_index("ix_fyp_registry_metadata_updated_at", "fyp_registry_metadata", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_fyp_registry_metadata_updated_at", table_name="fyp_registry_metadata")
    op.drop_table("fyp_registry_metadata")
