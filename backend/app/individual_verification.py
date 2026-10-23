"""Roster-bound one-time codes and transactional identity proofs."""
import secrets
import smtplib
from datetime import timedelta
from email.message import EmailMessage
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from .auth import get_current_user, utc_now, validate_mutating_origin
from .config import settings
from .database import get_db
from .models import ApprovedStudent, IdentityChallenge, IdentityProof, Team, TeamMember, User, UserRole
from .security import generate_session_token, hash_session_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1/individual-verification")
Purpose = Literal["join_request", "invitation"]

class IdentityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cycle_id: int = Field(gt=0, strict=True)
    registration_number: str = Field(min_length=1, max_length=100, strict=True)
    university_email: EmailStr
    purpose: Purpose

class VerifyInput(IdentityInput):
    code: str = Field(pattern=r"^[0-9]{8}$", strict=True)

def unavailable():
    return HTTPException(503, "Email verification is unavailable.")

def eligible(session, data):
    return session.scalar(select(ApprovedStudent).where(ApprovedStudent.academic_cycle_id == data.cycle_id, func.lower(ApprovedStudent.registration_number) == data.registration_number.strip().lower(), func.lower(ApprovedStudent.university_email) == str(data.university_email).strip().lower(), ApprovedStudent.semester.in_((7, 8))))

def send_email(address, code):
    if not settings.smtp_host or not settings.smtp_from or bool(settings.smtp_username) != bool(settings.smtp_password):
        raise unavailable()
    msg = EmailMessage()
    msg['From'], msg['To'], msg['Subject'] = settings.smtp_from, address, 'FYPHub verification code'
    msg.set_content(f'Your verification code is {code}. It expires in 10 minutes.')
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_username: smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
    except Exception:
        raise unavailable() from None

def guard(request, actor):
    validate_mutating_origin(request)
    if actor.role != UserRole.STUDENT: raise HTTPException(403, 'Student access is required.')

@router.post('/challenge')
def challenge(data: IdentityInput, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    guard(request, actor)
    if not settings.smtp_host or not settings.smtp_from or bool(settings.smtp_username) != bool(settings.smtp_password): raise unavailable()
    try:
        session.execute(select(User.id).where(User.id == actor.id).with_for_update()).scalar_one()
        student = eligible(session, data)
        if not student:
            session.rollback()
            return {'message': 'If eligible, a verification code may be sent.'}
        session.execute(select(ApprovedStudent.id).where(ApprovedStudent.id == student.id).with_for_update()).scalar_one()
        now = utc_now()
        recent = session.scalars(select(IdentityChallenge).where(IdentityChallenge.created_at > now - timedelta(hours=1), (IdentityChallenge.actor_id == actor.id) | (IdentityChallenge.student_id == student.id))).all()
        if len(recent) >= 5 or any(row.created_at > now - timedelta(seconds=60) for row in recent):
            session.rollback()
            return {'message': 'If eligible, a verification code may be sent.'}
        session.execute(update(IdentityChallenge).where(IdentityChallenge.student_id == student.id, IdentityChallenge.consumed_at.is_(None)).values(consumed_at=now))
        code = f'{secrets.randbelow(100000000):08d}'
        session.add(IdentityChallenge(student_id=student.id, cycle_id=data.cycle_id, actor_id=actor.id, purpose=data.purpose, code_hash=hash_password(code), expires_at=now + timedelta(minutes=10)))
        session.flush()
        send_email(student.university_email, code)
        session.commit()
        return {'message': 'If eligible, a verification code may be sent.'}
    except HTTPException:
        session.rollback(); raise
    except Exception:
        session.rollback(); raise unavailable() from None

@router.post('/verify')
def verify(data: VerifyInput, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    guard(request, actor)
    try:
        student = eligible(session, data)
        if not student: raise HTTPException(400, 'Verification failed.')
        row = session.scalar(select(IdentityChallenge).where(IdentityChallenge.student_id == student.id, IdentityChallenge.actor_id == actor.id, IdentityChallenge.cycle_id == data.cycle_id, IdentityChallenge.purpose == data.purpose).order_by(IdentityChallenge.id.desc()).with_for_update())
        now = utc_now()
        if not row or row.consumed_at is not None or row.expires_at <= now or row.attempts >= 5: raise HTTPException(400, 'Verification failed.')
        if not verify_password(data.code, row.code_hash):
            row.attempts += 1
            session.commit()
            raise HTTPException(400, 'Verification failed.')
        token = generate_session_token()
        row.consumed_at = now
        session.add(IdentityProof(challenge_id=row.id, student_id=student.id, cycle_id=data.cycle_id, actor_id=actor.id, purpose=data.purpose, token_hash=hash_session_token(token), expires_at=now + timedelta(minutes=5)))
        session.commit()
        return {'proof': token, 'expires_in_seconds': 300}
    except HTTPException:
        session.rollback(); raise
    except Exception:
        session.rollback(); raise HTTPException(500, 'Verification could not be completed.') from None

def consume_identity_proof(session: Session, token: str, *, student_id: int, cycle_id: int, actor_id: int, purpose: Purpose) -> bool:
    """Consume with the caller's action in the same transaction; do not commit here."""
    now = utc_now()
    return session.execute(update(IdentityProof).where(IdentityProof.token_hash == hash_session_token(token), IdentityProof.student_id == student_id, IdentityProof.cycle_id == cycle_id, IdentityProof.actor_id == actor_id, IdentityProof.purpose == purpose, IdentityProof.expires_at > now, IdentityProof.consumed_at.is_(None), select(ApprovedStudent.id).where(ApprovedStudent.id == student_id, ApprovedStudent.academic_cycle_id == cycle_id, ApprovedStudent.semester.in_((7, 8))).exists()).values(consumed_at=now).returning(IdentityProof.id)).scalar_one_or_none() is not None


def consume_creator_proof(session: Session, token: str, *, team_id: int, actor_id: int, purpose: Purpose) -> bool:
    """Consume the recorded creator's proof within the caller's transaction.

    This building block does not bind a proof to an individual request or
    invitation; callers must not treat it as complete action authorization.
    """
    row = session.execute(
        select(Team.academic_cycle_id, ApprovedStudent.id)
        .join(TeamMember, (TeamMember.team_id == Team.id) & (TeamMember.academic_cycle_id == Team.academic_cycle_id))
        .join(ApprovedStudent, (ApprovedStudent.academic_cycle_id == Team.academic_cycle_id)
              & (func.lower(ApprovedStudent.registration_number) == func.lower(TeamMember.registration_number))
              & (func.lower(ApprovedStudent.university_email) == func.lower(TeamMember.university_email)))
        .join(User, User.id == Team.shared_user_id)
        .where(Team.id == team_id, Team.shared_user_id == actor_id, User.is_active.is_(True),
               User.role == UserRole.STUDENT, TeamMember.is_creator.is_(True), TeamMember.is_active.is_(True),
               ApprovedStudent.semester.in_((7, 8)))
    ).one_or_none()
    if row is None:
        return False
    return consume_identity_proof(session, token, student_id=row.id, cycle_id=row.academic_cycle_id, actor_id=actor_id, purpose=purpose)
