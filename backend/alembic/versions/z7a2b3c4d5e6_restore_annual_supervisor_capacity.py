"""Restore annual supervisor capacity policies."""

from alembic import op


revision = "z7a2b3c4d5e6"
down_revision = "z7a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_supervisor_capacity_policies_supervisor_cycle")
    op.execute("DROP INDEX IF EXISTS uq_supervisor_capacity_policies_supervisor_year_legacy")
    op.execute(
        "ALTER TABLE supervisor_capacity_policies "
        "ADD CONSTRAINT uq_supervisor_capacity_policies_supervisor_year "
        "UNIQUE (supervisor_id, academic_year)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE supervisor_capacity_policies "
        "DROP CONSTRAINT IF EXISTS uq_supervisor_capacity_policies_supervisor_year"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_supervisor_capacity_policies_supervisor_cycle "
        "ON supervisor_capacity_policies (supervisor_id, academic_cycle_id) "
        "WHERE academic_cycle_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_supervisor_capacity_policies_supervisor_year_legacy "
        "ON supervisor_capacity_policies (supervisor_id, academic_year) "
        "WHERE academic_cycle_id IS NULL AND academic_year IS NOT NULL"
    )
