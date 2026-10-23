"""Team-scoped, advisory local Ollama chat."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request as UrlRequest, HTTPRedirectHandler, build_opener
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from .auth import get_current_user, validate_mutating_origin
from .config import settings
from .database import get_db
from .group_channels import MessageWrite, output
from .models import GroupMessage, Team, User, UserRole

router = APIRouter(prefix="/api/v1/group-ai")

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def require_team(session, actor, team_id):
    team = session.get(Team, team_id)
    if actor.role != UserRole.STUDENT or team is None or team.shared_user_id != actor.id:
        raise HTTPException(status_code=403, detail="Team access is not permitted.")

def unavailable():
    return HTTPException(status_code=503, detail="Group AI chatbot is unavailable. Check the configured local runtime and model.")

def generate(question):
    url = settings.ollama_url.strip().rstrip("/")
    model = settings.ollama_model.strip()
    try:
        parts = urlsplit(url)
        if not model or parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost", "::1") or parts.username or parts.password or parts.query or parts.fragment:
            raise unavailable()
        payload = json.dumps({"model": model, "stream": False, "messages": [{"role": "system", "content": "You are an advisory group assistant. Your output is AI-generated advice, not an academic decision."}, {"role": "user", "content": question}]}).encode("utf-8")
        request = UrlRequest(url + "/api/chat", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            raw = response.read(65537)
        if len(raw) > 65536: raise ValueError("response too large")
        data = json.loads(raw)
        content = data["message"]["content"]
        if not isinstance(content, str) or not content.strip() or len(content) > 16000: raise ValueError("invalid response")
        return content
    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError, UnicodeError, URLError, HTTPError, TimeoutError, OSError):
        raise unavailable() from None

@router.get("/{team_id}")
def history(team_id: int, before_id: int | None = Query(None, gt=0), actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    require_team(session, actor, team_id)
    query = select(GroupMessage).where(GroupMessage.team_id == team_id, GroupMessage.channel == "group_ai")
    if before_id is not None: query = query.where(GroupMessage.id < before_id)
    return [output(row) for row in reversed(session.scalars(query.order_by(GroupMessage.id.desc()).limit(100)).all())]

@router.post("/{team_id}", status_code=201)
def chat(team_id: int, payload: MessageWrite, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    require_team(session, actor, team_id)
    answer = generate(payload.body)
    try:
        user_message = GroupMessage(team_id=team_id, channel="group_ai", author_id=actor.id, author_kind="TEAM", body=payload.body)
        ai_message = GroupMessage(team_id=team_id, channel="group_ai", author_id=actor.id, author_kind="AI", body=answer)
        session.add_all([user_message, ai_message]); session.flush(); session.commit()
        session.refresh(user_message); session.refresh(ai_message)
        return {"question": output(user_message), "answer": output(ai_message)}
    except Exception:
        session.rollback()
        raise HTTPException(status_code=500, detail="Group AI conversation could not be saved.") from None
