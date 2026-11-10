"""Join-request submission. Decisions require a separately scoped creator proof."""
import secrets
from datetime import timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session
from .anonymous_verification import COOKIE, TargetedIdentityInput, consume_anonymous_proof
from .auth import get_current_user, utc_now, validate_mutating_origin
from .database import get_db
from .individual_verification import IdentityInput, eligible, guard, send_email, settings, unavailable
from .models import AcademicCycle, AcademicGroupPolicy, ApprovedStudent, IdentityChallenge, IdentityProof, JoinRequest, JoinRequestAudit, Module2Notification, Team, TeamMember, User
from .team_lifecycle import refresh_team_status
from .security import generate_session_token, hash_password, hash_session_token, verify_password

router = APIRouter(prefix='/api/v1/join-requests')

class Submission(TargetedIdentityInput):
    proof: str = Field(min_length=1, max_length=256, strict=True)

@router.post('', status_code=201)
def submit(data: Submission, request: Request, session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    try:
        cycle = session.scalar(select(AcademicCycle).where(AcademicCycle.id == data.cycle_id).with_for_update())
        policy = session.scalar(select(AcademicGroupPolicy).where(AcademicGroupPolicy.academic_cycle_id == data.cycle_id).with_for_update())
        team = session.scalar(select(Team).where(Team.id == data.target_team_id, Team.academic_cycle_id == data.cycle_id).with_for_update())
        student = eligible(session, data)
        if not cycle or not policy or not team or not student:
            raise HTTPException(400, 'Join request could not be submitted.')
        member = session.scalar(select(TeamMember.id).where(TeamMember.academic_cycle_id == cycle.id, TeamMember.is_active.is_(True), or_(func.lower(TeamMember.registration_number) == student.registration_number.lower(), func.lower(TeamMember.university_email) == student.university_email.lower())))
        count = session.scalar(select(func.count()).select_from(TeamMember).where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True)))
        pending = session.scalar(select(JoinRequest.id).where(JoinRequest.team_id == team.id, JoinRequest.student_id == student.id, JoinRequest.status == 'pending'))
        if member or count >= policy.max_group_size or pending:
            raise HTTPException(400, 'Join request could not be submitted.')
        if not consume_anonymous_proof(session, data.proof, request.cookies.get(COOKIE, ''), student_id=student.id, cycle_id=cycle.id, purpose='join_request', action='submit_join_request', target_team_id=team.id):
            raise HTTPException(400, 'Join request could not be submitted.')
        row = JoinRequest(team_id=team.id, cycle_id=cycle.id, student_id=student.id, expires_at=utc_now() + timedelta(days=7))
        session.add(row); session.flush()
        session.add(JoinRequestAudit(request_id=row.id, actor_student_id=student.id, action='submitted'))
        session.commit()
        return {'id': row.id, 'status': row.status}
    except HTTPException:
        session.rollback(); raise
    except Exception:
        session.rollback(); raise HTTPException(500, 'Join request could not be submitted.') from None


class CreatorInput(IdentityInput):
    purpose: Literal['join_request']
    action: Literal['accept_join_request', 'reject_join_request']

class CreatorVerify(CreatorInput):
    code: str = Field(pattern=r'^[0-9]{8}$', strict=True)

class DecisionProof(CreatorInput):
    proof: str = Field(min_length=1, max_length=256, strict=True)


def creator(session, actor, row, data):
    student = eligible(session, data)
    if not student or row.cycle_id != data.cycle_id:
        return None
    found = session.scalar(select(TeamMember.id).join(Team, Team.id == TeamMember.team_id).where(
        Team.id == row.team_id, Team.shared_user_id == actor.id,
        Team.academic_cycle_id == data.cycle_id, TeamMember.is_creator.is_(True),
        TeamMember.is_active.is_(True), TeamMember.academic_cycle_id == data.cycle_id,
        func.lower(TeamMember.registration_number) == student.registration_number.lower(),
        func.lower(TeamMember.university_email) == student.university_email.lower()))
    return student if found else None

@router.post('/{request_id}/creator/challenge')
def creator_challenge(request_id: int, data: CreatorInput, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    guard(request, actor)
    if not settings.smtp_host or not settings.smtp_from or bool(settings.smtp_username) != bool(settings.smtp_password):
        raise unavailable()
    try:
        row = session.get(JoinRequest, request_id)
        student = creator(session, actor, row, data) if row and row.status == 'pending' else None
        if not student:
            raise HTTPException(400, 'Verification failed.')
        session.execute(select(ApprovedStudent.id).where(ApprovedStudent.id == student.id).with_for_update()).scalar_one()
        now = utc_now()
        recent = session.scalars(select(IdentityChallenge).where(IdentityChallenge.created_at > now - timedelta(hours=1), (IdentityChallenge.actor_id == actor.id) | (IdentityChallenge.student_id == student.id))).all()
        if len(recent) >= 5 or any(item.created_at > now - timedelta(seconds=60) for item in recent):
            return {'message': 'If eligible, a verification code may be sent.'}
        session.execute(update(IdentityChallenge).where(IdentityChallenge.student_id == student.id, IdentityChallenge.consumed_at.is_(None)).values(consumed_at=now))
        code = f'{secrets.randbelow(100000000):08d}'
        session.add(IdentityChallenge(student_id=student.id, cycle_id=row.cycle_id, actor_id=actor.id, purpose='join_request', action=data.action, target_request_id=row.id, target_team_id=row.team_id, code_hash=hash_password(code), expires_at=now + timedelta(minutes=10)))
        session.flush(); send_email(student.university_email, code); session.commit()
        return {'message': 'If eligible, a verification code may be sent.'}
    except HTTPException:
        session.rollback(); raise
    except Exception:
        session.rollback(); raise unavailable() from None

@router.post('/{request_id}/creator/verify')
def creator_verify(request_id: int, data: CreatorVerify, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    guard(request, actor)
    try:
        row = session.get(JoinRequest, request_id)
        student = creator(session, actor, row, data) if row and row.status == 'pending' else None
        if not student: raise HTTPException(400, 'Verification failed.')
        challenge = session.scalar(select(IdentityChallenge).where(IdentityChallenge.student_id == student.id, IdentityChallenge.actor_id == actor.id, IdentityChallenge.cycle_id == row.cycle_id, IdentityChallenge.purpose == 'join_request', IdentityChallenge.action == data.action, IdentityChallenge.target_request_id == row.id, IdentityChallenge.target_team_id == row.team_id).order_by(IdentityChallenge.id.desc()).with_for_update())
        now = utc_now()
        if not challenge or challenge.consumed_at is not None or challenge.expires_at <= now or challenge.attempts >= 5: raise HTTPException(400, 'Verification failed.')
        if not verify_password(data.code, challenge.code_hash):
            challenge.attempts += 1; session.commit(); raise HTTPException(400, 'Verification failed.')
        token = generate_session_token(); challenge.consumed_at = now
        session.add(IdentityProof(challenge_id=challenge.id, student_id=student.id, cycle_id=row.cycle_id, actor_id=actor.id, purpose='join_request', action=data.action, target_request_id=row.id, target_team_id=row.team_id, token_hash=hash_session_token(token), expires_at=now + timedelta(minutes=5)))
        session.commit(); return {'proof': token, 'expires_in_seconds': 300}
    except HTTPException:
        session.rollback(); raise
    except Exception:
        session.rollback(); raise HTTPException(500, 'Verification could not be completed.') from None

@router.post('/{request_id}/decision')
def decide(request_id: int, data: DecisionProof, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    guard(request, actor)
    try:
        cycle = session.scalar(select(AcademicCycle).where(AcademicCycle.id == data.cycle_id).with_for_update())
        policy = session.scalar(select(AcademicGroupPolicy).where(AcademicGroupPolicy.academic_cycle_id == data.cycle_id).with_for_update())
        identity = session.get(JoinRequest, request_id)
        team = session.scalar(select(Team).where(Team.id == identity.team_id, Team.academic_cycle_id == data.cycle_id).with_for_update()) if identity else None
        row = session.scalar(select(JoinRequest).where(JoinRequest.id == request_id).with_for_update())
        person = creator(session, actor, row, data) if row and team and cycle and policy and row.status == 'pending' else None
        student = session.get(ApprovedStudent, row.student_id) if row else None
        if not person or not student or student.academic_cycle_id != data.cycle_id or student.semester not in (7, 8): raise HTTPException(400, 'Join request could not be decided.')
        if data.action == 'accept_join_request':
            member = session.scalar(select(TeamMember.id).where(TeamMember.academic_cycle_id == data.cycle_id, TeamMember.is_active.is_(True), or_(func.lower(TeamMember.registration_number) == student.registration_number.lower(), func.lower(TeamMember.university_email) == student.university_email.lower())))
            count = session.scalar(select(func.count()).select_from(TeamMember).where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True)))
            if member or count >= policy.max_group_size: raise HTTPException(400, 'Join request could not be decided.')
        consumed = session.execute(update(IdentityProof).where(IdentityProof.token_hash == hash_session_token(data.proof), IdentityProof.student_id == person.id, IdentityProof.cycle_id == data.cycle_id, IdentityProof.actor_id == actor.id, IdentityProof.purpose == 'join_request', IdentityProof.action == data.action, IdentityProof.target_request_id == row.id, IdentityProof.target_team_id == team.id, IdentityProof.expires_at > utc_now(), IdentityProof.consumed_at.is_(None)).values(consumed_at=utc_now()).returning(IdentityProof.id)).scalar_one_or_none()
        if consumed is None: raise HTTPException(400, 'Join request could not be decided.')
        row.status = 'accepted' if data.action == 'accept_join_request' else 'rejected'
        if row.status == 'accepted':
            session.add(TeamMember(team_id=team.id, academic_cycle_id=data.cycle_id, student_id=student.id, full_name=student.name.strip(), registration_number=student.registration_number.strip().upper(), university_email=student.university_email.strip().lower(), is_creator=False, is_active=True))
            session.flush()
            session.execute(update(JoinRequest).where(JoinRequest.student_id == student.id, JoinRequest.cycle_id == data.cycle_id, JoinRequest.status == 'pending', JoinRequest.id != row.id).values(status='cancelled'))
            from .models import Invitation
            session.execute(update(Invitation).where(Invitation.student_id == student.id, Invitation.cycle_id == data.cycle_id, Invitation.status == 'pending').values(status='cancelled'))
            refresh_team_status(session, team)
            session.add(Module2Notification(recipient_user_id=team.shared_user_id, kind='join_request_decided', payload={'team_id': team.id, 'request_id': row.id, 'status': row.status}))
        session.add(JoinRequestAudit(request_id=row.id, actor_student_id=person.id, action=row.status))
        session.commit(); return {'id': row.id, 'status': row.status}
    except HTTPException:
        session.rollback(); raise
    except Exception:
        session.rollback(); raise HTTPException(500, 'Join request could not be decided.') from None

@router.get('/team/{team_id}')
def list_requests(team_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    team = session.scalar(select(Team).where(Team.id == team_id, Team.shared_user_id == actor.id))
    if not team:
        raise HTTPException(403, 'Team access is required.')
    session.execute(update(JoinRequest).where(JoinRequest.team_id == team.id, JoinRequest.status == 'pending', JoinRequest.expires_at.is_not(None), JoinRequest.expires_at <= utc_now()).values(status='expired'))
    rows = session.execute(select(JoinRequest, ApprovedStudent).join(ApprovedStudent, ApprovedStudent.id == JoinRequest.student_id).where(JoinRequest.team_id == team.id, JoinRequest.cycle_id == team.academic_cycle_id).order_by(JoinRequest.id.desc()).limit(100)).all()
    return [{'id': row.id, 'status': row.status, 'student_name': student.name, 'registration_number': student.registration_number} for row, student in rows]
