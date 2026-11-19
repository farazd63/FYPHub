"""Merge the three Alembic heads into a single head.

Joins:
- fb1c2d3e4f5 (Module 03 compliance tables + historical archive fields)
- qa1b2c3d4e5f (Module 2 collaboration completion / Module 3 workspace)
- ri2d3e4f5a6b (archive import, document lifecycle, collaboration read markers)
"""

from alembic import op


revision = "sj3k4l5m6n7o"
down_revision = ("fb1c2d3e4f5", "qa1b2c3d4e5f", "ri2d3e4f5a6b")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Schema changes live on the parent branches; this revision only unifies heads.
    pass


def downgrade() -> None:
    pass
