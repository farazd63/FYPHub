"""Add supervisor allocation history."""
from alembic import op
import sqlalchemy as sa
revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("supervisor_assignments", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("team_id", sa.Integer(), nullable=False), sa.Column("academic_cycle_id", sa.Integer(), nullable=False), sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("assigned_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("ended_at", sa.DateTime(timezone=True)), sa.Column("ended_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT")), sa.ForeignKeyConstraint(["team_id", "academic_cycle_id"], ["teams.id", "teams.academic_cycle_id"], ondelete="RESTRICT"))
    op.create_index("uq_supervisor_assignment_active_team", "supervisor_assignments", ["team_id"], unique=True, postgresql_where=sa.text("ended_at IS NULL"))

def downgrade():
    op.drop_table("supervisor_assignments")
