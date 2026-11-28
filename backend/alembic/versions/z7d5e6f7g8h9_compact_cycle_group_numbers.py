"""Compact cycle-local student group numbers."""

import re

from alembic import op
import sqlalchemy as sa


revision = "z7d5e6f7g8h9"
down_revision = "z7d4e5f6g7h8"
branch_labels = None
depends_on = None


def _generated_name(display_name: str, code: str, academic_year: int | None, session: str | None, number: int) -> str:
    year = academic_year
    if year is None:
        match = re.search(r"\b(?:19|20|21)\d{2}\b", f"{display_name} {code}")
        year = int(match.group(0)) if match else None
    term = (session or "").strip().upper()
    if term not in {"FALL", "SPRING"}:
        match = re.search(r"\b(FALL|SPRING)\b", f"{display_name} {code}".upper())
        term = match.group(1) if match else ""
    period = f"{term.title()} {year}" if year is not None and term else None
    return f"{period} Group {number}" if period else f"Group {number}"


def upgrade() -> None:
    connection = op.get_bind()
    cycles = connection.execute(
        sa.text("SELECT id, display_name, code, academic_year, session FROM academic_cycles ORDER BY id")
    ).mappings().all()
    for cycle in cycles:
        teams = connection.execute(
            sa.text(
                """
                SELECT id, group_number
                FROM teams
                WHERE academic_cycle_id = :cycle_id
                ORDER BY CASE WHEN status = 'dissolved' THEN 1 ELSE 0 END, created_at, id
                FOR UPDATE
                """
            ),
            {"cycle_id": cycle["id"]},
        ).mappings().all()
        if not teams:
            continue

        offset = max((row["group_number"] or 0 for row in teams), default=0) + len(teams) + 1
        for index, row in enumerate(teams, start=1):
            connection.execute(
                sa.text("UPDATE teams SET group_number = :number WHERE id = :team_id"),
                {"number": offset + index, "team_id": row["id"]},
            )
        for index, row in enumerate(teams, start=1):
            connection.execute(
                sa.text("UPDATE teams SET group_number = :number, group_name = :name WHERE id = :team_id"),
                {
                    "number": index,
                    "name": _generated_name(cycle["display_name"], cycle["code"], cycle["academic_year"], cycle["session"], index),
                    "team_id": row["id"],
                },
            )


def downgrade() -> None:
    # Group numbering is a repaired presentation invariant; restoring the old
    # gaps would be destructive and cannot be inferred safely.
    pass
