"""Reusable cookie-session authentication dependencies and helpers."""

from collections.abc import Callable
from datetime import datetime, timezone
import logging
import os

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .config import settings
from .models import AuthSession, Team, User, UserRole
from .security import hash_session_token
from .tenant import ensure_access_ready, set_tenant_context

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "fyphub_session"
# Deliberately fixed for this checkpoint; changing it is a reviewed configuration change.
SESSION_LIFETIME_HOURS = settings.session_lifetime_hours
ALLOWED_BROWSER_ORIGIN = "http://127.0.0.1:5173"
# Explicit local Vite origins. Credentials remain restricted; no wildcard is
# permitted because the application uses cookie-backed sessions.
_BASE_ALLOWED_BROWSER_ORIGINS = (
    ALLOWED_BROWSER_ORIGIN,
    "http://localhost:5173",
    "http://127.0.0.1:5174",
    "http://localhost:5174",
)
ALLOWED_BROWSER_ORIGINS = (
    *_BASE_ALLOWED_BROWSER_ORIGINS,
    *tuple(
        origin.strip().rstrip("/")
        for origin in os.getenv("FYPHUB_LAN_ORIGINS", "").split(",")
        if origin.strip()
    ),
)
_TEMPORARY_DIAGNOSTIC_PATHS = {"/api/v1/auth/login", "/api/v1/auth/me", "/api/v1/admin/me"}


def log_temporary_auth_diagnostic(request: Request, event: str, **metadata: object) -> None:
    """TEMPORARY: emit safe metadata while diagnosing post-login access failures."""
    if request.url.path not in _TEMPORARY_DIAGNOSTIC_PATHS:
        return
    safe_metadata = {
        "path": request.url.path,
        "origin": request.headers.get("origin"),
        "host": request.headers.get("host"),
        "cookie_name": SESSION_COOKIE_NAME,
        "request_id": getattr(request.state, "request_id", None),
        **metadata,
    }
    logger.warning("TEMP_AUTH_DIAGNOSTIC %s %s", event, safe_metadata)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def authentication_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")


def validate_mutating_origin(request: Request) -> None:
    """Allow same-origin/non-browser calls, but reject a supplied foreign browser Origin.

    The portal is commonly opened from another device over the local network
    (for example, ``http://10.34.118.50:5173`` on a phone).  A fixed localhost
    allow-list cannot recognize that request even though it is same-origin.
    Prefer the origin reconstructed from the trusted reverse-proxy headers and
    keep the explicit development origins as a fallback for direct API calls.
    """
    origin = request.headers.get("origin")
    if origin is None:
        return

    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    scheme = forwarded_proto or request.url.scheme
    forwarded_host = request.headers.get("x-forwarded-host", "").split(",", 1)[0].strip()
    host = forwarded_host or request.headers.get("host", "").strip()
    same_origin = bool(host) and origin.rstrip("/") == f"{scheme}://{host}".rstrip("/")

    if origin not in ALLOWED_BROWSER_ORIGINS and not same_origin:
        log_temporary_auth_diagnostic(
            request,
            "origin_rejected",
            response_status=status.HTTP_403_FORBIDDEN,
            reason="Origin rejection",
        )
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
        log_temporary_auth_diagnostic(
            request,
            "session_rejected",
            session_cookie_present=False,
            session_lookup_success=False,
            session_lookup="not found",
            response_status=status.HTTP_401_UNAUTHORIZED,
            reason="missing cookie",
        )
        raise authentication_error()
    now = utc_now()
    record = session.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.token_hash == hash_session_token(token))
    ).one_or_none()
    if record is None:
        log_temporary_auth_diagnostic(
            request,
            "session_rejected",
            session_cookie_present=True,
            session_lookup_success=False,
            session_lookup="not found",
            response_status=status.HTTP_401_UNAUTHORIZED,
            reason="invalid session",
        )
        raise authentication_error()
    auth_session, user = record
    common_metadata = {
        "session_cookie_present": True,
        "session_lookup_success": True,
        "session_lookup": "found",
        "user_id": user.id,
        "user_active": user.is_active,
        "persisted_role": user.role.value,
    }
    if auth_session.revoked_at is not None:
        log_temporary_auth_diagnostic(
            request,
            "session_rejected",
            **common_metadata,
            response_status=status.HTTP_401_UNAUTHORIZED,
            reason="invalid session",
        )
        raise authentication_error()
    if auth_session.expires_at <= now:
        log_temporary_auth_diagnostic(
            request,
            "session_rejected",
            **common_metadata,
            response_status=status.HTTP_401_UNAUTHORIZED,
            reason="expired session",
        )
        raise authentication_error()
    if not user.is_active:
        log_temporary_auth_diagnostic(
            request,
            "session_rejected",
            **common_metadata,
            response_status=status.HTTP_401_UNAUTHORIZED,
            reason="inactive user",
        )
        raise authentication_error()
    set_tenant_context(session, user, request)
    try:
        ensure_access_ready(session, user)
    except HTTPException:
        log_temporary_auth_diagnostic(
            request,
            "session_rejected",
            **common_metadata,
            response_status=status.HTTP_403_FORBIDDEN,
            reason="email verification or institutional approval is incomplete",
        )
        raise
    if user.role == UserRole.STUDENT and session.scalar(
        select(Team.id).where(Team.shared_user_id == user.id, Team.status != "dissolved").limit(1)
    ) is None:
        log_temporary_auth_diagnostic(
            request,
            "session_rejected",
            **common_metadata,
            response_status=status.HTTP_401_UNAUTHORIZED,
            reason="student account is not linked to a group",
        )
        raise authentication_error()
    log_temporary_auth_diagnostic(request, "session_accepted", **common_metadata)
    return user


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """Create a dependency that permits only the listed roles after authentication."""
    def role_guard(current_user: User = Depends(get_current_user), request: Request = None) -> User:
        role_allowed = current_user.role in roles or (
            UserRole.ADMIN in roles and current_user.role == UserRole.PLATFORM_ADMIN
        )
        if not role_allowed:
            if request is not None:
                log_temporary_auth_diagnostic(
                    request,
                    "role_rejected",
                    user_id=current_user.id,
                    user_active=current_user.is_active,
                    persisted_role=current_user.role.value,
                    role_comparison="mismatch",
                    response_status=status.HTTP_403_FORBIDDEN,
                    reason="role mismatch",
                )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")
        if request is not None:
            log_temporary_auth_diagnostic(
                request,
                "role_accepted",
                user_id=current_user.id,
                user_active=current_user.is_active,
                persisted_role=current_user.role.value,
                role_comparison="matched",
            )
        return current_user

    return role_guard
