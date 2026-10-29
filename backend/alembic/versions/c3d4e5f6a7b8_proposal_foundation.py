"""Add non-operational proposal identity and version foundations.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("proposal_type", sa.String(5), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("proposal_type IN ('SHORT', 'LONG')", name="ck_proposals_type"),
    )
    op.create_table(
        "proposal_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("proposals.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("proposal_id", "version_number", name="uq_proposal_version_number"),
        sa.CheckConstraint("version_number > 0", name="ck_proposal_version_positive"),
    )


def downgrade():
    op.drop_table("proposal_versions")
    op.drop_table("proposals")
