"""Add role-scoped dashboard requirements."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "gm2b3c4d5e6f"
down_revision = "fl1a2b3c4d5"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "dashboard_requirements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("academic_deadline_id", sa.Integer(), sa.ForeignKey("academic_deadlines.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("requirement_type", sa.String(24), nullable=False),
        sa.Column("module", sa.String(120), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False, server_default="MEDIUM"),
        sa.Column("role_visibility", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("assigned_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("assigned_group_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completion_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="UPCOMING"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_dashboard_requirements_cycle", "dashboard_requirements", ["academic_cycle_id"])
    op.create_index("ix_dashboard_requirements_user", "dashboard_requirements", ["assigned_user_id"])
    op.create_index("ix_dashboard_requirements_status_due", "dashboard_requirements", ["status", "due_at"])

def downgrade() -> None:
    op.drop_index("ix_dashboard_requirements_status_due", table_name="dashboard_requirements")
    op.drop_index("ix_dashboard_requirements_user", table_name="dashboard_requirements")
    op.drop_index("ix_dashboard_requirements_cycle", table_name="dashboard_requirements")
    op.drop_table("dashboard_requirements")
