"""Authenticated notifications kept outside the retired team-collaboration module."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user, utc_now, validate_mutating_origin
from .database import get_db
from .models import Module2Notification, User

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("")
def notifications(unread_only: bool = False, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    query = select(Module2Notification).where(Module2Notification.recipient_user_id == actor.id)
    if unread_only:
        query = query.where(Module2Notification.read_at.is_(None))
    rows = session.scalars(query.order_by(Module2Notification.id.desc()).limit(100)).all()
    return [{"id": row.id, "kind": row.kind, "payload": row.payload, "read_at": row.read_at, "created_at": row.created_at} for row in rows]


@router.post("/{notification_id}/read")
def mark_notification_read(notification_id: int, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.scalar(select(Module2Notification).where(Module2Notification.id == notification_id, Module2Notification.recipient_user_id == actor.id).with_for_update())
    if row is None:
        raise HTTPException(404, "Notification not found.")
    row.read_at = utc_now()
    session.commit()
    return {"id": row.id, "read_at": row.read_at}
