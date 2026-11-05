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
from .models import AcademicDeadline, AcademicDeadlineVersion, AcademicGroupPolicy, GroupMessage, ProjectTask, SupervisorAssignment, Team, User, UserRole

router = APIRouter(prefix="/api/v1/group-ai")

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def require_team(session, actor, team_id):
    team = session.get(Team, team_id)
    if team is None or not (actor.role in (UserRole.ADMIN, UserRole.COORDINATOR) or (actor.role == UserRole.STUDENT and team.shared_user_id == actor.id)):
        raise HTTPException(status_code=403, detail="Team access is not permitted.")
    return team


def scoped_context(session, team):
    messages = session.scalars(select(GroupMessage).where(GroupMessage.team_id == team.id, GroupMessage.channel != "group_ai").order_by(GroupMessage.id.desc()).limit(60)).all()
    policy = session.scalar(select(AcademicGroupPolicy).where(AcademicGroupPolicy.academic_cycle_id == team.academic_cycle_id))
    deadlines = session.scalars(select(AcademicDeadlineVersion).join(AcademicDeadline, AcademicDeadline.id == AcademicDeadlineVersion.academic_deadline_id).where(AcademicDeadline.academic_cycle_id == team.academic_cycle_id).order_by(AcademicDeadlineVersion.due_at_utc)).all()
    tasks = session.scalars(select(ProjectTask).where(ProjectTask.team_id == team.id).order_by(ProjectTask.due_at.nulls_last()).limit(40)).all()
    return {
        "team_id": team.id,
        "cycle_id": team.academic_cycle_id,
        "group_policy": {"min_size": policy.min_group_size, "max_size": policy.max_group_size} if policy else {},
        "deadlines": [{"name": version.name, "due_at": version.due_at_utc.isoformat()} for version in deadlines],
        "tasks": [{"title": task.title, "due_at": task.due_at.isoformat() if task.due_at else None, "completion_percent": task.completion_percent} for task in tasks],
        "recent_channel_messages": [{"channel": row.channel, "body": row.body[:1000]} for row in reversed(messages)],
    }

def unavailable():
    return HTTPException(status_code=503, detail="Group AI chatbot is unavailable. Check the configured local runtime and model.")

def generate(question, context=None):
    url = settings.ollama_url.strip().rstrip("/")
    # Group collaboration uses the configured agent model. The old
    # ``ollama_model`` attribute no longer exists on Settings and caused every
    # live chatbot request to fail before reaching Ollama.
    model = str(getattr(settings, "ollama_agent_model", getattr(settings, "ollama_model", ""))).strip()
    try:
        parts = urlsplit(url)
        if not model or parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost", "::1") or parts.username or parts.password or parts.query or parts.fragment:
            raise unavailable()
        system = "You are an advisory group assistant. Your output is AI-generated advice, not an academic decision."
        if context:
            system += " You are strictly scoped to this group context and must not reveal other group data:\n" + json.dumps(context, sort_keys=True)
        payload = json.dumps({"model": model, "stream": False, "messages": [{"role": "system", "content": system}, {"role": "user", "content": question}]}).encode("utf-8")
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
    team = require_team(session, actor, team_id)
    context = scoped_context(session, team)
    answer = generate(payload.body, context)
    try:
        user_message = GroupMessage(team_id=team_id, channel="group_ai", author_id=actor.id, author_kind="TEAM", body=payload.body)
        ai_message = GroupMessage(team_id=team_id, channel="group_ai", author_id=actor.id, author_kind="AI", body=answer)
        session.add_all([user_message, ai_message]); session.flush(); session.commit()
        session.refresh(user_message); session.refresh(ai_message)
        return {"question": output(user_message), "answer": output(ai_message)}
    except Exception:
        session.rollback()
        raise HTTPException(status_code=500, detail="Group AI conversation could not be saved.") from None
