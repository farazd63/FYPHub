"""Make supervisor capacity policies cycle-scoped."""

from alembic import op


revision = "z7z0a1b2c3d4"
down_revision = "z7y9z0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_supervisor_capacity_policies_supervisor_year_legacy")
    op.execute("DROP INDEX IF EXISTS uq_supervisor_capacity_policies_supervisor_cycle")
    op.execute(
        "ALTER TABLE supervisor_capacity_policies "
        "ADD CONSTRAINT uq_supervisor_capacity_policies_supervisor_year "
        "UNIQUE (supervisor_id, academic_year)"
    )
