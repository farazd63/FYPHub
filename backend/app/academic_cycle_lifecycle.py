"""Shared lifecycle guards for academic-cycle registration windows."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import utc_now
from .models import AcademicCycle, AcademicGroupPolicy


def deadline_has_passed(deadline: datetime | None, *, now: datetime | None = None) -> bool:
    """Return whether a formation/registration deadline has elapsed.

    Older rows can contain a naive timestamp.  Treat those values as UTC so a
    legacy policy cannot bypass the registration gate with a timezone error.
    """
    if deadline is None:
        return False
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return deadline <= current


def close_expired_cycle(
    session: Session,
    cycle: AcademicCycle,
    *,
    policy: AcademicGroupPolicy | None = None,
    commit: bool = False,
) -> bool:
    """Close an open cycle whose configured formation deadline has elapsed.

    The caller may request an immediate commit when the operation is about to
    reject a write.  That makes the automatic close durable even when the
    endpoint later rolls back its transaction while constructing the response.
    """
    if not getattr(cycle, "registration_open", False):
        return False
    if policy is None:
        policy = session.scalar(
            select(AcademicGroupPolicy).where(
                AcademicGroupPolicy.academic_cycle_id == cycle.id
            )
        )
    deadline = getattr(policy, "formation_deadline", None) if policy is not None else None
    if not isinstance(deadline, datetime) or not deadline_has_passed(deadline):
        return False

    cycle.registration_open = False
    if commit:
        session.commit()
        session.refresh(cycle)
    return True


def close_expired_cycles(session: Session, *, cycle_id: int | None = None) -> list[int]:
    """Persist automatic closes for all open cycles (or one selected cycle)."""
    statement = select(AcademicCycle).where(AcademicCycle.registration_open.is_(True))
    if cycle_id is not None:
        statement = statement.where(AcademicCycle.id == cycle_id)
    cycles = session.scalars(statement).all()
    closed_ids: list[int] = []
    for cycle in cycles:
        if close_expired_cycle(session, cycle):
            closed_ids.append(cycle.id)
    if closed_ids:
        session.commit()
    return closed_ids
