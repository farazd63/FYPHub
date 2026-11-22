"""Add rich message kinds and payloads to private collaboration channels."""

from alembic import op
import sqlalchemy as sa


revision = "z7p8q9r0s1t2"
down_revision = "z7o8p9q0r1s2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "collaboration_messages",
        sa.Column("message_kind", sa.String(length=24), nullable=False, server_default="TEXT"),
    )
    op.add_column(
        "collaboration_messages",
        sa.Column("message_payload", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("collaboration_messages", "message_payload")
    op.drop_column("collaboration_messages", "message_kind")
