"""Remove the retired history source index."""

from alembic import op


revision = "z7x8y9z0a1b2"
down_revision = "z7w7x8y9z0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_supervised_project_history_source")


def downgrade() -> None:
    pass
