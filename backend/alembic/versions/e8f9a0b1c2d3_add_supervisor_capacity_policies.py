"""add supervisor capacity policies"""

from alembic import op
import sqlalchemy as sa

revision = "e8f9a0b1c2d3"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "supervisor_capacity_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("max_group_capacity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("max_group_capacity > 0", name="ck_supervisor_capacity_policies_capacity_positive"),
        sa.UniqueConstraint("supervisor_id", "academic_cycle_id", name="uq_supervisor_capacity_policies_supervisor_cycle"),
    )


def downgrade():
    op.drop_table("supervisor_capacity_policies")
