"""Cycle-scoped, human-readable labels for student groups.

Database primary keys are intentionally never used as a visible group number.
Legacy teams without a stored ``group_number`` receive a deterministic ordinal
within their academic cycle based on creation order.
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .models import AcademicCycle, Team
from .team_naming import generated_group_name


def visible_group_number(session: Session, team: Team) -> int | None:
    """Return the cycle-local group number used in all user-facing labels."""

    if team.group_number is not None:
        return team.group_number

    ordering = []
    if team.created_at is not None:
        ordering.append(
            or_(
                Team.created_at < team.created_at,
                (Team.created_at == team.created_at) & (Team.id <= team.id),
            )
        )
    else:
        ordering.append(Team.id <= team.id)

    return session.scalar(
        select(func.count(Team.id)).where(
            Team.academic_cycle_id == team.academic_cycle_id,
            *ordering,
        )
    ) or None


def visible_group_name(
    session: Session,
    team: Team | None,
    cycle: AcademicCycle | None = None,
) -> str:
    """Return the canonical generated name without exposing a primary key."""

    if team is None:
        return "Group"
    resolved_cycle = cycle or session.get(AcademicCycle, team.academic_cycle_id)
    number = visible_group_number(session, team)
    if resolved_cycle is not None:
        return generated_group_name(resolved_cycle, number)
    return f"Group {number}" if number is not None else "Group"


def visible_group_code(
    session: Session,
    team: Team,
    cycle: AcademicCycle | None = None,
) -> str | None:
    """Return a cycle code plus the visible group number, never the DB ID."""

    resolved_cycle = cycle or session.get(AcademicCycle, team.academic_cycle_id)
    number = visible_group_number(session, team)
    if resolved_cycle is None or number is None:
        return None
    return f"{resolved_cycle.code}-{number}"
