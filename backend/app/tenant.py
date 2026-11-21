"""Tenant resolution, request scoping, and account activation rules."""

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from secrets import token_urlsafe
import smtplib

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    EmailVerificationToken,
    Institution,
    InstitutionDomain,
    InstitutionInvitation,
    InstitutionMembership,
    User,
    UserRole,
)
from .config import settings
from .security import hash_session_token


PRIMARY_INSTITUTION_DOMAIN = "szabist-isb.pk"


def email_domain(email: str) -> str:
    normalized = email.strip().lower()
    return normalized.rsplit("@", 1)[1]


def is_primary_email(email: str) -> bool:
    normalized = email.strip().lower()
    return normalized.count("@") == 1 and email_domain(normalized) == PRIMARY_INSTITUTION_DOMAIN


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_platform_admin(user: User) -> bool:
    """Platform-wide access is explicit and separate from university ADMIN."""

    return user.role == UserRole.PLATFORM_ADMIN


def primary_institution_id(session: Session) -> int | None:
    """Return the institution configured for this single-university deployment."""

    return session.scalar(
        select(InstitutionDomain.institution_id).where(
            InstitutionDomain.domain == PRIMARY_INSTITUTION_DOMAIN,
        )
    )


def set_tenant_context(session: Session, user: User, request: Request | None = None) -> None:
    """Bind the authenticated request to one tenant or to platform scope."""

    session.info.pop("institution_id", None)
    session.info["platform_admin"] = is_platform_admin(user)
    if is_platform_admin(user):
        requested = request.headers.get("x-institution-id") if request is not None else None
        if requested:
            try:
                requested_id = int(requested)
                if requested_id != primary_institution_id(session):
                    raise HTTPException(status.HTTP_403_FORBIDDEN, "Only SZABIST is configured for this portal.")
                session.info["institution_id"] = requested_id
                session.info["platform_admin"] = False
            except ValueError as error:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "X-Institution-ID must be an integer.") from error
        return
    if user.institution_id is not None:
        session.info["institution_id"] = user.institution_id


def membership_for(session: Session, user_id: int, institution_id: int) -> InstitutionMembership | None:
    return session.scalar(
        select(InstitutionMembership).where(
            InstitutionMembership.user_id == user_id,
            InstitutionMembership.institution_id == institution_id,
        )
    )


def ensure_access_ready(session: Session, user: User) -> None:
    """Reject accounts that have not completed email and institution approval."""

    if is_platform_admin(user):
        return
    if user.institution_id is None or not is_primary_email(user.email):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only SZABIST accounts can access this portal.")
    institution = session.get(Institution, user.institution_id)
    membership = membership_for(session, user.id, user.institution_id)
    if (
        institution is None
        or institution.status != "ACTIVE"
        or user.email_verified_at is None
        or user.access_approved_at is None
        or membership is None
        or membership.status != "ACTIVE"
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Email verification and institutional approval are required.")


def resolve_registration_institution(
    session: Session,
    emails: list[str],
    invitation_token: str | None = None,
) -> tuple[Institution, InstitutionInvitation | None]:
    """Resolve all supplied emails to one active verified institution domain."""

    normalized_emails = [email.strip().lower() for email in emails if email and "@" in email]
    if not normalized_emails or any(not is_primary_email(email) for email in normalized_emails):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Only @szabist-isb.pk university emails are accepted.")
    domains = {email_domain(email) for email in normalized_emails}
    domain_rows = []
    for domain in domains:
        row = session.scalar(select(InstitutionDomain).where(InstitutionDomain.domain == domain))
        if row is not None:
            domain_rows.append(row)
    active_rows = [row for row in domain_rows if row.is_verified and row.is_active]
    if any(row.institution_id != active_rows[0].institution_id for row in active_rows[1:]):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The SZABIST email domain is mapped inconsistently.")
    invitation = None
    if invitation_token:
        invitation = session.scalar(
            select(InstitutionInvitation).where(
                InstitutionInvitation.token_hash == hash_session_token(invitation_token),
                InstitutionInvitation.status == "PENDING",
                InstitutionInvitation.expires_at > utc_now(),
            )
        )
        if invitation is not None and invitation.email is not None and invitation.email not in normalized_emails:
            invitation = None
        if invitation is not None and active_rows and any(row.institution_id != invitation.institution_id for row in active_rows):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The invitation does not match SZABIST.")
    if len(active_rows) != len(domains):
        if invitation is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The SZABIST email domain is not registered with an active institution.")
        institution = session.get(Institution, invitation.institution_id)
        if institution is None or institution.status != "ACTIVE":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "The institution is disabled.")
        if active_rows and active_rows[0].institution_id != institution.id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The invitation does not match SZABIST.")
        return institution, invitation
    if not active_rows:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A verified @szabist-isb.pk email domain is required.")
    institution = session.get(Institution, active_rows[0].institution_id)
    if institution is None or institution.status != "ACTIVE":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The institution is disabled.")
    return institution, invitation


def issue_email_verification_token(session: Session, user: User, institution_id: int) -> str:
    raw_token = token_urlsafe(32)
    session.add(
        EmailVerificationToken(
            institution_id=institution_id,
            user_id=user.id,
            token_hash=hash_session_token(raw_token),
            expires_at=utc_now() + timedelta(hours=72),
        )
    )
    return raw_token


def send_email_verification(address: str, raw_token: str) -> bool:
    """Send a verification link when SMTP is configured; never expose it in production."""

    if not settings.smtp_host or not settings.smtp_from_email or bool(settings.smtp_username) != bool(settings.smtp_password):
        return False
    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = address
    message["Subject"] = "Verify your FYPHub email"
    message.set_content(
        "Verify your FYPHub email before accessing the portal:\n\n"
        f"{settings.email_verification_base_url}?token={raw_token}\n\n"
        "If you did not create this account, you can ignore this message."
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        return True
    except Exception:
        return False


def approve_membership(session: Session, membership: InstitutionMembership, actor_id: int) -> None:
    membership.approved_by_id = actor_id
    membership.approved_at = utc_now()
    membership.status = "ACTIVE"
    user = session.get(User, membership.user_id)
    if user is not None:
        user.institution_id = membership.institution_id
        user.access_approved_at = membership.approved_at
        if user.email_verified_at is not None:
            user.is_active = True

