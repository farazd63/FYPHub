"""add academic deadline configuration versions

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
"""

from alembic import op
import sqlalchemy as sa

revision = "a2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "academic_deadlines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "academic_deadline_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("academic_deadline_id", sa.Integer(), sa.ForeignKey("academic_deadlines.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("time_zone", sa.String(100), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("academic_deadline_id", "version_number", name="uq_academic_deadline_version"),
    )


def downgrade() -> None:
    op.drop_table("academic_deadline_versions")
    op.drop_table("academic_deadlines")
