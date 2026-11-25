"""Student-only general chatbot backed directly by the local Llama model."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request as UrlRequest, build_opener

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .auth import get_current_user, validate_mutating_origin
from .config import settings
from .database import SessionLocal, get_db
from .group_channels import MessageWrite
from .models import StudentAIConversation, StudentAIMessage, User, UserRole

router = APIRouter(prefix="/api/v1/group-ai", tags=["student-ai"])

CHAT_MODEL = "llama3.1:8b"
MAX_HISTORY_MESSAGES = 24
MAX_HISTORY_CHARACTERS = 16000
MODEL_CONTEXT_TOKENS = 8192
MAX_GENERATION_TOKENS = 256
CHAT_TEMPERATURE = 0.2
CHAT_TIMEOUT_SECONDS = 180
MODEL_KEEP_ALIVE = "24h"
CHAT_SYSTEM_PROMPT = (
    "You are FYPHub's student assistant in an ongoing conversation. "
    "The earlier user and assistant messages are a saved, authoritative transcript of this same chat. "
    "Use that transcript whenever the user refers to something discussed earlier or asks for a summary. "
    "Treat the student's messages as the primary source of facts. Treat earlier assistant messages as tentative "
    "and, when they conflict, describe the inconsistency instead of repeating an unsupported assistant claim as fact. "
    "An earlier assistant message may be wrong; never treat an assistant claim that history is empty as proof "
    "that the transcript is empty. If earlier messages are present, do not say that the conversation just started "
    "or that you have no record of previous messages. If the transcript does not contain the requested information, "
    "say so clearly instead of inventing details."
)


class ConversationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)


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


def _conversation_out(conversation: StudentAIConversation, message_count: int | None = None) -> dict:
    result = {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
    }
    if message_count is not None:
        result["message_count"] = message_count
    return result


def _conversation_for_actor(session: Session, actor: User, conversation_id: int) -> StudentAIConversation:
    conversation = session.scalar(
        select(StudentAIConversation).where(
            StudentAIConversation.id == conversation_id,
            StudentAIConversation.user_id == actor.id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return conversation


def _latest_conversation(session: Session, actor: User) -> StudentAIConversation | None:
    return session.scalar(
        select(StudentAIConversation)
        .where(StudentAIConversation.user_id == actor.id)
        .order_by(StudentAIConversation.updated_at.desc(), StudentAIConversation.id.desc())
        .limit(1)
    )


def _conversation_messages(session: Session, conversation_id: int) -> list[StudentAIMessage]:
    return list(
        session.scalars(
            select(StudentAIMessage)
            .where(StudentAIMessage.conversation_id == conversation_id)
            .order_by(StudentAIMessage.id.asc())
        ).all()
    )


def _recent_rows(session: Session, conversation_id: int) -> list[StudentAIMessage]:
    rows = session.scalars(
        select(StudentAIMessage)
        .where(StudentAIMessage.conversation_id == conversation_id)
        .order_by(StudentAIMessage.id.desc())
        .limit(MAX_HISTORY_MESSAGES)
    ).all()
    selected: list[StudentAIMessage] = []
    characters = 0
    for row in rows:
        row_characters = len(row.body)
        if selected and characters + row_characters > MAX_HISTORY_CHARACTERS:
            break
        selected.append(row)
        characters += row_characters
    return list(reversed(selected))


def _model_messages(rows: list[StudentAIMessage], question: str) -> list[dict[str, str]]:
    messages = [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
        *[
        {
            "role": "assistant" if row.author_kind == "AI" else "user",
            "content": row.body,
        }
        for row in rows
        if row.body.strip()
        ],
    ]
    messages.append(
        {
            "role": "user",
            "content": (
                f"There are {len(rows)} saved messages above in this same conversation. "
                "Use them as context and answer this current student request now. "
                "If the request asks for a summary, summarize those saved messages.\n\n"
                f"Current student request:\n{question}"
            ),
        }
    )
    return messages


def _title_from_question(question: str) -> str:
    title = " ".join(question.split()).strip()
    if len(title) > 64:
        return f"{title[:61].rstrip()}..."
    return title or "New chat"


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
            "options": {
                "num_ctx": MODEL_CONTEXT_TOKENS,
                "num_predict": MAX_GENERATION_TOKENS,
                "temperature": CHAT_TEMPERATURE,
            },
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


def _create_conversation(session: Session, actor: User, title: str | None = None) -> StudentAIConversation:
    conversation = StudentAIConversation(user_id=actor.id, title=(title or "New chat").strip() or "New chat")
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def _stream_chat(payload: MessageWrite, actor: User, conversation: StudentAIConversation, recent: list[StudentAIMessage]):
    def events():
        question = StudentAIMessage(
            user_id=actor.id,
            conversation_id=conversation.id,
            author_kind="USER",
            body=payload.body,
        )
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
            response = StudentAIMessage(
                user_id=actor.id,
                conversation_id=conversation.id,
                author_kind="AI",
                body=answer_text,
            )
            persistence_session = SessionLocal()
            try:
                persisted_conversation = _conversation_for_actor(persistence_session, actor, conversation.id)
                if persisted_conversation.title == "New chat":
                    persisted_conversation.title = _title_from_question(payload.body)
                persisted_conversation.updated_at = datetime.now(timezone.utc)
                persistence_session.add_all([question, response])
                persistence_session.commit()
                persistence_session.refresh(question)
                persistence_session.refresh(response)
                persistence_session.refresh(persisted_conversation)
                message_count = persistence_session.scalar(
                    select(func.count(StudentAIMessage.id)).where(
                        StudentAIMessage.conversation_id == persisted_conversation.id
                    )
                )
                conversation_out = _conversation_out(persisted_conversation, int(message_count or 0))
            except Exception:
                persistence_session.rollback()
                raise
            finally:
                persistence_session.close()
            yield f"data: {json.dumps({'type': 'done', 'model': CHAT_MODEL, 'question': _message_out(question), 'answer': _message_out(response), 'conversation': conversation_out}, ensure_ascii=False, default=str)}\n\n"
        except HTTPException as error:
            yield f"data: {json.dumps({'type': 'error', 'message': error.detail}, ensure_ascii=False, default=str)}\n\n"
        except (ValueError, KeyError, TypeError, UnicodeError, URLError, HTTPError, TimeoutError, OSError):
            yield f"data: {json.dumps({'type': 'error', 'message': 'Llama 3.1 8B is unavailable. Check the local Ollama service.'}, ensure_ascii=False)}\n\n"
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'message': 'The chatbot response could not be saved.'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations")
def conversations(actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    _require_student(actor)
    rows = session.scalars(
        select(StudentAIConversation)
        .where(StudentAIConversation.user_id == actor.id)
        .order_by(StudentAIConversation.updated_at.desc(), StudentAIConversation.id.desc())
    ).all()
    result = []
    for conversation in rows:
        count = session.scalar(
            select(func.count(StudentAIMessage.id)).where(StudentAIMessage.conversation_id == conversation.id)
        )
        result.append(_conversation_out(conversation, int(count or 0)))
    return result


@router.post("/conversations", status_code=201)
def create_conversation(
    payload: ConversationWrite,
    request: Request,
    actor: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    _require_student(actor)
    validate_mutating_origin(request)
    return _conversation_out(_create_conversation(session, actor, payload.title))


@router.get("/conversations/{conversation_id}")
def conversation_detail(
    conversation_id: int,
    actor: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    _require_student(actor)
    conversation = _conversation_for_actor(session, actor, conversation_id)
    return {
        "conversation": _conversation_out(conversation),
        "messages": [_message_out(row) for row in _conversation_messages(session, conversation.id)],
    }


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int,
    request: Request,
    actor: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    _require_student(actor)
    validate_mutating_origin(request)
    conversation = _conversation_for_actor(session, actor, conversation_id)
    session.execute(delete(StudentAIMessage).where(StudentAIMessage.conversation_id == conversation.id))
    session.delete(conversation)
    session.commit()


@router.post("/conversations/{conversation_id}/messages", status_code=200)
def conversation_chat(
    conversation_id: int,
    payload: MessageWrite,
    request: Request,
    actor: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    _require_student(actor)
    validate_mutating_origin(request)
    conversation = _conversation_for_actor(session, actor, conversation_id)
    return _stream_chat(payload, actor, conversation, _recent_rows(session, conversation.id))


@router.get("")
def history(actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    _require_student(actor)
    conversation = _latest_conversation(session, actor)
    if conversation is None:
        return []
    return [_message_out(row) for row in _conversation_messages(session, conversation.id)]


@router.post("", status_code=200)
def chat(
    payload: MessageWrite,
    request: Request,
    actor: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    _require_student(actor)
    validate_mutating_origin(request)
    conversation = _latest_conversation(session, actor) or _create_conversation(session, actor)
    return _stream_chat(payload, actor, conversation, _recent_rows(session, conversation.id))
