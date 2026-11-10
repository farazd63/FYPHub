from enum import Enum
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
import re
from sqlalchemy import select
from sqlalchemy.orm import Session
from .auth import get_current_user, validate_mutating_origin
from .database import get_db
from .models import GroupMessage, SupervisorAssignment, Team, User, UserRole
from .config import settings

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
    thread_root_id: int | None = Field(default=None, gt=0)
    attachment_name: str | None = Field(default=None, max_length=255)
    attachment_url: str | None = Field(default=None, max_length=500)
    @field_validator("body")
    @classmethod
    def nonblank(cls, value):
        if not value.strip(): raise ValueError("Message cannot be blank.")
        return value

def permission(session, actor, team_id, channel, write=False):
    team = session.get(Team, team_id)
    if team and actor.role in (UserRole.ADMIN, UserRole.COORDINATOR):
        return actor.role.value
    if team and actor.role == UserRole.STUDENT and team.shared_user_id == actor.id:
        if write and channel == Channel.announcements_deadlines:
            raise HTTPException(status_code=403, detail="This channel is read-only for students.")
        return "TEAM"
    if team and actor.role == UserRole.SUPERVISOR and channel != Channel.general and not (write and channel == Channel.announcements_deadlines):
        assignment = session.execute(select(SupervisorAssignment).where(SupervisorAssignment.team_id == team.id, SupervisorAssignment.supervisor_id == actor.id, SupervisorAssignment.ended_at.is_(None)).with_for_update()).scalar_one_or_none()
        if assignment: return "SUPERVISOR"
    raise HTTPException(status_code=403, detail="Channel access is not permitted.")

def output(message):
    return {"id": message.id, "author_kind": message.author_kind, "author_id": message.author_id, "body": message.body, "thread_root_id": message.thread_root_id, "mentions": message.mentions or [], "attachment_name": message.attachment_name, "attachment_url": message.attachment_url, "created_at": message.created_at}


def _file_path(team_id: int, stored_name: str) -> Path:
    safe = Path(stored_name).name
    return settings.document_storage_root / "module-2" / "files" / str(team_id) / safe
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
        if payload.thread_root_id is not None:
            root = session.scalar(select(GroupMessage.id).where(GroupMessage.id == payload.thread_root_id, GroupMessage.team_id == team_id, GroupMessage.channel == channel.value))
            if root is None:
                raise HTTPException(400, "The thread does not belong to this channel.")
        mentions = sorted(set(re.findall(r"@([A-Za-z0-9_.-]{2,80})", payload.body)))
        message = GroupMessage(team_id=team_id, channel=channel.value, author_id=actor.id, author_kind=kind, body=payload.body, thread_root_id=payload.thread_root_id, mentions=mentions, attachment_name=payload.attachment_name, attachment_url=payload.attachment_url)
        session.add(message); session.flush(); session.commit(); session.refresh(message)
        return output(message)
    except HTTPException:
        session.rollback(); raise
    except Exception as exc:
        session.rollback(); raise HTTPException(status_code=500, detail="Message could not be saved.") from exc


@router.post("/{team_id}/files", status_code=201)
async def upload_file(team_id: int, request: Request, upload: UploadFile = File(...), actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    """Store a team-scoped resource and publish it into Files & Resources."""
    validate_mutating_origin(request)
    permission(session, actor, team_id, Channel.files_resources, write=True)
    data = await upload.read()
    if not data or len(data) > 10 * 1024 * 1024:
        raise HTTPException(422, "The file must be non-empty and 10 MiB or smaller.")
    original = Path(upload.filename or "resource").name
    stored = f"{uuid4().hex}-{original[:160]}"
    path = _file_path(team_id, stored)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    message = GroupMessage(team_id=team_id, channel=Channel.files_resources.value, author_id=actor.id, author_kind="TEAM" if actor.role == UserRole.STUDENT else actor.role.value, body=f"Uploaded resource: {original}", attachment_name=original, attachment_url=f"/api/v1/group-channels/{team_id}/files/{stored}")
    session.add(message)
    session.commit()
    session.refresh(message)
    return output(message)


@router.get("/{team_id}/files/{stored_name}")
def download_file(team_id: int, stored_name: str, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    permission(session, actor, team_id, Channel.files_resources)
    path = _file_path(team_id, stored_name)
    if not path.is_file():
        raise HTTPException(404, "Resource was not found.")
    return FileResponse(path, filename=path.name.split("-", 1)[-1])
