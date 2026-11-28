"""Allow one coordinator to be assigned to multiple academic cycles."""

from alembic import op


revision = "z7z2a3b4c5d6"
down_revision = "z7z1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_academic_cycles_coordinator_id", table_name="academic_cycles")


def downgrade() -> None:
    op.create_index(
        "uq_academic_cycles_coordinator_id",
        "academic_cycles",
        ["coordinator_id"],
        unique=True,
    )
