from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from .auth import get_current_user, validate_mutating_origin
from .database import get_db
from .models import GroupMessage, SupervisorAssignment, Team, User, UserRole

router = APIRouter(prefix="/api/v1/group-channels")
class Channel(str, Enum):
    general = "general"
    proposal = "proposal"
    research = "research"
    supervisor_discussion = "supervisor_discussion"
    tasks_progress = "tasks_progress"
    files_resources = "files_resources"
    announcements_deadlines = "announcements_deadlines"
class MessageWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=4000, strict=True)
    @field_validator("body")
    @classmethod
    def nonblank(cls, value):
        if not value.strip(): raise ValueError("Message cannot be blank.")
        return value

def permission(session, actor, team_id, channel, write=False):
    team = session.get(Team, team_id)
    if team and actor.role == UserRole.STUDENT and team.shared_user_id == actor.id:
        return "TEAM"
    if team and actor.role == UserRole.SUPERVISOR and channel != Channel.general and not (write and channel == Channel.announcements_deadlines):
        assignment = session.execute(select(SupervisorAssignment).where(SupervisorAssignment.team_id == team.id, SupervisorAssignment.supervisor_id == actor.id, SupervisorAssignment.ended_at.is_(None)).with_for_update()).scalar_one_or_none()
        if assignment: return "SUPERVISOR"
    raise HTTPException(status_code=403, detail="Channel access is not permitted.")

def output(message):
    return {"id": message.id, "author_kind": message.author_kind, "author_id": message.author_id, "body": message.body, "created_at": message.created_at}
@router.get("/teams")
def teams(actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    if actor.role == UserRole.STUDENT:
        found = session.scalars(select(Team).where(Team.shared_user_id == actor.id).order_by(Team.id)).all()
    elif actor.role == UserRole.SUPERVISOR:
        found = session.scalars(select(Team).join(SupervisorAssignment, SupervisorAssignment.team_id == Team.id).where(SupervisorAssignment.supervisor_id == actor.id, SupervisorAssignment.ended_at.is_(None)).order_by(Team.id)).all()
    else: found = []
    return [{"id": t.id, "academic_cycle_id": t.academic_cycle_id} for t in found]
@router.get("/{team_id}/{channel}")
def history(team_id: int, channel: Channel, before_id: int | None = Query(None, gt=0), actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    permission(session, actor, team_id, channel)
    statement = select(GroupMessage).where(GroupMessage.team_id == team_id, GroupMessage.channel == channel.value)
    if before_id is not None: statement = statement.where(GroupMessage.id < before_id)
    messages = session.scalars(statement.order_by(GroupMessage.id.desc()).limit(100)).all()
    return [output(m) for m in reversed(messages)]
@router.post("/{team_id}/{channel}", status_code=201)
def send(team_id: int, channel: Channel, payload: MessageWrite, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    try:
        kind = permission(session, actor, team_id, channel, write=True)
        message = GroupMessage(team_id=team_id, channel=channel.value, author_id=actor.id, author_kind=kind, body=payload.body)
        session.add(message); session.flush(); session.commit(); session.refresh(message)
        return output(message)
    except HTTPException:
        session.rollback(); raise
    except Exception as exc:
        session.rollback(); raise HTTPException(status_code=500, detail="Message could not be saved.") from exc
