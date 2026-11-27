"""Remove the retired multi-channel and agent-supervision tables."""

from alembic import op


revision = "z7u4v5w6x7y8"
down_revision = "z7t3u4v5w6x7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in (
        "group_messages",
        "module2_channel_reads",
        "supervision_agent_runs",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")


def downgrade() -> None:
    # Retired data is intentionally not recreated. Historical migrations remain
    # available for fresh installations that need the old schema history.
    pass
