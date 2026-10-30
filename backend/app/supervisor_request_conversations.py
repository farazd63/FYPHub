"""Request-scoped conversation endpoints with server-side authorization."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user, validate_mutating_origin
from .database import get_db
from .models import SupervisorRequest, SupervisorRequestMessage, Team, User, UserRole

router = APIRouter(prefix="/api/v1/supervisor-requests")


class RequestMessageWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=4000, strict=True)

    @field_validator("body")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank.")
        return value


def _request_for_actor(session: Session, request_id: int, actor: User, *, lock: bool = False) -> SupervisorRequest:
    statement = select(SupervisorRequest).where(SupervisorRequest.id == request_id)
    if lock:
        statement = statement.with_for_update()
    row = session.scalar(statement)
    if row is None:
        raise HTTPException(status_code=404, detail="Supervisor request was not found.")
    team = session.scalar(select(Team).where(Team.shared_user_id == actor.id)) if actor.role == UserRole.STUDENT else None
    allowed = (
        actor.role in (UserRole.ADMIN, UserRole.COORDINATOR)
        or (actor.role == UserRole.SUPERVISOR and row.supervisor_id == actor.id)
        or (actor.role == UserRole.STUDENT and (row.requester_user_id == actor.id or (team is not None and row.team_id == team.id)))
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="This request conversation is not accessible.")
    return row


def _message_out(session: Session, message: SupervisorRequestMessage) -> dict:
    sender = session.get(User, message.sender_id)
    return {"id": message.id, "request_id": message.request_id, "sender_id": message.sender_id, "sender_name": sender.full_name if sender else "Unknown", "sender_role": sender.role.value if sender else None, "body": message.body, "created_at": message.created_at}


@router.get("/{request_id}/conversation")
def conversation_history(request_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    _request_for_actor(session, request_id, actor)
    rows = session.scalars(select(SupervisorRequestMessage).where(SupervisorRequestMessage.request_id == request_id).order_by(SupervisorRequestMessage.id)).all()
    return [_message_out(session, row) for row in rows]


@router.post("/{request_id}/conversation", status_code=status.HTTP_201_CREATED)
def send_conversation_message(request_id: int, payload: RequestMessageWrite, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    try:
        if actor.role not in (UserRole.STUDENT, UserRole.SUPERVISOR):
            raise HTTPException(status_code=403, detail="This conversation is read-only for your role.")
        _request_for_actor(session, request_id, actor, lock=True)
        message = SupervisorRequestMessage(request_id=request_id, sender_id=actor.id, body=payload.body)
        session.add(message)
        session.flush()
        from .main import add_admin_audit_event
        add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type="SUPERVISOR_REQUEST", target_id=request_id, action="supervisor_request_message_sent", changed_values={"message_id": message.id})
        session.commit()
        session.refresh(message)
        return _message_out(session, message)
    except HTTPException:
        session.rollback()
        raise
    except Exception as error:
        session.rollback()
        raise HTTPException(status_code=500, detail="Request conversation message could not be saved.") from error
