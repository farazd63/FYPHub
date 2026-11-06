"""Complete Module 2 workspace endpoints and cross-module lifecycle surface."""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from .auth import get_current_user, require_roles, utc_now, validate_mutating_origin
from .database import get_db
from .group_channels import Channel
from .models import AcademicDeadline, AcademicDeadlineVersion, AcademicGroupPolicy, GroupMessage, Module2ChannelRead, Module2Notification, ProposalComplianceReport, ProposalComplianceSubmission, ProjectTask, SupervisorAssignment, Team, TeamMember, User, UserRole
from .team_lifecycle import cancel_open_team_requests, refresh_team_status

router = APIRouter(prefix="/api/v1/module-2", tags=["module-2-collaboration"])


def team_for_actor(session: Session, actor: User, team_id: int | None = None, *, lock: bool = False) -> Team:
    if actor.role != UserRole.STUDENT:
        raise HTTPException(403, "Student team access is required.")
    query = select(Team).where(Team.shared_user_id == actor.id)
    if team_id is not None:
        query = query.where(Team.id == team_id)
    if lock:
        query = query.with_for_update()
    team = session.scalar(query)
    if team is None:
        raise HTTPException(404, "No active team is available.")
    refresh_team_status(session, team)
    return team


def team_payload(session: Session, team: Team) -> dict:
    policy = session.scalar(select(AcademicGroupPolicy).where(AcademicGroupPolicy.academic_cycle_id == team.academic_cycle_id))
    members = session.scalars(select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True)).order_by(TeamMember.id)).all()
    return {
        "id": team.id, "academic_cycle_id": team.academic_cycle_id, "status": team.status,
        "locked_at": team.locked_at, "lock_reason": team.lock_reason,
        "min_group_size": policy.min_group_size if policy else None, "max_group_size": policy.max_group_size if policy else None,
        "formation_deadline": policy.formation_deadline if policy else None,
        "formation_deadline_passed": bool(policy and policy.formation_deadline and policy.formation_deadline <= utc_now() and team.status == "forming"),
        "members": [{"id": m.id, "student_id": m.student_id, "name": m.full_name, "registration_number": m.registration_number, "email": m.university_email, "is_creator": m.is_creator} for m in members],
        "channels": [{"id": item.value, "label": item.value.replace("_", " ").title()} for item in Channel],
    }


@router.get("/workspace")
def workspace(actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    team = team_for_actor(session, actor)
    result = team_payload(session, team)
    session.commit()
    return result


class TransferLeadership(BaseModel):
    member_id: int = Field(gt=0)

class LeaveTeam(BaseModel):
    new_leader_member_id: int | None = Field(default=None, gt=0)


@router.post("/teams/{team_id}/transfer-leadership")
def transfer_leadership(team_id: int, payload: TransferLeadership, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    team = team_for_actor(session, actor, team_id, lock=True)
    if team.status == "locked":
        raise HTTPException(409, "A locked team cannot transfer leadership.")
    current = session.scalar(select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.is_creator.is_(True), TeamMember.is_active.is_(True)).with_for_update())
    target = session.scalar(select(TeamMember).where(TeamMember.id == payload.member_id, TeamMember.team_id == team.id, TeamMember.is_active.is_(True)).with_for_update())
    if not current or target is None:
        raise HTTPException(400, "The leadership transfer target is not an active team member.")
    current.is_creator = False
    target.is_creator = True
    session.commit()
    return {"team_id": team.id, "leader_member_id": target.id, "status": team.status}


@router.post("/teams/{team_id}/dissolve")
def dissolve(team_id: int, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    team = team_for_actor(session, actor, team_id, lock=True)
    if team.status == "locked":
        raise HTTPException(409, "A locked team cannot be dissolved.")
    team.status = "dissolved"
    for member in session.scalars(select(TeamMember).where(TeamMember.team_id == team.id).with_for_update()).all():
        member.is_active = False
    cancel_open_team_requests(session, team.id)
    session.commit()
    return {"team_id": team.id, "status": team.status}


@router.post("/teams/{team_id}/leave")
def leave_team(team_id: int, payload: LeaveTeam, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    team = team_for_actor(session, actor, team_id, lock=True)
    if team.status == "locked":
        raise HTTPException(409, "A locked team cannot change leadership.")
    leader = session.scalar(select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.is_creator.is_(True), TeamMember.is_active.is_(True)).with_for_update())
    active = session.scalars(select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True)).with_for_update()).all()
    if leader is None or len(active) <= 1:
        team.status = "dissolved"
        for member in active:
            member.is_active = False
        cancel_open_team_requests(session, team.id)
        session.commit()
        return {"team_id": team.id, "status": team.status}
    target = session.scalar(select(TeamMember).where(TeamMember.id == payload.new_leader_member_id, TeamMember.team_id == team.id, TeamMember.is_active.is_(True)).with_for_update()) if payload.new_leader_member_id else None
    if target is None or target.id == leader.id:
        raise HTTPException(400, "Select an active member to receive leadership before leaving.")
    leader.is_creator = False
    target.is_creator = True
    leader.is_active = False
    refresh_team_status(session, team)
    session.commit()
    return {"team_id": team.id, "status": team.status, "leader_member_id": target.id}


@router.get("/notifications")
def notifications(unread_only: bool = False, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    query = select(Module2Notification).where(Module2Notification.recipient_user_id == actor.id)
    if unread_only:
        query = query.where(Module2Notification.read_at.is_(None))
    rows = session.scalars(query.order_by(Module2Notification.id.desc()).limit(100)).all()
    return [{"id": row.id, "kind": row.kind, "payload": row.payload, "read_at": row.read_at, "created_at": row.created_at} for row in rows]


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.scalar(select(Module2Notification).where(Module2Notification.id == notification_id, Module2Notification.recipient_user_id == actor.id).with_for_update())
    if row is None:
        raise HTTPException(404, "Notification not found.")
    row.read_at = utc_now(); session.commit()
    return {"id": row.id, "read_at": row.read_at}


@router.post("/teams/{team_id}/{channel}/read")
def mark_channel_read(team_id: int, channel: Channel, request: Request, message_id: int | None = None, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    team = team_for_actor(session, actor, team_id)
    row = session.scalar(select(Module2ChannelRead).where(Module2ChannelRead.user_id == actor.id, Module2ChannelRead.team_id == team.id, Module2ChannelRead.channel == channel.value).with_for_update())
    if row is None:
        row = Module2ChannelRead(user_id=actor.id, team_id=team.id, channel=channel.value)
        session.add(row)
    row.last_read_message_id = message_id
    session.commit()
    return {"team_id": team.id, "channel": channel.value, "last_read_message_id": row.last_read_message_id}


@router.get("/teams/{team_id}/unread")
def unread_counts(team_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    team = team_for_actor(session, actor, team_id)
    result = {}
    for channel in Channel:
        read = session.scalar(select(Module2ChannelRead.last_read_message_id).where(Module2ChannelRead.user_id == actor.id, Module2ChannelRead.team_id == team.id, Module2ChannelRead.channel == channel.value))
        query = select(func.count()).select_from(GroupMessage).where(GroupMessage.team_id == team.id, GroupMessage.channel == channel.value)
        if read is not None:
            query = query.where(GroupMessage.id > read)
        result[channel.value] = session.scalar(query) or 0
    return result


@router.get("/teams/{team_id}/proposal-versions")
def proposal_versions(team_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    team = team_for_actor(session, actor, team_id)
    rows = session.scalars(select(ProposalComplianceSubmission).where((ProposalComplianceSubmission.team_id == team.id) | (ProposalComplianceSubmission.owner_user_id == team.shared_user_id)).order_by(ProposalComplianceSubmission.version.desc())).all()
    return [{"id": row.id, "proposal_key": row.proposal_key, "version": row.version, "title": row.title, "status": row.status, "score": session.scalar(select(ProposalComplianceReport.score).where(ProposalComplianceReport.submission_id == row.id))} for row in rows]


@router.get("/teams/{team_id}/tasks")
def tasks(team_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    team = team_for_actor(session, actor, team_id)
    rows = session.scalars(select(ProjectTask).where(ProjectTask.team_id == team.id).order_by(ProjectTask.due_at.nulls_last(), ProjectTask.id)).all()
    return [{"id": row.id, "title": row.title, "description": row.description, "due_at": row.due_at, "completion_percent": row.completion_percent, "owner_user_id": row.owner_user_id} for row in rows]


@router.get("/teams/{team_id}/deadlines")
def deadlines(team_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    team = team_for_actor(session, actor, team_id)
    rows = session.scalars(select(AcademicDeadlineVersion).join(AcademicDeadline, AcademicDeadline.id == AcademicDeadlineVersion.academic_deadline_id).where(AcademicDeadline.academic_cycle_id == team.academic_cycle_id).order_by(AcademicDeadlineVersion.due_at_utc)).all()
    return [{"id": row.id, "name": row.name, "description": row.description, "due_at_utc": row.due_at_utc, "time_zone": row.time_zone} for row in rows]
