"""Merge the Alembic history into the current application head.

Joins:
- u789a001 (legacy merge revision already used by existing deployments)
"""

from alembic import op


revision = "sj3k4l5m6n7o"
down_revision = "u789a001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Schema changes live on the parent branches; this revision only unifies heads.
    pass


def downgrade() -> None:
    pass
