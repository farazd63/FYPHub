"""Reusable cookie-session authentication dependencies and helpers."""

from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .config import settings
from .models import AuthSession, User, UserRole
from .security import hash_session_token

SESSION_COOKIE_NAME = "fyphub_session"
# Deliberately fixed for this checkpoint; changing it is a reviewed configuration change.
SESSION_LIFETIME_HOURS = settings.session_lifetime_hours
ALLOWED_BROWSER_ORIGIN = "http://127.0.0.1:5174"
ALLOWED_BROWSER_ORIGINS = (ALLOWED_BROWSER_ORIGIN, "http://localhost:5173")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def authentication_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")


def validate_mutating_origin(request: Request) -> None:
    """Allow same-origin/non-browser calls, but reject a supplied foreign browser Origin."""
    origin = request.headers.get("origin")
    if origin is not None and origin not in ALLOWED_BROWSER_ORIGINS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin is not allowed.")


def session_cookie_secure(request: Request) -> bool:
    """Mark session cookies Secure exactly when the request is served over HTTPS."""
    return request.url.scheme.lower() == "https"


def set_session_cookie(request: Request, response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_LIFETIME_HOURS * 60 * 60,
        httponly=True,
        secure=session_cookie_secure(request),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(request: Request, response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=session_cookie_secure(request),
        samesite="lax",
        path="/",
    )


def get_current_user(request: Request, session: Session = Depends(get_db)) -> User:
    """Resolve an active user through a current, non-revoked hashed cookie session."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise authentication_error()
    now = utc_now()
    record = session.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.token_hash == hash_session_token(token))
    ).one_or_none()
    if record is None:
        raise authentication_error()
    auth_session, user = record
    if auth_session.revoked_at is not None or auth_session.expires_at <= now or not user.is_active:
        raise authentication_error()
    return user


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """Create a dependency that permits only the listed roles after authentication."""
    def role_guard(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")
        return current_user

    return role_guard
