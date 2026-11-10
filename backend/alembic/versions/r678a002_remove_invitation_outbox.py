"""Remove the transactional outbox belonging to retired invitations."""

from alembic import op


revision = "r678a002"
down_revision = "r678a001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS invitation_outbox CASCADE")


def downgrade() -> None:
    raise NotImplementedError("The retired invitation outbox cannot be restored.")
