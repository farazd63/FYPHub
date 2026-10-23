"""Anonymous roster email verification; not an account or membership flow."""
import hashlib
import secrets
from datetime import timedelta
from typing import Literal
from pydantic import Field, BaseModel, ConfigDict, EmailStr, model_validator
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session
from .auth import utc_now, validate_mutating_origin, session_cookie_secure
from .database import get_db
from .individual_verification import IdentityInput, VerifyInput, eligible, send_email, settings, unavailable
from .models import ApprovedStudent, AnonymousVerificationContext, AnonymousVerificationChallenge, AnonymousIdentityProof, Team
from .security import generate_session_token, hash_password, hash_session_token, verify_password

router = APIRouter(prefix='/api/v1/anonymous-verification')
COOKIE = 'fyphub_verification'

class TargetedIdentityInput(IdentityInput):
    purpose: Literal['join_request']
    action: Literal['submit_join_request']
    target_team_id: int = Field(strict=True, gt=0)

class MatchingIdentityInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cycle_id: int = Field(strict=True, gt=0)
    registration_number: str = Field(strict=True, min_length=1, max_length=100)
    university_email: EmailStr
    purpose: Literal['student_matching']
    action: Literal['discover_groups']

class MatchingVerifyInput(MatchingIdentityInput):
    code: str = Field(pattern=r'^[0-9]{8}$', strict=True)

class TargetedVerifyInput(TargetedIdentityInput):
    code: str = Field(pattern=r'^[0-9]{8}$', strict=True)

def valid_target(session, data):
    return session.scalar(select(Team.id).where(Team.id == data.target_team_id, Team.academic_cycle_id == data.cycle_id)) is not None

def client_digest(request):
    return hashlib.sha256((request.client.host if request.client else 'unknown').encode()).hexdigest()

def lock_rate(session, digest):
    session.execute(text('select pg_advisory_xact_lock(:key)'), {'key': int(digest[:15], 16)})

def get_context(session, request, lock=False):
    token = request.cookies.get(COOKIE, '')
    if not token or len(token) > 100: raise HTTPException(400, 'Verification failed.')
    stmt = select(AnonymousVerificationContext).where(AnonymousVerificationContext.token_hash == hash_session_token(token), AnonymousVerificationContext.expires_at > utc_now())
    context = session.scalar(stmt.with_for_update() if lock else stmt)
    if not context: raise HTTPException(400, 'Verification failed.')
    return context

@router.post('/context')
def create_context(request: Request, response: Response, session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    if not settings.smtp_host or not settings.smtp_from or bool(settings.smtp_username) != bool(settings.smtp_password): raise unavailable()
    try:
        digest = client_digest(request); lock_rate(session, digest); now = utc_now()
        count = session.scalar(select(func.count()).select_from(AnonymousVerificationContext).where(AnonymousVerificationContext.client_hash == digest, AnonymousVerificationContext.created_at > now - timedelta(hours=1)))
        if count >= 20: raise HTTPException(429, 'Verification is temporarily unavailable.')
        token = generate_session_token()
        session.add(AnonymousVerificationContext(token_hash=hash_session_token(token), client_hash=digest, expires_at=now + timedelta(minutes=15)))
        session.commit()
        response.set_cookie(COOKIE, token, max_age=900, httponly=True, secure=session_cookie_secure(request), samesite='strict', path='/api/v1')
        return {'message': 'Verification session created.'}
    except HTTPException: session.rollback(); raise
    except Exception: session.rollback(); raise unavailable() from None

@router.post('/challenge')
def challenge(data: TargetedIdentityInput | MatchingIdentityInput, request: Request, session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    if not settings.smtp_host or not settings.smtp_from or bool(settings.smtp_username) != bool(settings.smtp_password): raise unavailable()
    try:
        context = get_context(session, request, lock=True)
        student = eligible(session, data)
        if not student or (data.purpose == 'join_request' and not valid_target(session, data)):
            session.rollback(); return {'message': 'If eligible, a verification code may be sent.'}
        session.execute(select(ApprovedStudent.id).where(ApprovedStudent.id == student.id).with_for_update()).scalar_one()
        now = utc_now()
        recent = session.scalars(select(AnonymousVerificationChallenge).where(AnonymousVerificationChallenge.student_id == student.id, AnonymousVerificationChallenge.created_at > now - timedelta(hours=1))).all()
        if len(recent) >= 5 or any(row.created_at > now - timedelta(seconds=60) for row in recent):
            session.rollback(); return {'message': 'If eligible, a verification code may be sent.'}
        session.execute(update(AnonymousVerificationChallenge).where(AnonymousVerificationChallenge.student_id == student.id, AnonymousVerificationChallenge.consumed_at.is_(None)).values(consumed_at=now))
        code = f'{secrets.randbelow(100000000):08d}'
        session.add(AnonymousVerificationChallenge(context_id=context.id, student_id=student.id, cycle_id=data.cycle_id, purpose=data.purpose, action=data.action, target_team_id=getattr(data, 'target_team_id', None), code_hash=hash_password(code), expires_at=now + timedelta(minutes=10)))
        session.flush(); send_email(student.university_email, code); session.commit()
        return {'message': 'If eligible, a verification code may be sent.'}
    except HTTPException: session.rollback(); raise
    except Exception: session.rollback(); raise unavailable() from None

@router.post('/verify')
def verify(data: TargetedVerifyInput | MatchingVerifyInput, request: Request, session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    try:
        context = get_context(session, request, lock=True); student = eligible(session, data)
        if not student or (data.purpose == 'join_request' and not valid_target(session, data)): raise HTTPException(400, 'Verification failed.')
        row = session.scalar(select(AnonymousVerificationChallenge).where(AnonymousVerificationChallenge.context_id == context.id, AnonymousVerificationChallenge.student_id == student.id, AnonymousVerificationChallenge.cycle_id == data.cycle_id, AnonymousVerificationChallenge.purpose == data.purpose, AnonymousVerificationChallenge.action == data.action, AnonymousVerificationChallenge.target_team_id == getattr(data, 'target_team_id', None)).order_by(AnonymousVerificationChallenge.id.desc()).with_for_update())
        now = utc_now()
        if not row or row.consumed_at is not None or row.expires_at <= now or row.attempts >= 5: raise HTTPException(400, 'Verification failed.')
        if not verify_password(data.code, row.code_hash):
            row.attempts += 1; session.commit(); raise HTTPException(400, 'Verification failed.')
        token = generate_session_token(); row.consumed_at = now
        session.add(AnonymousIdentityProof(challenge_id=row.id, context_id=context.id, student_id=student.id, cycle_id=data.cycle_id, purpose=data.purpose, action=data.action, target_team_id=getattr(data, 'target_team_id', None), token_hash=hash_session_token(token), expires_at=min(context.expires_at, now + timedelta(minutes=5))))
        session.commit(); return {'proof': token, 'expires_in_seconds': max(0, min(300, int((context.expires_at-now).total_seconds())))}
    except HTTPException: session.rollback(); raise
    except Exception: session.rollback(); raise HTTPException(500, 'Verification could not be completed.') from None

def consume_anonymous_proof(session: Session, proof: str, context_token: str, *, student_id: int, cycle_id: int, purpose: str, action: str, target_team_id: int) -> bool:
    """Consume in the caller's transaction, without committing its action."""
    if purpose != 'join_request' or action != 'submit_join_request' or target_team_id <= 0 or not context_token or not proof: return False
    now = utc_now()
    return session.execute(update(AnonymousIdentityProof).where(AnonymousIdentityProof.token_hash == hash_session_token(proof), AnonymousIdentityProof.student_id == student_id, AnonymousIdentityProof.cycle_id == cycle_id, AnonymousIdentityProof.purpose == purpose, AnonymousIdentityProof.action == action, AnonymousIdentityProof.target_team_id == target_team_id, select(Team.id).where(Team.id == target_team_id, Team.academic_cycle_id == cycle_id).exists(), AnonymousIdentityProof.expires_at > now, AnonymousIdentityProof.consumed_at.is_(None), select(AnonymousVerificationContext.id).where(AnonymousVerificationContext.id == AnonymousIdentityProof.context_id, AnonymousVerificationContext.token_hash == hash_session_token(context_token), AnonymousVerificationContext.expires_at > now).exists(), select(ApprovedStudent.id).where(ApprovedStudent.id == student_id, ApprovedStudent.academic_cycle_id == cycle_id, ApprovedStudent.semester.in_((7,8))).exists()).values(consumed_at=now).returning(AnonymousIdentityProof.id)).scalar_one_or_none() is not None
