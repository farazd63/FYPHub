"""Cross-portal notification fan-out helpers.

Notifications are intentionally written in the same transaction as the
business change that caused them.  Callers should add notifications before
their existing ``session.commit()`` so a failed mutation cannot leave a false
notification behind.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import SupervisorAssignment, Team, TeamMember, User, UserRole
from .models import Module2Notification


ADMIN_ROLES = (UserRole.ADMIN, UserRole.PLATFORM_ADMIN)


def _ids(values: Iterable[int | User], *, exclude: Iterable[int] = ()) -> set[int]:
    excluded = set(exclude)
    result: set[int] = set()
    for value in values:
        user_id = value.id if isinstance(value, User) else value
        if user_id is not None and user_id not in excluded:
            result.add(int(user_id))
    return result


def notify(
    session: Session,
    recipients: Iterable[int | User],
    *,
    kind: str,
    title: str,
    message: str,
    path: str | None = None,
    exclude: Iterable[int] = (),
    **metadata: object,
) -> None:
    """Queue one notification per unique active recipient.

    The payload is deliberately stable because the header bell is shared by
    every portal.  Extra metadata is retained for deep links and future
    filtering without requiring a schema change for every new event.
    """

    payload: dict[str, object] = {
        "title": title,
        "message": message[:1000],
    }
    if path:
        payload["path"] = path
    payload.update({key: value for key, value in metadata.items() if value is not None})
    recipient_ids = _ids(recipients, exclude=exclude)
    if not recipient_ids:
        return
    active_ids = set(
        session.scalars(
            select(User.id).where(User.id.in_(recipient_ids), User.is_active.is_(True))
        ).all()
    )
    for user_id in active_ids:
        session.add(Module2Notification(recipient_user_id=user_id, kind=kind, payload=payload))


def notify_admins(session: Session, *, exclude: Iterable[int] = (), **kwargs: object) -> None:
    admins = session.scalars(
        select(User).where(User.role.in_(ADMIN_ROLES), User.is_active.is_(True))
    ).all()
    notify(session, admins, exclude=exclude, **kwargs)


def team_student_ids(session: Session, team_id: int) -> set[int]:
    team = session.get(Team, team_id)
    if team is None:
        return set()
    recipients = {team.shared_user_id}
    members = session.scalars(
        select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True))
    ).all()
    conditions = []
    registrations = [member.registration_number for member in members if member.registration_number]
    emails = [member.university_email for member in members if member.university_email]
    if registrations:
        conditions.append(User.registration_number.in_(registrations))
    if emails:
        conditions.append(User.email.in_(emails))
    if conditions:
        recipients.update(
            session.scalars(
                select(User.id).where(
                    User.role == UserRole.STUDENT,
                    User.is_active.is_(True),
                    or_(*conditions),
                )
            ).all()
        )
    return recipients


def team_supervisor_ids(session: Session, team_id: int) -> set[int]:
    return set(
        session.scalars(
            select(SupervisorAssignment.supervisor_id).where(
                SupervisorAssignment.team_id == team_id,
                SupervisorAssignment.ended_at.is_(None),
            )
        ).all()
    )


def cycle_student_ids(session: Session, cycle_id: int) -> set[int]:
    team_ids = session.scalars(
        select(Team.id).where(Team.academic_cycle_id == cycle_id, Team.status != "dissolved")
    ).all()
    recipients: set[int] = set()
    for team_id in team_ids:
        recipients.update(team_student_ids(session, team_id))
    if not recipients:
        recipients.update(
            session.scalars(
                select(User.id).where(User.role == UserRole.STUDENT, User.is_active.is_(True))
            ).all()
        )
    return recipients


def notify_team_students(session: Session, team_id: int, **kwargs: object) -> None:
    notify(session, team_student_ids(session, team_id), **kwargs)


def notify_team_supervisors(session: Session, team_id: int, **kwargs: object) -> None:
    notify(session, team_supervisor_ids(session, team_id), **kwargs)


def notify_team_stakeholders(
    session: Session,
    team_id: int,
    *,
    student_kwargs: dict[str, object] | None = None,
    supervisor_kwargs: dict[str, object] | None = None,
    admin_kwargs: dict[str, object] | None = None,
    exclude: Iterable[int] = (),
) -> None:
    """Notify the portals affected by a team-level change."""

    if student_kwargs:
        notify_team_students(session, team_id, exclude=exclude, **student_kwargs)
    if supervisor_kwargs:
        notify_team_supervisors(session, team_id, exclude=exclude, **supervisor_kwargs)
    if admin_kwargs:
        notify_admins(session, exclude=exclude, **admin_kwargs)
