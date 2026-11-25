"""Backfill automatic names for legacy display-name-only cycles."""

from alembic import op


revision = "z7s2t3u4v5w6"
down_revision = "z7r1s2t3u4v5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE teams AS team
        SET group_name = initcap(substring(lower(cycle.display_name) from '(fall|spring)'))
            || ' ' || substring(cycle.display_name from '([0-9]{4})')
            || ' Group ' || coalesce(team.group_number::text, team.id::text)
        FROM academic_cycles AS cycle
        WHERE cycle.id = team.academic_cycle_id
          AND team.group_name IS NULL
          AND lower(cycle.display_name) ~ '(fall|spring)'
          AND cycle.display_name ~ '[0-9]{4}'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE teams AS team
        SET group_name = NULL
        FROM academic_cycles AS cycle
        WHERE cycle.id = team.academic_cycle_id
          AND lower(cycle.display_name) ~ '(fall|spring)'
          AND cycle.display_name ~ '[0-9]{4}'
        """
    )
