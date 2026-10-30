"""Secure, enumeration-resistant password recovery endpoints."""

from __future__ import annotations

import secrets
import smtplib
from collections import defaultdict
from datetime import datetime, timedelta
from email.message import EmailMessage
from threading import Lock

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .auth import utc_now, validate_mutating_origin
from .config import settings
from .database import get_db
from .models import AdminAuditEvent, AuthSession, PasswordResetToken, User
from .schemas.password_reset import ForgotPasswordRequest, PasswordResetMessage, ResetPasswordRequest
from .security import generate_session_token, hash_password, hash_session_token

router = APIRouter(prefix="/api/v1/auth")

PASSWORD_RESET_GENERIC_MESSAGE = "If an account exists, a password reset link will be sent."
PASSWORD_RESET_DEVELOPMENT_UNKNOWN_MESSAGE = "No account was found with this email address."
PASSWORD_RESET_SUCCESS_MESSAGE = "Password reset successful. Please log in again."
PASSWORD_RESET_TOKEN_MINUTES = 15
MAX_REQUESTS_PER_HOUR = 5
_development_links: dict[str, tuple[str, datetime]] = {}
_rate_lock = Lock()
_requests_by_ip: defaultdict[str, list[datetime]] = defaultdict(list)


def _smtp_from() -> str:
    return getattr(settings, "smtp_from_email", "") or getattr(settings, "smtp_from", "")


def _smtp_configured() -> bool:
    username = getattr(settings, "smtp_username", "")
    password = getattr(settings, "smtp_password", "")
    return bool(getattr(settings, "smtp_host", "")) and bool(_smtp_from()) and bool(username) == bool(password)


def _development_mode() -> bool:
    return getattr(settings, "app_env", "production").lower() in {"dev", "development", "local"}


def _development_or_demo_mode() -> bool:
    return _development_mode() or getattr(settings, "registration_mode", "restricted").lower() == "demo"


def _is_valid_email(value: str) -> bool:
    try:
        validate_email(value, check_deliverability=False)
    except EmailNotValidError:
        return False
    return True


def _rate_limit_allows(ip: str) -> bool:
    now = utc_now()
    cutoff = now - timedelta(hours=1)
    with _rate_lock:
        entries = [value for value in _requests_by_ip[ip] if value > cutoff]
        if len(entries) >= MAX_REQUESTS_PER_HOUR:
            _requests_by_ip[ip] = entries
            return False
        entries.append(now)
        _requests_by_ip[ip] = entries
        return True


def _send_reset_email(address: str, link: str) -> bool:
    if not _smtp_configured():
        return False
    message = EmailMessage()
    message["From"] = _smtp_from()
    message["To"] = address
    message["Subject"] = "FYPHub password reset"
    message.set_content(
        "A password reset was requested for your FYPHub account. "
        f"Open this link within {PASSWORD_RESET_TOKEN_MINUTES} minutes:\n\n{link}\n\n"
        "If you did not request this, you can ignore this message."
    )
    try:
        with smtplib.SMTP(getattr(settings, "smtp_host", ""), getattr(settings, "smtp_port", 587), timeout=10) as smtp:
            smtp.starttls()
            username = getattr(settings, "smtp_username", "")
            if username:
                smtp.login(username, getattr(settings, "smtp_password", ""))
            smtp.send_message(message)
        return True
    except Exception:
        return False


def _audit(session: Session, user_id: int, action: str, changed_values: dict[str, object]) -> None:
    session.add(
        AdminAuditEvent(
            actor_id=user_id,
            affected_user_id=user_id,
            target_type="PASSWORD_RESET",
            target_id=user_id,
            action=action,
            changed_values=changed_values,
        )
    )


def _generic_response() -> dict[str, str]:
    return {"message": PASSWORD_RESET_GENERIC_MESSAGE}


@router.post("/forgot-password", response_model=PasswordResetMessage)
def forgot_password(payload: ForgotPasswordRequest, request: Request, session: Session = Depends(get_db)) -> dict[str, str]:
    """Create a reset token without revealing whether an account exists."""
    validate_mutating_origin(request)
    client_ip = request.client.host if request.client else "unknown"
    kind, value = payload.normalized_identifier()
    if not _rate_limit_allows(client_ip):
        return _generic_response()

    if kind == "email":
        user = session.execute(select(User).where(User.email == value, User.is_active.is_(True)).with_for_update()).scalar_one_or_none()
    else:
        user = session.execute(select(User).where(User.registration_number == value, User.is_active.is_(True)).with_for_update()).scalar_one_or_none()
    if user is None:
        session.rollback()
        if kind == "email" and _development_or_demo_mode() and not _smtp_configured() and _is_valid_email(value):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "account_not_found", "message": PASSWORD_RESET_DEVELOPMENT_UNKNOWN_MESSAGE},
            )
        return _generic_response()

    now = utc_now()
    session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    raw_token = generate_session_token()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_session_token(raw_token),
            expires_at=now + timedelta(minutes=PASSWORD_RESET_TOKEN_MINUTES),
            requested_ip=client_ip[:64],
        )
    )
    _audit(session, user.id, "password_reset_requested", {"identifier_type": kind, "delivery": "smtp" if _smtp_configured() else "development"})
    session.commit()

    base_url = getattr(settings, "password_reset_base_url", "http://localhost:5173/reset-password").rstrip("/")
    link = f"{base_url}?token={raw_token}"
    if _smtp_configured():
        _send_reset_email(user.email, link)
    elif _development_mode() and client_ip in {"127.0.0.1", "::1", "localhost"}:
        # The link is retrievable only through the explicit local-development endpoint below.
        _development_links[value] = (link, now + timedelta(minutes=PASSWORD_RESET_TOKEN_MINUTES))
    return _generic_response()


@router.get("/password-reset-status")
def password_reset_status() -> dict[str, bool]:
    """Expose only the non-sensitive delivery mode needed by the local recovery UI."""
    return {
        "development_mode": _development_mode(),
        "smtp_configured": _smtp_configured(),
    }


@router.get("/dev/password-reset-link")
def development_password_reset_link(identifier: str, request: Request) -> dict[str, str]:
    """Return a local reset link only when the backend is explicitly in development mode."""
    if not _development_mode() or (request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    entry = _development_links.get(identifier.strip().lower()) or _development_links.get(identifier.strip().upper())
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reset link not found.")
    link, expires_at = entry
    if expires_at <= utc_now():
        _development_links.pop(identifier.strip().lower(), None)
        _development_links.pop(identifier.strip().upper(), None)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reset link not found.")
    return {"reset_link": link}


@router.post("/reset-password", response_model=PasswordResetMessage)
def reset_password(payload: ResetPasswordRequest, request: Request, session: Session = Depends(get_db)) -> dict[str, str]:
    """Consume a valid reset token and revoke every existing browser session."""
    validate_mutating_origin(request)
    now = utc_now()
    token_hash = hash_session_token(payload.token)
    row = session.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash).with_for_update()).scalar_one_or_none()
    if row is None or not secrets.compare_digest(row.token_hash, token_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "invalid_reset_token", "message": "This password reset link is invalid."})
    if row.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "used_reset_token", "message": "This password reset link has already been used."})
    if row.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "expired_reset_token", "message": "This password reset link has expired."})
    user = session.execute(select(User).where(User.id == row.user_id).with_for_update()).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "invalid_reset_token", "message": "This password reset link is invalid."})

    user.password_hash = hash_password(payload.password)
    row.used_at = now
    revoked = session.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).values(revoked_at=now)).rowcount or 0
    _audit(session, user.id, "password_reset_completed", {"sessions_revoked": revoked})
    session.commit()
    return {"message": PASSWORD_RESET_SUCCESS_MESSAGE}
