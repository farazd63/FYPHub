"""Add controlled supervision agent run records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "fl1a2b3c4d5"
down_revision = "fk0f1a2b3c4"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "supervision_agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("proposal_request_id", sa.Integer(), sa.ForeignKey("supervisor_requests.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="IDLE"),
        sa.Column("approval_status", sa.String(24), nullable=False, server_default="PENDING"),
        sa.Column("plan", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tool_calls", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("result", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_supervision_agent_runs_team_created", "supervision_agent_runs", ["team_id", "created_at"])

def downgrade() -> None:
    op.drop_index("ix_supervision_agent_runs_team_created", table_name="supervision_agent_runs")
    op.drop_table("supervision_agent_runs")
