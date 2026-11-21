"""Platform and institution administration APIs."""

from datetime import timedelta
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles, utc_now, validate_mutating_origin
from .database import get_db
from .models import (
    EmailVerificationToken,
    Institution,
    InstitutionDomain,
    InstitutionInvitation,
    InstitutionMembership,
    User,
    UserRole,
)
from .schemas.institutions import (
    InstitutionCreate,
    InstitutionDomainCreate,
    InstitutionDomainOut,
    InstitutionDomainUpdate,
    InstitutionInvitationCreate,
    InstitutionInvitationOut,
    InstitutionMembershipOut,
    InstitutionOut,
    InstitutionUpdate,
    VerifyEmailRequest,
)
from .security import hash_session_token
from .tenant import PRIMARY_INSTITUTION_DOMAIN, approve_membership, is_platform_admin, primary_institution_id


router = APIRouter(tags=["institutions"])


def _platform_actor(actor: User = Depends(get_current_user)) -> User:
    if not is_platform_admin(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform administrator access is required.")
    return actor


def _institution_manager(institution_id: int, actor: User) -> None:
    if is_platform_admin(actor):
        return
    if actor.role != UserRole.ADMIN or actor.institution_id != institution_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only manage your own institution.")


def _institution(session: Session, institution_id: int) -> Institution:
    if primary_institution_id(session) != institution_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Institution not found.")
    row = session.get(Institution, institution_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Institution not found.")
    return row


@router.get("/api/v1/platform/institutions", response_model=list[InstitutionOut])
def list_institutions(_: User = Depends(_platform_actor), session: Session = Depends(get_db)):
    primary_id = primary_institution_id(session)
    return session.scalars(select(Institution).where(Institution.id == primary_id).order_by(Institution.name, Institution.id)).all()


@router.post("/api/v1/platform/institutions", response_model=InstitutionOut, status_code=status.HTTP_201_CREATED)
def create_institution(payload: InstitutionCreate, request: Request, _: User = Depends(_platform_actor), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    raise HTTPException(status.HTTP_409_CONFLICT, "This deployment is configured for SZABIST only.")


@router.patch("/api/v1/platform/institutions/{institution_id}", response_model=InstitutionOut)
def update_institution(institution_id: int, payload: InstitutionUpdate, request: Request, _: User = Depends(_platform_actor), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = _institution(session, institution_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    session.commit()
    session.refresh(row)
    return row


@router.get("/api/v1/platform/institutions/{institution_id}/domains", response_model=list[InstitutionDomainOut])
def list_domains(institution_id: int, _: User = Depends(_platform_actor), session: Session = Depends(get_db)):
    _institution(session, institution_id)
    return session.scalars(select(InstitutionDomain).where(InstitutionDomain.institution_id == institution_id).order_by(InstitutionDomain.domain)).all()


@router.post("/api/v1/platform/institutions/{institution_id}/domains", response_model=InstitutionDomainOut, status_code=status.HTTP_201_CREATED)
def add_domain(institution_id: int, payload: InstitutionDomainCreate, request: Request, _: User = Depends(_platform_actor), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    _institution(session, institution_id)
    if payload.domain != PRIMARY_INSTITUTION_DOMAIN:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only the SZABIST domain @szabist-isb.pk is allowed.")
    row = InstitutionDomain(institution_id=institution_id, domain=payload.domain, is_verified=False, is_active=True)
    session.add(row)
    try:
        session.commit()
        session.refresh(row)
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "That email domain is already registered.") from error
    return row


@router.patch("/api/v1/platform/institution-domains/{domain_id}", response_model=InstitutionDomainOut)
def update_domain(domain_id: int, payload: InstitutionDomainUpdate, request: Request, actor: User = Depends(_platform_actor), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(InstitutionDomain, domain_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Institution domain not found.")
    if primary_institution_id(session) != row.institution_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Institution domain not found.")
    _institution_manager(row.institution_id, actor)
    changes = payload.model_dump(exclude_unset=True)
    if "domain" in changes and changes["domain"] != row.domain:
        if changes["domain"] != PRIMARY_INSTITUTION_DOMAIN:
            raise HTTPException(status.HTTP_409_CONFLICT, "Only the SZABIST domain @szabist-isb.pk is allowed.")
        row.domain = changes.pop("domain")
        row.is_verified = False
        row.verified_at = None
    if "is_verified" in changes and changes["is_verified"] and not is_platform_admin(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a platform administrator can verify domains.")
    for key, value in changes.items():
        setattr(row, key, value)
    if row.is_active:
        row.disabled_at = None
    else:
        row.disabled_at = utc_now()
    try:
        session.commit()
        session.refresh(row)
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "That email domain is already registered.") from error
    return row


@router.post("/api/v1/platform/institution-domains/{domain_id}/verify", response_model=InstitutionDomainOut)
def verify_domain(domain_id: int, request: Request, _: User = Depends(_platform_actor), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(InstitutionDomain, domain_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Institution domain not found.")
    if row.domain != PRIMARY_INSTITUTION_DOMAIN or primary_institution_id(session) != row.institution_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only the SZABIST domain @szabist-isb.pk is allowed.")
    row.is_verified = True
    row.is_active = True
    row.verified_at = utc_now()
    row.disabled_at = None
    session.commit()
    session.refresh(row)
    return row


@router.delete("/api/v1/platform/institution-domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_domain(domain_id: int, request: Request, _: User = Depends(_platform_actor), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(InstitutionDomain, domain_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Institution domain not found.")
    if primary_institution_id(session) != row.institution_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Institution domain not found.")
    if row.domain == PRIMARY_INSTITUTION_DOMAIN:
        raise HTTPException(status.HTTP_409_CONFLICT, "The primary SZABIST domain cannot be removed.")
    session.delete(row)
    session.commit()


@router.get("/api/v1/institutions/{institution_id}/memberships", response_model=list[InstitutionMembershipOut])
def list_memberships(institution_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    _institution(session, institution_id)
    _institution_manager(institution_id, actor)
    return session.scalars(select(InstitutionMembership).where(InstitutionMembership.institution_id == institution_id).order_by(InstitutionMembership.id)).all()


@router.post("/api/v1/institutions/{institution_id}/invitations", response_model=InstitutionInvitationOut, status_code=status.HTTP_201_CREATED)
def create_invitation(institution_id: int, payload: InstitutionInvitationCreate, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    institution = _institution(session, institution_id)
    _institution_manager(institution_id, actor)
    if institution.status != "ACTIVE":
        raise HTTPException(status.HTTP_409_CONFLICT, "The institution is disabled.")
    raw_token = token_urlsafe(32)
    row = InstitutionInvitation(
        institution_id=institution_id,
        email=str(payload.email).lower() if payload.email else None,
        token_hash=hash_session_token(raw_token),
        invited_by_id=actor.id,
        expires_at=utc_now() + timedelta(hours=payload.expires_in_hours),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return InstitutionInvitationOut.model_validate(row).model_copy(update={"invitation_token": raw_token})


@router.post("/api/v1/institutions/{institution_id}/memberships/{membership_id}/approve", response_model=InstitutionMembershipOut)
def approve(institution_id: int, membership_id: int, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    _institution(session, institution_id)
    _institution_manager(institution_id, actor)
    row = session.scalar(select(InstitutionMembership).where(InstitutionMembership.id == membership_id, InstitutionMembership.institution_id == institution_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Institution membership not found.")
    approve_membership(session, row, actor.id)
    session.commit()
    session.refresh(row)
    return row


@router.post("/api/v1/institutions/{institution_id}/memberships/{membership_id}/disable", response_model=InstitutionMembershipOut)
def disable_membership(institution_id: int, membership_id: int, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    _institution(session, institution_id)
    _institution_manager(institution_id, actor)
    row = session.scalar(select(InstitutionMembership).where(InstitutionMembership.id == membership_id, InstitutionMembership.institution_id == institution_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Institution membership not found.")
    row.status = "DISABLED"
    user = session.get(User, row.user_id)
    if user is not None:
        user.is_active = False
    session.commit()
    session.refresh(row)
    return row


def _verify_email_token(raw_token: str, session: Session) -> dict[str, object]:
    token = session.scalar(select(EmailVerificationToken).where(EmailVerificationToken.token_hash == hash_session_token(raw_token)))
    if token is None or token.verified_at is not None or token.expires_at <= utc_now():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The email verification token is invalid or expired.")
    user = session.get(User, token.user_id)
    membership = session.scalar(select(InstitutionMembership).where(InstitutionMembership.user_id == token.user_id, InstitutionMembership.institution_id == token.institution_id))
    if user is None or membership is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The email verification token is invalid.")
    now = utc_now()
    token.verified_at = now
    user.email_verified_at = now
    if membership.status == "APPROVED":
        membership.status = "ACTIVE"
        user.access_approved_at = membership.approved_at or now
        user.is_active = True
    session.commit()
    return {"verified": True, "activated": bool(user.is_active), "institution_id": token.institution_id}


@router.post("/api/v1/auth/verify-email")
def verify_email(payload: VerifyEmailRequest, session: Session = Depends(get_db)):
    return _verify_email_token(payload.token, session)


@router.get("/api/v1/auth/verify-email")
def verify_email_link(token: str = Query(min_length=20, max_length=256), session: Session = Depends(get_db)):
    return _verify_email_token(token, session)

