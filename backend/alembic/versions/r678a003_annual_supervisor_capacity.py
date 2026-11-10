"""Make supervisor capacity annual and shared across Fall and Spring."""

from alembic import op
import sqlalchemy as sa


revision = "r678a003"
down_revision = "r678a002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing policy rows were period-specific.  Backfill their year, merge
    # Fall/Spring rows into one annual policy, and retain the largest configured
    # capacity so migration never silently reduces an existing limit.
    op.execute(
        """
        UPDATE supervisor_capacity_policies AS policy
        SET academic_year = cycle.academic_year
        FROM academic_cycles AS cycle
        WHERE policy.academic_year IS NULL
          AND policy.academic_cycle_id = cycle.id
          AND cycle.academic_year IS NOT NULL
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   max(max_group_capacity) OVER (PARTITION BY supervisor_id, academic_year) AS merged_capacity,
                   row_number() OVER (PARTITION BY supervisor_id, academic_year ORDER BY id) AS row_number
            FROM supervisor_capacity_policies
            WHERE academic_year IS NOT NULL
        )
        UPDATE supervisor_capacity_policies AS policy
        SET max_group_capacity = ranked.merged_capacity
        FROM ranked
        WHERE policy.id = ranked.id
          AND ranked.row_number = 1
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (PARTITION BY supervisor_id, academic_year ORDER BY id) AS row_number
            FROM supervisor_capacity_policies
            WHERE academic_year IS NOT NULL
        )
        DELETE FROM supervisor_capacity_policies AS policy
        USING ranked
        WHERE policy.id = ranked.id
          AND ranked.row_number > 1
        """
    )
    op.execute("DROP INDEX IF EXISTS uq_supervisor_capacity_policies_supervisor_period")
    op.execute("ALTER TABLE supervisor_capacity_policies DROP CONSTRAINT IF EXISTS uq_supervisor_capacity_policies_supervisor_cycle")
    op.execute("ALTER TABLE supervisor_capacity_policies DROP CONSTRAINT IF EXISTS ck_supervisor_capacity_policies_session_valid")
    op.execute("ALTER TABLE supervisor_capacity_policies DROP COLUMN IF EXISTS session")
    op.execute(
        """
        ALTER TABLE supervisor_capacity_policies
        ADD CONSTRAINT uq_supervisor_capacity_policies_supervisor_year
        UNIQUE (supervisor_id, academic_year)
        """
    )

    op.add_column("supervisor_assignments", sa.Column("academic_year", sa.Integer(), nullable=True))
    op.add_column("supervisor_assignments", sa.Column("session", sa.String(length=16), nullable=True))
    op.execute(
        """
        UPDATE supervisor_assignments AS assignment
        SET academic_year = cycle.academic_year,
            session = cycle.session
        FROM academic_cycles AS cycle
        WHERE assignment.academic_cycle_id = cycle.id
        """
    )
    op.create_check_constraint(
        "ck_supervisor_assignments_year_valid",
        "supervisor_assignments",
        "academic_year IS NULL OR academic_year BETWEEN 1900 AND 2200",
    )
    op.create_check_constraint(
        "ck_supervisor_assignments_session_valid",
        "supervisor_assignments",
        "session IS NULL OR session IN ('FALL','SPRING')",
    )
    op.create_index("ix_supervisor_assignments_supervisor_year_session", "supervisor_assignments", ["supervisor_id", "academic_year", "session"])


def downgrade() -> None:
    op.drop_constraint("ck_supervisor_assignments_session_valid", "supervisor_assignments", type_="check")
    op.drop_constraint("ck_supervisor_assignments_year_valid", "supervisor_assignments", type_="check")
    op.drop_index("ix_supervisor_assignments_supervisor_year_session", table_name="supervisor_assignments")
    op.drop_column("supervisor_assignments", "session")
    op.drop_column("supervisor_assignments", "academic_year")
    op.drop_constraint("uq_supervisor_capacity_policies_supervisor_year", "supervisor_capacity_policies", type_="unique")
    op.add_column("supervisor_capacity_policies", sa.Column("session", sa.String(length=16), nullable=True))
    op.create_index("uq_supervisor_capacity_policies_supervisor_period", "supervisor_capacity_policies", ["supervisor_id", "academic_year", "session"], unique=True, postgresql_where=sa.text("academic_year IS NOT NULL AND session IS NOT NULL"))
