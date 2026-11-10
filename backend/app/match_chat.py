"""Temporary team-to-team match conversations."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from .auth import get_current_user, utc_now, validate_mutating_origin
from .database import SessionLocal, get_db
from .group_channels import MessageWrite
from .models import AuthSession, MatchChat, MatchMessage, MatchConsent, Module2MatchReport, Team, TeamPreference, User
from .security import hash_session_token
from .team_matching import assessments, owned
from .team_compatibility import aggregate_compatibility

router = APIRouter(prefix="/api/v1/match-chats")
class OpenChat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    team_id: StrictInt = Field(gt=0)
class ReportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=2000)
def fail(status=403): return HTTPException(status, "Match chat is unavailable.")
def lock_pair(session, first, second):
    teams = session.scalars(select(Team).where(Team.id.in_([first,second])).order_by(Team.id).with_for_update()).all()
    if len(teams) != 2 or teams[0].academic_cycle_id != teams[1].academic_cycle_id: raise fail()
    profiles = [session.get(TeamPreference, team.id) for team in teams]
    if any(p is None or not p.opted_in for p in profiles): raise fail()
    return teams, profiles

def chat_access(session, actor, chat_id):
    team = owned(session, actor)
    chat = session.get(MatchChat, chat_id)
    if chat is None or team.id not in (chat.team_a_id, chat.team_b_id): raise fail()
    lock_pair(session, chat.team_a_id, chat.team_b_id)
    session.refresh(chat)
    if chat.closed_at is not None: raise fail()
    return team, chat

def chat_out(chat, team_id):
    return {"id":chat.id, "other_team_id":chat.team_b_id if team_id == chat.team_a_id else chat.team_a_id, "created_at":chat.created_at, "closed_at":chat.closed_at}
@router.get("")
def listing(actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    team = owned(session,actor)
    rows = session.scalars(select(MatchChat).where(or_(MatchChat.team_a_id == team.id, MatchChat.team_b_id == team.id)).order_by(MatchChat.id)).all()
    result = []
    for row in rows:
        try: chat_access(session, actor, row.id); result.append(chat_out(row,team.id))
        except HTTPException: pass
    return result
@router.post("", status_code=201)
def open_chat(payload: OpenChat, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    try:
        team = owned(session,actor)
        if team.id == payload.team_id: raise fail()
        teams, profiles = lock_pair(session,team.id,payload.team_id)
        if not aggregate_compatibility(assessments(profiles[0].answers,profiles[1].answers))["matched"]: raise fail()
        chat = session.scalar(select(MatchChat).where(MatchChat.team_a_id == teams[0].id, MatchChat.team_b_id == teams[1].id, MatchChat.closed_at.is_(None)))
        if chat: return {"status": "open", "chat": chat_out(chat, team.id)}
        previous = session.scalar(select(MatchChat).where(MatchChat.team_a_id == teams[0].id, MatchChat.team_b_id == teams[1].id).order_by(MatchChat.id.desc()).limit(1))
        if previous:
            consent = session.scalar(select(MatchConsent).where(MatchConsent.closed_chat_id == previous.id, MatchConsent.team_id == team.id))
            if not consent: session.add(MatchConsent(closed_chat_id=previous.id, team_id=team.id)); session.flush()
            consents = session.scalars(select(MatchConsent.team_id).where(MatchConsent.closed_chat_id == previous.id)).all()
            if set(consents) != {teams[0].id, teams[1].id}:
                session.commit(); return {"status": "awaiting_other_team", "chat": None}
        chat=MatchChat(team_a_id=teams[0].id,team_b_id=teams[1].id); session.add(chat); session.flush(); session.commit(); session.refresh(chat); return {"status": "open", "chat": chat_out(chat,team.id)}
    except HTTPException: session.rollback(); raise
    except Exception: session.rollback(); raise HTTPException(500,"Match chat could not be opened.") from None
@router.get("/{chat_id}/messages")
def messages(chat_id:int, before_id:int|None=Query(None,gt=0), actor:User=Depends(get_current_user), session:Session=Depends(get_db)):
    chat_access(session,actor,chat_id)
    q=select(MatchMessage).where(MatchMessage.chat_id==chat_id)
    if before_id: q=q.where(MatchMessage.id<before_id)
    rows=session.scalars(q.order_by(MatchMessage.id.desc()).limit(100)).all()
    return [{"id":m.id,"team_id":m.team_id,"body":m.body,"created_at":m.created_at} for m in reversed(rows)]
@router.post("/{chat_id}/messages",status_code=201)
def send(chat_id:int,payload:MessageWrite,request:Request,actor:User=Depends(get_current_user),session:Session=Depends(get_db)):
    validate_mutating_origin(request)
    try:
        team, chat=chat_access(session,actor,chat_id)
        if chat.closed_at: raise HTTPException(409,"Match chat is closed.")
        message=MatchMessage(chat_id=chat.id,team_id=team.id,body=payload.body);session.add(message);session.flush();session.commit();session.refresh(message)
        return {"id":message.id,"team_id":message.team_id,"body":message.body,"created_at":message.created_at}
    except HTTPException: session.rollback(); raise
    except Exception: session.rollback(); raise HTTPException(500,"Message could not be saved.") from None
@router.post("/{chat_id}/close")
def close(chat_id:int,request:Request,actor:User=Depends(get_current_user),session:Session=Depends(get_db)):
    validate_mutating_origin(request)
    try:
        _,chat=chat_access(session,actor,chat_id)
        if chat.closed_at: raise HTTPException(409,"Match chat is already closed.")
        chat.closed_at=utc_now(); session.commit(); return {"closed":True}
    except HTTPException: session.rollback(); raise
    except Exception: session.rollback(); raise HTTPException(500,"Match chat could not be closed.") from None

@router.post("/{chat_id}/report", status_code=201)
def report(chat_id: int, payload: ReportBody, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    try:
        team = owned(session, actor)
        chat = session.get(MatchChat, chat_id)
        if chat is None or team.id not in (chat.team_a_id, chat.team_b_id):
            raise fail()
        row = Module2MatchReport(chat_id=chat.id, reporter_user_id=actor.id, reason=payload.reason.strip())
        session.add(row); session.commit(); session.refresh(row)
        return {"id": row.id, "status": row.status}
    except HTTPException:
        session.rollback(); raise
    except Exception:
        session.rollback(); raise HTTPException(500, "Match chat report could not be saved.") from None

@router.websocket("/ws/{chat_id}")
async def websocket_messages(websocket: WebSocket, chat_id: int):
    """Live match chat transport; PostgreSQL remains the source of truth."""
    session = SessionLocal()
    try:
        token = websocket.cookies.get("fyphub_session")
        record = session.execute(select(AuthSession, User).join(User, User.id == AuthSession.user_id).where(AuthSession.token_hash == hash_session_token(token or ""))).one_or_none()
        if record is None or record[0].revoked_at is not None or record[0].expires_at <= utc_now():
            await websocket.close(code=4401); return
        actor = record[1]
        team = owned(session, actor)
        chat = session.get(MatchChat, chat_id)
        if chat is None or chat.closed_at is not None or team.id not in (chat.team_a_id, chat.team_b_id):
            await websocket.close(code=4403); return
        await websocket.accept()
        while True:
            payload = await websocket.receive_json()
            body = str(payload.get("body", "")).strip() if isinstance(payload, dict) else ""
            if not body or len(body) > 4000:
                await websocket.send_json({"error": "Message must contain 1 to 4000 characters."}); continue
            row = MatchMessage(chat_id=chat.id, team_id=team.id, body=body)
            session.add(row); session.commit(); session.refresh(row)
            await websocket.send_json({"id": row.id, "team_id": row.team_id, "body": row.body, "created_at": row.created_at.isoformat()})
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        session.close()
