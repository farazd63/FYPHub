"""Private assignment-scoped Module 2 collaboration channels."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator
from sqlalchemy.dialects.postgresql import insert
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
        # Keep indentation and line breaks in scripts/code; trim only for validation.
        return value


class ReadWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: StrictInt = Field(gt=0)


def _active_channel(session: Session, channel_id: int) -> CollaborationChannel:
    channel = session.get(CollaborationChannel, channel_id)
    if channel is None:
        raise HTTPException(404, "Collaboration channel was not found.")
    return channel


def _student_member(session: Session, actor: User, team_id: int) -> TeamMember | None:
    if actor.role != UserRole.STUDENT:
        return None
    return session.scalar(select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.is_active.is_(True), or_(TeamMember.registration_number == actor.registration_number, TeamMember.university_email == actor.email)))


def _authorize(session: Session, channel: CollaborationChannel, actor: User, *, write: bool = False) -> None:
    team = session.get(Team, channel.team_id)
    assignment = session.scalar(select(SupervisorAssignment).where(
        SupervisorAssignment.id == channel.assignment_id,
        SupervisorAssignment.team_id == channel.team_id,
        SupervisorAssignment.supervisor_id == channel.supervisor_id,
        SupervisorAssignment.ended_at.is_(None),
    ))
    accepted = _accepted_request(session, channel.team_id, channel.supervisor_id, team.academic_cycle_id) if team else None
    if channel.status != "ACTIVE" or team is None or team.status == "dissolved" or assignment is None or accepted is None:
        raise HTTPException(403, "Collaboration channel will be available after a supervisor accepts your request.")
    if actor.role == UserRole.STUDENT:
        if team.shared_user_id != actor.id and _student_member(session, actor, team.id) is None:
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


def _channel_out(session: Session, channel: CollaborationChannel, actor: User) -> dict:
    team = session.get(Team, channel.team_id)
    cycle = session.get(AcademicCycle, team.academic_cycle_id) if team else None
    members = session.scalars(select(TeamMember).where(TeamMember.team_id == channel.team_id, TeamMember.is_active.is_(True)).order_by(TeamMember.id)).all()
    supervisor = session.get(User, channel.supervisor_id)
    request = _accepted_request(session, channel.team_id, channel.supervisor_id, team.academic_cycle_id) if team else None
    last_read = session.scalar(select(CollaborationParticipant.last_read_message_id).where(CollaborationParticipant.channel_id == channel.id, CollaborationParticipant.user_id == actor.id)) or 0
    unread = session.scalar(select(func.count()).select_from(CollaborationMessage).where(CollaborationMessage.channel_id == channel.id, CollaborationMessage.deleted_at.is_(None), CollaborationMessage.sender_user_id != actor.id, CollaborationMessage.id > last_read)) or 0
    leader = next((member for member in members if member.is_creator), None)
    return {"id": channel.id, "group_id": channel.team_id, "group_name": f"{leader.full_name}'s Group" if leader else f"Group {channel.team_id}", "assignment_status": "ACCEPTED", "supervisor_id": channel.supervisor_id, "assignment_id": channel.assignment_id, "academic_year": channel.academic_year, "session": channel.session, "status": channel.status, "project_title": request.title if request else None, "group_leader": {"name": leader.full_name, "registration_number": leader.registration_number} if leader else None, "members": [{"id": member.id, "name": member.full_name, "registration_number": member.registration_number, "email": member.university_email, "is_creator": member.is_creator} for member in members], "supervisor": {"id": supervisor.id, "name": supervisor.full_name, "email": supervisor.email} if supervisor else None, "cycle_name": cycle.display_name if cycle else None, "unread_count": unread, "last_read_message_id": last_read}


def _message_out(session: Session, message: CollaborationMessage) -> dict:
    sender = session.get(User, message.sender_user_id)
    return {"id": message.id, "channel_id": message.channel_id, "sender_user_id": message.sender_user_id, "sender_name": sender.full_name if sender else "Unknown user", "sender_role": sender.role.value if sender else "UNKNOWN", "message_text": message.message_text, "attachment_reference": message.attachment_reference, "created_at": message.created_at, "updated_at": message.updated_at, "deleted_at": message.deleted_at}


def _list_channels(session: Session, actor: User) -> list[dict]:
    if actor.role == UserRole.STUDENT:
        membership = select(TeamMember.id).where(TeamMember.team_id == Team.id, TeamMember.is_active.is_(True), or_(TeamMember.registration_number == actor.registration_number, TeamMember.university_email == actor.email)).exists()
        teams = select(Team.id).where(Team.status != "dissolved", or_(Team.shared_user_id == actor.id, membership))
        rows = session.scalars(select(CollaborationChannel).where(CollaborationChannel.team_id.in_(teams), CollaborationChannel.status == "ACTIVE").order_by(CollaborationChannel.updated_at.desc(), CollaborationChannel.id.desc())).all()
    else:
        rows = session.scalars(select(CollaborationChannel).where(CollaborationChannel.supervisor_id == actor.id, CollaborationChannel.status == "ACTIVE").order_by(CollaborationChannel.updated_at.desc(), CollaborationChannel.id.desc())).all()
    result = []
    for row in rows:
        try:
            _authorize(session, row, actor)
        except HTTPException as error:
            if error.status_code == 403:
                continue
            raise
        result.append(_channel_out(session, row, actor))
    return result


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
    return _channel_out(session, channel, actor)


@router.get("/student/collaboration/channels/{channel_id}/messages")
@router.get("/supervisor/collaboration/channels/{channel_id}/messages")
def collaboration_messages(channel_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db), before_id: Annotated[int | None, Query(gt=0)] = None, limit: Annotated[int | None, Query(ge=1, le=200)] = None):
    channel = _active_channel(session, channel_id); _authorize(session, channel, actor)
    statement = select(CollaborationMessage).where(CollaborationMessage.channel_id == channel.id, CollaborationMessage.deleted_at.is_(None))
    if before_id is not None:
        statement = statement.where(CollaborationMessage.id < before_id)
    statement = statement.order_by(CollaborationMessage.id.desc())
    if limit is not None:
        statement = statement.limit(limit)
    rows = session.scalars(statement).all()
    return [_message_out(session, row) for row in reversed(rows)]


@router.post("/student/collaboration/channels/{channel_id}/messages", status_code=201)
@router.post("/supervisor/collaboration/channels/{channel_id}/messages", status_code=201)
def send_collaboration_message(channel_id: int, payload: MessageWrite, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    channel = _active_channel(session, channel_id); _authorize(session, channel, actor, write=True)
    message = CollaborationMessage(channel_id=channel.id, sender_user_id=actor.id, message_text=payload.message_text, attachment_reference=payload.attachment_reference)
    session.add(message); channel.updated_at = func.now(); session.commit(); session.refresh(message)
    return _message_out(session, message)


@router.post("/student/collaboration/channels/{channel_id}/read")
@router.post("/supervisor/collaboration/channels/{channel_id}/read")
def mark_collaboration_read(channel_id: int, payload: ReadWrite, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    channel = _active_channel(session, channel_id)
    _authorize(session, channel, actor)
    message = session.scalar(select(CollaborationMessage).where(CollaborationMessage.id == payload.message_id, CollaborationMessage.channel_id == channel.id, CollaborationMessage.deleted_at.is_(None)))
    if message is None:
        raise HTTPException(404, "Message was not found in this channel.")
    statement = insert(CollaborationParticipant).values(channel_id=channel.id, user_id=actor.id, participant_role=actor.role.value, is_active=True, last_read_message_id=message.id, last_read_at=func.now())
    session.execute(statement.on_conflict_do_update(constraint="uq_collaboration_participant_user", set_={"last_read_message_id": func.greatest(func.coalesce(CollaborationParticipant.last_read_message_id, 0), message.id), "last_read_at": func.now(), "is_active": True}))
    session.commit()
    return {"channel_id": channel.id, "last_read_message_id": session.scalar(select(CollaborationParticipant.last_read_message_id).where(CollaborationParticipant.channel_id == channel.id, CollaborationParticipant.user_id == actor.id))}
