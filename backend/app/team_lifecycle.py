"""Deterministic Module 2 lifecycle helpers shared by modules 2, 3 and 5."""
from datetime import datetime, timezone
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from .models import AcademicGroupPolicy, Team, TeamMember


def refresh_team_status(session: Session, team: Team) -> str:
    if team.status in {"locked", "dissolved"}:
        return team.status
    policy = session.scalar(select(AcademicGroupPolicy).where(AcademicGroupPolicy.academic_cycle_id == team.academic_cycle_id))
    count = session.scalar(select(func.count()).select_from(TeamMember).where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True))) or 0
    team.status = "complete" if policy and count >= policy.min_group_size else "forming"
    return team.status


def lock_team(session: Session, team_id: int, reason: str) -> Team | None:
    team = session.scalar(select(Team).where(Team.id == team_id).with_for_update())
    if team is None:
        return None
    if team.status != "dissolved":
        team.status = "locked"
        team.locked_at = datetime.now(timezone.utc)
        team.lock_reason = reason[:64]
    return team


def cancel_open_team_requests(session: Session, team_id: int, status: str = "cancelled") -> None:
    from .models import Invitation, JoinRequest
    session.execute(update(JoinRequest).where(JoinRequest.team_id == team_id, JoinRequest.status == "pending").values(status=status))
    session.execute(update(Invitation).where(Invitation.team_id == team_id, Invitation.status == "pending").values(status=status))
