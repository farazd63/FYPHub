"""Cycle-scoped, human-readable labels for student groups.

Database primary keys are intentionally never used as a visible group number.
Legacy teams without a stored ``group_number`` receive a deterministic ordinal
within their academic cycle based on creation order.
"""

from __future__ import annotations

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from .models import AcademicCycle, Team
from .team_naming import generated_group_name


def compact_cycle_group_numbers(
    session: Session,
    cycle_id: int,
    cycle: AcademicCycle | None = None,
) -> list[Team]:
    """Keep visible group numbers contiguous within one academic cycle.

    Team IDs remain unchanged. Only the human-facing cycle-local number and
    generated name are repaired. Dissolved records are placed after active
    records so they do not create gaps in the admin group list.
    """
    teams = session.execute(
        select(Team)
        .where(Team.academic_cycle_id == cycle_id)
        .order_by(
            case((Team.status == "dissolved", 1), else_=0),
            Team.created_at,
            Team.id,
        )
        .with_for_update()
    ).scalars().all()
    if not teams:
        return []

    resolved_cycle = cycle or session.get(AcademicCycle, cycle_id)
    if resolved_cycle is None:
        return teams

    # Move values out of the destination range first. This avoids the unique
    # (academic_cycle_id, group_number) constraint while rows are reordered.
    offset = max((team.group_number or 0 for team in teams), default=0) + len(teams) + 1
    for index, team in enumerate(teams, start=1):
        team.group_number = offset + index
    session.flush()

    for index, team in enumerate(teams, start=1):
        team.group_number = index
        team.group_name = generated_group_name(resolved_cycle, index)
    session.flush()
    return teams


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
