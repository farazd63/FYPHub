"""Normalize student group names to cycle session and number."""

from alembic import op


revision = "z7r1s2t3u4v5"
down_revision = "z7q0p1q2r3s4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE teams AS team
        SET group_name = CASE
            WHEN cycle.academic_year IS NOT NULL AND upper(coalesce(cycle.session, '')) IN ('FALL', 'SPRING')
                THEN initcap(lower(cycle.session)) || ' ' || cycle.academic_year::text || ' Group ' || coalesce(team.group_number::text, team.id::text)
           WHEN lower(cycle.display_name) ~ '(fall|spring)' AND cycle.display_name ~ '[0-9]{4}'
               THEN initcap(substring(lower(cycle.display_name) from '(fall|spring)')) || ' ' || substring(cycle.display_name from '([0-9]{4})') || ' Group ' || coalesce(team.group_number::text, team.id::text)
            ELSE 'Group ' || coalesce(team.group_number::text, team.id::text)
        END
        FROM academic_cycles AS cycle
        WHERE cycle.id = team.academic_cycle_id
        """
    )


def downgrade() -> None:
    op.execute("UPDATE teams SET group_name = NULL")
