"""Student-only general chatbot backed directly by the local Llama model."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request as UrlRequest, build_opener

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user, validate_mutating_origin
from .config import settings
from .database import SessionLocal, get_db
from .group_channels import MessageWrite
from .models import StudentAIMessage, User, UserRole

router = APIRouter(prefix="/api/v1/group-ai", tags=["student-ai"])

CHAT_MODEL = "llama3.1:8b"
MAX_HISTORY_MESSAGES = 12
MAX_GENERATION_TOKENS = 256
CHAT_TIMEOUT_SECONDS = 180
MODEL_KEEP_ALIVE = "24h"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="Llama 3.1 8B is unavailable. Check the local Ollama service.")


def _require_student(actor: User) -> None:
    if actor.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="The AI chatbot is available in the student portal only.")


def _message_out(message: StudentAIMessage) -> dict:
    return {
        "id": message.id,
        "author_kind": message.author_kind,
        "body": message.body,
        "created_at": message.created_at,
    }


def _recent_rows(session: Session, actor: User) -> list[StudentAIMessage]:
    rows = session.scalars(
        select(StudentAIMessage)
        .where(StudentAIMessage.user_id == actor.id)
        .order_by(StudentAIMessage.id.desc())
        .limit(MAX_HISTORY_MESSAGES)
    ).all()
    return list(reversed(rows))


def _model_messages(rows: list[StudentAIMessage], question: str) -> list[dict[str, str]]:
    messages = [
        {
            "role": "assistant" if row.author_kind == "AI" else "user",
            "content": row.body,
        }
        for row in rows
        if row.body.strip()
    ]
    messages.append({"role": "user", "content": question})
    return messages


def _request(question: str, recent_messages: list[StudentAIMessage] | None = None) -> UrlRequest:
    """Build the direct Llama request without adding application context."""

    url = settings.ollama_url.strip().rstrip("/")
    parts = urlsplit(url)
    allowed_hosts = getattr(settings, "ollama_allowed_hosts", ("127.0.0.1", "localhost", "::1", "ollama"))
    hostname = (parts.hostname or "").lower()
    if (
        parts.scheme != "http"
        or hostname not in allowed_hosts
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise unavailable()

    payload = json.dumps(
        {
            "model": CHAT_MODEL,
            "stream": True,
            "keep_alive": MODEL_KEEP_ALIVE,
            "options": {"num_predict": MAX_GENERATION_TOKENS},
            "messages": _model_messages(recent_messages or [], question),
        }
    ).encode("utf-8")
    return UrlRequest(
        url + "/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )


def generate(question: str, recent_messages: list[StudentAIMessage] | None = None) -> str:
    """Send only the question and optional chatbot history to Llama 3.1 8B."""

    request = _request(question, recent_messages)
    try:
        with build_opener(NoRedirect()).open(request, timeout=CHAT_TIMEOUT_SECONDS) as response:
            content = ""
            for line in response:
                if not line.strip():
                    continue
                data = json.loads(line)
                content += str(data.get("message", {}).get("content", ""))
                if data.get("done"):
                    break
                if len(content) > 16000:
                    raise ValueError("response too large")
        if not content.strip():
            raise ValueError("invalid response")
        return content.strip()
    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError, UnicodeError, URLError, HTTPError, TimeoutError, OSError):
        raise unavailable() from None


@router.get("")
def history(actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    _require_student(actor)
    return [_message_out(row) for row in _recent_rows(session, actor)]


@router.post("", status_code=200)
def chat(
    payload: MessageWrite,
    request: Request,
    actor: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    _require_student(actor)
    validate_mutating_origin(request)
    recent = _recent_rows(session, actor)
    def events():
        question = StudentAIMessage(user_id=actor.id, author_kind="USER", body=payload.body)
        answer_parts: list[str] = []
        try:
            request_to_ollama = _request(payload.body, recent)
            with build_opener(NoRedirect()).open(request_to_ollama, timeout=CHAT_TIMEOUT_SECONDS) as ollama_response:
                for line in ollama_response:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    token = str(data.get("message", {}).get("content", ""))
                    if token:
                        answer_parts.append(token)
                        yield f"data: {json.dumps({'type': 'token', 'token': token}, ensure_ascii=False)}\n\n"
                    if data.get("done"):
                        break
                    if sum(len(part) for part in answer_parts) > 16000:
                        raise ValueError("response too large")
            answer_text = "".join(answer_parts).strip()
            if not answer_text:
                raise ValueError("invalid response")
            response = StudentAIMessage(user_id=actor.id, author_kind="AI", body=answer_text)
            persistence_session = SessionLocal()
            try:
                persistence_session.add_all([question, response])
                persistence_session.commit()
                persistence_session.refresh(question)
                persistence_session.refresh(response)
            except Exception:
                persistence_session.rollback()
                raise
            finally:
                persistence_session.close()
            yield f"data: {json.dumps({'type': 'done', 'model': CHAT_MODEL, 'question': _message_out(question), 'answer': _message_out(response)}, ensure_ascii=False, default=str)}\n\n"
        except HTTPException as error:
            yield f"data: {json.dumps({'type': 'error', 'message': error.detail}, ensure_ascii=False, default=str)}\n\n"
        except (ValueError, KeyError, TypeError, UnicodeError, URLError, HTTPError, TimeoutError, OSError) as error:
            detail = "Llama 3.1 8B is unavailable. Check the local Ollama service."
            if isinstance(error, HTTPException):
                detail = str(error.detail)
            yield f"data: {json.dumps({'type': 'error', 'message': detail}, ensure_ascii=False)}\n\n"
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'message': 'The chatbot response could not be saved.'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
