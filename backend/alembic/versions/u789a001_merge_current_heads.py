"""Merge the active migration branches into one application head."""


from alembic import op


revision = "u789a001"
down_revision = (
    "fb1c2d3e4f5",
    "qa1b2c3d4e5f",
    "tk4f5a6b7c8d",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
