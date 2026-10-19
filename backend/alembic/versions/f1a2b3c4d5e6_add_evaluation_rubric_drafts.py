"""add evaluation rubric draft versions

Revision ID: f1a2b3c4d5e6
Revises: e8f9a0b1c2d3
"""

from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4d5e6"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_rubrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "evaluation_rubric_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rubric_id", sa.Integer(), sa.ForeignKey("evaluation_rubrics.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("rubric_id", "version_number", name="uq_evaluation_rubric_version"),
    )
    op.create_table(
        "evaluation_rubric_criteria",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rubric_version_id", sa.Integer(), sa.ForeignKey("evaluation_rubric_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("rubric_version_id", "display_order", name="uq_evaluation_rubric_criterion_order"),
    )


def downgrade() -> None:
    op.drop_table("evaluation_rubric_criteria")
    op.drop_table("evaluation_rubric_versions")
    op.drop_table("evaluation_rubrics")
