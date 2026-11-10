"""Persist advisory AI review runs for supervisor proposal requests."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "mo8r9e0f1a2b"
down_revision = ("mn7c8d9e0f1a", "ff5a6b7c8d9e")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proposal_ai_review_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposal_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("runtime", sa.String(128), nullable=False),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_proposal_ai_review_runs_proposal", "proposal_ai_review_runs", ["proposal_id"])


def downgrade() -> None:
    op.drop_index("ix_proposal_ai_review_runs_proposal", table_name="proposal_ai_review_runs")
    op.drop_table("proposal_ai_review_runs")
