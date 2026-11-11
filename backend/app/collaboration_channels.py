"""Private assignment-scoped Module 2 collaboration channels."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles, validate_mutating_origin
from .database import get_db
from .models import AcademicCycle, CollaborationChannel, CollaborationMessage, CollaborationParticipant, SupervisorAssignment, SupervisorRequest, Team, TeamMember, User, UserRole

router = APIRouter(prefix="/api/v1", tags=["module-2-private-collaboration"])


class MessageWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_text: str = Field(min_length=1, max_length=4000)
    attachment_reference: str | None = Field(default=None, max_length=500)

    @field_validator("message_text")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be blank.")
        return value.strip()


def _active_channel(session: Session, channel_id: int) -> CollaborationChannel:
    channel = session.get(CollaborationChannel, channel_id)
    if channel is None:
        raise HTTPException(404, "Collaboration channel was not found.")
    return channel


def _student_member(session: Session, actor: User, team_id: int) -> TeamMember | None:
    if actor.role != UserRole.STUDENT or not actor.registration_number:
        return None
    return session.scalar(select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.is_active.is_(True), or_(TeamMember.registration_number == actor.registration_number, TeamMember.university_email == actor.email)))


def _authorize(session: Session, channel: CollaborationChannel, actor: User, *, write: bool = False) -> None:
    if actor.role == UserRole.STUDENT:
        team = session.get(Team, channel.team_id)
        if team is None or team.status == "dissolved" or _student_member(session, actor, team.id) is None:
            raise HTTPException(403, "This collaboration channel is not available to your group.")
    elif actor.role == UserRole.SUPERVISOR:
        assignment = session.scalar(select(SupervisorAssignment).where(SupervisorAssignment.id == channel.assignment_id, SupervisorAssignment.team_id == channel.team_id, SupervisorAssignment.supervisor_id == actor.id, SupervisorAssignment.ended_at.is_(None)))
        if assignment is None:
            raise HTTPException(403, "This collaboration channel is not assigned to you.")
    else:
        raise HTTPException(403, "Collaboration channel access is restricted to students and supervisors.")
    if write and channel.status != "ACTIVE":
        raise HTTPException(409, "Archived collaboration channels cannot receive new messages.")


def _accepted_request(session: Session, team_id: int, supervisor_id: int, cycle_id: int) -> SupervisorRequest | None:
    return session.scalar(select(SupervisorRequest).where(SupervisorRequest.team_id == team_id, SupervisorRequest.supervisor_id == supervisor_id, SupervisorRequest.academic_cycle_id == cycle_id, SupervisorRequest.status == "ACCEPTED").order_by(SupervisorRequest.id.desc()))


def ensure_collaboration_channel(session: Session, assignment: SupervisorAssignment, team: Team) -> CollaborationChannel:
    existing = session.scalar(select(CollaborationChannel).where(CollaborationChannel.assignment_id == assignment.id, CollaborationChannel.status == "ACTIVE"))
    if existing is not None:
        return existing
    cycle = session.get(AcademicCycle, assignment.academic_cycle_id)
    if cycle is None or cycle.academic_year is None or not cycle.session:
        raise HTTPException(422, "The assigned academic cycle must have a year and session.")
    # A changed assignment archives the previous conversation but never merges it.
    previous = session.scalars(select(CollaborationChannel).where(CollaborationChannel.team_id == team.id, CollaborationChannel.status == "ACTIVE")).all()
    for channel in previous:
        channel.status = "ARCHIVED"
    channel = CollaborationChannel(team_id=team.id, supervisor_id=assignment.supervisor_id, academic_year=assignment.academic_year or cycle.academic_year, session=assignment.session or cycle.session, assignment_id=assignment.id, status="ACTIVE")
    session.add(channel); session.flush()
    members = session.scalars(select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True)).order_by(TeamMember.id)).all()
    for member in members:
        user = session.scalar(select(User).where(User.registration_number == member.registration_number, User.email == member.university_email, User.role == UserRole.STUDENT))
        session.add(CollaborationParticipant(channel_id=channel.id, user_id=user.id if user else None, team_member_id=member.id, participant_role="STUDENT", is_active=True))
    session.add(CollaborationParticipant(channel_id=channel.id, user_id=assignment.supervisor_id, participant_role="SUPERVISOR", is_active=True))
    return channel


def _channel_out(session: Session, channel: CollaborationChannel) -> dict:
    team = session.get(Team, channel.team_id)
    cycle = session.get(AcademicCycle, team.academic_cycle_id) if team else None
    members = session.scalars(select(TeamMember).where(TeamMember.team_id == channel.team_id, TeamMember.is_active.is_(True)).order_by(TeamMember.id)).all()
    supervisor = session.get(User, channel.supervisor_id)
    request = _accepted_request(session, channel.team_id, channel.supervisor_id, team.academic_cycle_id) if team else None
    unread = session.scalar(select(func.count()).select_from(CollaborationMessage).where(CollaborationMessage.channel_id == channel.id, CollaborationMessage.deleted_at.is_(None))) or 0
    return {"id": channel.id, "group_id": channel.team_id, "supervisor_id": channel.supervisor_id, "assignment_id": channel.assignment_id, "academic_year": channel.academic_year, "session": channel.session, "status": channel.status, "project_title": request.title if request else None, "group_leader": next(({"name": member.full_name, "registration_number": member.registration_number} for member in members if member.is_creator), None), "members": [{"id": member.id, "name": member.full_name, "registration_number": member.registration_number, "email": member.university_email, "is_creator": member.is_creator} for member in members], "supervisor": {"id": supervisor.id, "name": supervisor.full_name, "email": supervisor.email} if supervisor else None, "cycle_name": cycle.display_name if cycle else None, "unread_count": unread}


def _message_out(session: Session, message: CollaborationMessage) -> dict:
    sender = session.get(User, message.sender_user_id)
    return {"id": message.id, "channel_id": message.channel_id, "sender_user_id": message.sender_user_id, "sender_name": sender.full_name if sender else "Unknown user", "sender_role": sender.role.value if sender else "UNKNOWN", "message_text": message.message_text, "attachment_reference": message.attachment_reference, "created_at": message.created_at, "updated_at": message.updated_at, "deleted_at": message.deleted_at}


def _list_channels(session: Session, actor: User) -> list[dict]:
    if actor.role == UserRole.STUDENT:
        teams = select(TeamMember.team_id).join(Team, Team.id == TeamMember.team_id).where(Team.status != "dissolved", TeamMember.is_active.is_(True), or_(TeamMember.registration_number == actor.registration_number, TeamMember.university_email == actor.email))
        rows = session.scalars(select(CollaborationChannel).where(CollaborationChannel.team_id.in_(teams), CollaborationChannel.status == "ACTIVE").order_by(CollaborationChannel.updated_at.desc(), CollaborationChannel.id.desc())).all()
    else:
        rows = session.scalars(select(CollaborationChannel).where(CollaborationChannel.supervisor_id == actor.id, CollaborationChannel.status == "ACTIVE").order_by(CollaborationChannel.updated_at.desc(), CollaborationChannel.id.desc())).all()
    return [_channel_out(session, row) for row in rows]


@router.get("/student/collaboration/channels")
def student_channels(actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    return _list_channels(session, actor)


@router.get("/supervisor/collaboration/channels")
def supervisor_channels(actor: User = Depends(require_roles(UserRole.SUPERVISOR)), session: Session = Depends(get_db)):
    return _list_channels(session, actor)


@router.get("/student/collaboration/channels/{channel_id}")
@router.get("/supervisor/collaboration/channels/{channel_id}")
def collaboration_channel(channel_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    channel = _active_channel(session, channel_id); _authorize(session, channel, actor)
    return _channel_out(session, channel)


@router.get("/student/collaboration/channels/{channel_id}/messages")
@router.get("/supervisor/collaboration/channels/{channel_id}/messages")
def collaboration_messages(channel_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    channel = _active_channel(session, channel_id); _authorize(session, channel, actor)
    rows = session.scalars(select(CollaborationMessage).where(CollaborationMessage.channel_id == channel.id, CollaborationMessage.deleted_at.is_(None)).order_by(CollaborationMessage.created_at, CollaborationMessage.id)).all()
    return [_message_out(session, row) for row in rows]


@router.post("/student/collaboration/channels/{channel_id}/messages", status_code=201)
@router.post("/supervisor/collaboration/channels/{channel_id}/messages", status_code=201)
def send_collaboration_message(channel_id: int, payload: MessageWrite, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    channel = _active_channel(session, channel_id); _authorize(session, channel, actor, write=True)
    message = CollaborationMessage(channel_id=channel.id, sender_user_id=actor.id, message_text=payload.message_text, attachment_reference=payload.attachment_reference)
    session.add(message); channel.updated_at = func.now(); session.commit(); session.refresh(message)
    return _message_out(session, message)
