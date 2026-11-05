"""Invitation-specific verification and transactional team membership."""
import secrets
import smtplib
from datetime import timedelta
from email.message import EmailMessage
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session
from .anonymous_verification import COOKIE, get_context
from .auth import get_current_user, utc_now, validate_mutating_origin
from .database import get_db
from .individual_verification import eligible, guard, send_email, settings, unavailable
from .models import AcademicCycle, AcademicGroupPolicy, ApprovedStudent, AnonymousIdentityProof, AnonymousVerificationChallenge, IdentityChallenge, IdentityProof, Invitation, InvitationAudit, InvitationOutbox, Module2Notification, Team, TeamMember, User
from .team_lifecycle import refresh_team_status
from .security import generate_session_token, hash_password, hash_session_token, verify_password

router = APIRouter(prefix='/api/v1/invitations')

class CreatorInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cycle_id: int = Field(strict=True, gt=0)
    team_id: int = Field(strict=True, gt=0)
    registration_number: str = Field(strict=True, min_length=1, max_length=100)
    university_email: EmailStr
    recipient_registration: str = Field(strict=True, min_length=1, max_length=100)
    recipient_email: EmailStr
    action: Literal['send_invitation']

class CreatorVerify(CreatorInput):
    code: str = Field(strict=True, pattern=r'^[0-9]{8}$')

class CreatorSend(CreatorInput):
    proof: str = Field(strict=True, min_length=1, max_length=256)

class InviteeInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cycle_id: int = Field(strict=True, gt=0)
    invitation_id: int = Field(strict=True, gt=0)
    registration_number: str = Field(strict=True, min_length=1, max_length=100)
    university_email: EmailStr
    action: Literal['accept_invitation', 'reject_invitation']

class InviteeVerify(InviteeInput):
    code: str = Field(strict=True, pattern=r'^[0-9]{8}$')

class InviteeDecision(InviteeInput):
    proof: str = Field(strict=True, min_length=1, max_length=256)


def creator_and_recipient(session, actor, data):
    creator = eligible(session, data)
    recipient = session.scalar(select(ApprovedStudent).where(ApprovedStudent.academic_cycle_id == data.cycle_id, func.lower(ApprovedStudent.registration_number) == data.recipient_registration.strip().lower(), func.lower(ApprovedStudent.university_email) == str(data.recipient_email).strip().lower(), ApprovedStudent.semester.in_((7, 8))))
    if not creator or not recipient: return None, None
    found = session.scalar(select(TeamMember.id).join(Team, Team.id == TeamMember.team_id).where(Team.id == data.team_id, Team.academic_cycle_id == data.cycle_id, Team.shared_user_id == actor.id, TeamMember.academic_cycle_id == data.cycle_id, TeamMember.is_creator.is_(True), TeamMember.is_active.is_(True), func.lower(TeamMember.registration_number) == creator.registration_number.lower(), func.lower(TeamMember.university_email) == creator.university_email.lower()))
    return (creator, recipient) if found else (None, None)


def send_invitation_email(address, invitation_id, cycle_id):
    if not settings.smtp_host or not settings.smtp_from or bool(settings.smtp_username) != bool(settings.smtp_password): raise unavailable()
    msg = EmailMessage(); msg['From'] = settings.smtp_from; msg['To'] = address; msg['Subject'] = 'FYPHub team invitation'
    msg.set_content(f'You have received a team invitation. Invitation ID: {invitation_id}; academic cycle ID: {cycle_id}. Open FYPHub to verify your university email and respond.')
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_username: smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
    except Exception: raise unavailable() from None

def dispatch_invitation(session: Session, invitation_id: int, *, retry_failed: bool = False) -> str:
    """Dispatch committed work under a row lock. SMTP is not exactly-once."""
    try:
        outbox = session.scalar(select(InvitationOutbox).where(InvitationOutbox.invitation_id == invitation_id).with_for_update())
        if not outbox:
            session.rollback(); return 'unknown'
        if outbox.status != 'queued' and not (retry_failed and outbox.status == 'failed'):
            status = outbox.status; session.rollback(); return status
        invitation = session.get(Invitation, invitation_id)
        recipient = session.get(ApprovedStudent, invitation.student_id)
        try:
            send_invitation_email(recipient.university_email, invitation.id, invitation.cycle_id)
            outbox.status = 'smtp_accepted'
        except Exception:
            outbox.status = 'failed'
        session.commit()
        return outbox.status
    except Exception:
        session.rollback()
        return 'queued'


@router.post('/creator/challenge')
def creator_challenge(data: CreatorInput, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    guard(request, actor)
    if not settings.smtp_host or not settings.smtp_from or bool(settings.smtp_username) != bool(settings.smtp_password): raise unavailable()
    try:
        person, recipient = creator_and_recipient(session, actor, data)
        if not person:
            session.rollback()
            return {'message': 'If eligible, a verification code may be sent.'}
        session.execute(select(ApprovedStudent.id).where(ApprovedStudent.id == person.id).with_for_update()).scalar_one()
        now=utc_now(); recent=session.scalars(select(IdentityChallenge).where(IdentityChallenge.created_at > now-timedelta(hours=1), (IdentityChallenge.actor_id==actor.id)|(IdentityChallenge.student_id==person.id))).all()
        if len(recent)>=5 or any(row.created_at>now-timedelta(seconds=60) for row in recent): return {'message':'If eligible, a verification code may be sent.'}
        session.execute(update(IdentityChallenge).where(IdentityChallenge.student_id==person.id,IdentityChallenge.consumed_at.is_(None)).values(consumed_at=now))
        code=f'{secrets.randbelow(100000000):08d}'
        session.add(IdentityChallenge(student_id=person.id,cycle_id=data.cycle_id,actor_id=actor.id,purpose='invitation',action=data.action,target_team_id=data.team_id,target_student_id=recipient.id,code_hash=hash_password(code),expires_at=now+timedelta(minutes=10)))
        session.flush();send_email(person.university_email,code);session.commit();return {'message':'If eligible, a verification code may be sent.'}
    except HTTPException: session.rollback();raise
    except Exception: session.rollback();raise unavailable() from None

@router.post('/creator/verify')
def creator_verify(data: CreatorVerify, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    guard(request,actor)
    try:
        person,recipient=creator_and_recipient(session,actor,data)
        if not person: raise HTTPException(400,'Verification failed.')
        row=session.scalar(select(IdentityChallenge).where(IdentityChallenge.student_id==person.id,IdentityChallenge.actor_id==actor.id,IdentityChallenge.cycle_id==data.cycle_id,IdentityChallenge.purpose=='invitation',IdentityChallenge.action==data.action,IdentityChallenge.target_team_id==data.team_id,IdentityChallenge.target_student_id==recipient.id).order_by(IdentityChallenge.id.desc()).with_for_update());now=utc_now()
        if not row or row.consumed_at is not None or row.expires_at<=now or row.attempts>=5: raise HTTPException(400,'Verification failed.')
        if not verify_password(data.code,row.code_hash): row.attempts+=1;session.commit();raise HTTPException(400,'Verification failed.')
        token=generate_session_token();row.consumed_at=now
        session.add(IdentityProof(challenge_id=row.id,student_id=person.id,cycle_id=data.cycle_id,actor_id=actor.id,purpose='invitation',action=data.action,target_team_id=data.team_id,target_student_id=recipient.id,token_hash=hash_session_token(token),expires_at=now+timedelta(minutes=5)))
        session.commit();return {'proof':token,'expires_in_seconds':300}
    except HTTPException: session.rollback();raise
    except Exception: session.rollback();raise HTTPException(500,'Verification could not be completed.') from None

@router.post('',status_code=201)
def send(data: CreatorSend,request:Request,actor:User=Depends(get_current_user),session:Session=Depends(get_db)):
    guard(request,actor)
    try:
        cycle=session.scalar(select(AcademicCycle).where(AcademicCycle.id==data.cycle_id).with_for_update())
        policy=session.scalar(select(AcademicGroupPolicy).where(AcademicGroupPolicy.academic_cycle_id==data.cycle_id).with_for_update())
        team=session.scalar(select(Team).where(Team.id==data.team_id,Team.academic_cycle_id==data.cycle_id).with_for_update())
        person,recipient=creator_and_recipient(session,actor,data)
        if not cycle or not policy or not team or not person or not recipient: raise HTTPException(400,'Invitation could not be sent.')
        member=session.scalar(select(TeamMember.id).where(TeamMember.academic_cycle_id==cycle.id,TeamMember.is_active.is_(True),or_(func.lower(TeamMember.registration_number)==recipient.registration_number.lower(),func.lower(TeamMember.university_email)==recipient.university_email.lower())))
        count=session.scalar(select(func.count()).select_from(TeamMember).where(TeamMember.team_id==team.id,TeamMember.is_active.is_(True)))
        pending=session.scalar(select(Invitation.id).where(Invitation.team_id==team.id,Invitation.student_id==recipient.id,Invitation.status=='pending'))
        if member or count>=policy.max_group_size or pending: raise HTTPException(400,'Invitation could not be sent.')
        consumed=session.execute(update(IdentityProof).where(IdentityProof.token_hash==hash_session_token(data.proof),IdentityProof.student_id==person.id,IdentityProof.cycle_id==cycle.id,IdentityProof.actor_id==actor.id,IdentityProof.purpose=='invitation',IdentityProof.action=='send_invitation',IdentityProof.target_team_id==team.id,IdentityProof.target_student_id==recipient.id,IdentityProof.expires_at>utc_now(),IdentityProof.consumed_at.is_(None)).values(consumed_at=utc_now()).returning(IdentityProof.id)).scalar_one_or_none()
        if consumed is None: raise HTTPException(400,'Invitation could not be sent.')
        row=Invitation(team_id=team.id,cycle_id=cycle.id,student_id=recipient.id,status='pending',expires_at=utc_now()+timedelta(days=7));session.add(row);session.flush()
        session.add(InvitationAudit(invitation_id=row.id,actor_student_id=person.id,action='queued'))
        session.add(InvitationOutbox(invitation_id=row.id,status='queued'));session.commit()
        invitation_id=row.id
        delivery=dispatch_invitation(session,invitation_id)
        return {'id':invitation_id,'status':'pending','delivery':delivery}
    except HTTPException: session.rollback();raise
    except Exception: session.rollback();raise HTTPException(500,'Invitation could not be sent.') from None

def invitee_target(session,data):
    person=eligible(session,data)
    if not person: return None,None
    row=session.scalar(select(Invitation).where(Invitation.id==data.invitation_id,Invitation.cycle_id==data.cycle_id,Invitation.student_id==person.id,Invitation.status=='pending', select(InvitationOutbox.id).where(InvitationOutbox.invitation_id==Invitation.id,InvitationOutbox.status=='smtp_accepted').exists()))
    return (person,row) if row else (None,None)

@router.post('/invitee/challenge')
def invitee_challenge(data:InviteeInput,request:Request,session:Session=Depends(get_db)):
    validate_mutating_origin(request)
    if not settings.smtp_host or not settings.smtp_from or bool(settings.smtp_username)!=bool(settings.smtp_password): raise unavailable()
    try:
        context=get_context(session,request,lock=True);person,row=invitee_target(session,data)
        if not person: session.rollback();return {'message':'If eligible, a verification code may be sent.'}
        session.execute(select(ApprovedStudent.id).where(ApprovedStudent.id==person.id).with_for_update()).scalar_one();now=utc_now()
        recent=session.scalars(select(AnonymousVerificationChallenge).where(AnonymousVerificationChallenge.student_id==person.id,AnonymousVerificationChallenge.created_at>now-timedelta(hours=1))).all()
        if len(recent)>=5 or any(item.created_at>now-timedelta(seconds=60) for item in recent): session.rollback();return {'message':'If eligible, a verification code may be sent.'}
        session.execute(update(AnonymousVerificationChallenge).where(AnonymousVerificationChallenge.student_id==person.id,AnonymousVerificationChallenge.consumed_at.is_(None)).values(consumed_at=now))
        code=f'{secrets.randbelow(100000000):08d}';session.add(AnonymousVerificationChallenge(context_id=context.id,student_id=person.id,cycle_id=data.cycle_id,purpose='invitation',action=data.action,target_team_id=row.team_id,target_invitation_id=row.id,code_hash=hash_password(code),expires_at=now+timedelta(minutes=10)))
        session.flush();send_email(person.university_email,code);session.commit();return {'message':'If eligible, a verification code may be sent.'}
    except HTTPException: session.rollback();raise
    except Exception: session.rollback();raise unavailable() from None

@router.post('/invitee/verify')
def invitee_verify(data:InviteeVerify,request:Request,session:Session=Depends(get_db)):
    validate_mutating_origin(request)
    try:
        context=get_context(session,request,lock=True);person,invitation=invitee_target(session,data)
        if not person: raise HTTPException(400,'Verification failed.')
        row=session.scalar(select(AnonymousVerificationChallenge).where(AnonymousVerificationChallenge.context_id==context.id,AnonymousVerificationChallenge.student_id==person.id,AnonymousVerificationChallenge.cycle_id==data.cycle_id,AnonymousVerificationChallenge.purpose=='invitation',AnonymousVerificationChallenge.action==data.action,AnonymousVerificationChallenge.target_invitation_id==invitation.id,AnonymousVerificationChallenge.target_team_id==invitation.team_id).order_by(AnonymousVerificationChallenge.id.desc()).with_for_update());now=utc_now()
        if not row or row.consumed_at is not None or row.expires_at<=now or row.attempts>=5: raise HTTPException(400,'Verification failed.')
        if not verify_password(data.code,row.code_hash): row.attempts+=1;session.commit();raise HTTPException(400,'Verification failed.')
        token=generate_session_token();row.consumed_at=now
        session.add(AnonymousIdentityProof(challenge_id=row.id,context_id=context.id,student_id=person.id,cycle_id=data.cycle_id,purpose='invitation',action=data.action,target_team_id=invitation.team_id,target_invitation_id=invitation.id,token_hash=hash_session_token(token),expires_at=min(context.expires_at,now+timedelta(minutes=5))))
        session.commit();return {'proof':token,'expires_in_seconds':max(0,min(300,int((context.expires_at-now).total_seconds())))}
    except HTTPException: session.rollback();raise
    except Exception: session.rollback();raise HTTPException(500,'Verification could not be completed.') from None

@router.post('/invitee/decision')
def decide(data:InviteeDecision,request:Request,session:Session=Depends(get_db)):
    validate_mutating_origin(request)
    try:
        cycle=session.scalar(select(AcademicCycle).where(AcademicCycle.id==data.cycle_id).with_for_update())
        policy=session.scalar(select(AcademicGroupPolicy).where(AcademicGroupPolicy.academic_cycle_id==data.cycle_id).with_for_update())
        identity=session.get(Invitation,data.invitation_id)
        team=session.scalar(select(Team).where(Team.id==identity.team_id,Team.academic_cycle_id==data.cycle_id).with_for_update()) if identity else None
        row=session.scalar(select(Invitation).where(Invitation.id==data.invitation_id).with_for_update());person=eligible(session,data)
        if not cycle or not policy or not team or not row or row.status!='pending' or not session.scalar(select(InvitationOutbox.id).where(InvitationOutbox.invitation_id==row.id,InvitationOutbox.status=='smtp_accepted')) or not person or row.student_id!=person.id or row.cycle_id!=cycle.id: raise HTTPException(400,'Invitation could not be decided.')
        if data.action=='accept_invitation':
            member=session.scalar(select(TeamMember.id).where(TeamMember.academic_cycle_id==cycle.id,TeamMember.is_active.is_(True),or_(func.lower(TeamMember.registration_number)==person.registration_number.lower(),func.lower(TeamMember.university_email)==person.university_email.lower())))
            count=session.scalar(select(func.count()).select_from(TeamMember).where(TeamMember.team_id==team.id,TeamMember.is_active.is_(True)))
            if member or count>=policy.max_group_size: raise HTTPException(400,'Invitation could not be decided.')
        context=get_context(session,request);now=utc_now()
        consumed=session.execute(update(AnonymousIdentityProof).where(AnonymousIdentityProof.token_hash==hash_session_token(data.proof),AnonymousIdentityProof.context_id==context.id,AnonymousIdentityProof.student_id==person.id,AnonymousIdentityProof.cycle_id==cycle.id,AnonymousIdentityProof.purpose=='invitation',AnonymousIdentityProof.action==data.action,AnonymousIdentityProof.target_team_id==team.id,AnonymousIdentityProof.target_invitation_id==row.id,AnonymousIdentityProof.expires_at>now,AnonymousIdentityProof.consumed_at.is_(None)).values(consumed_at=now).returning(AnonymousIdentityProof.id)).scalar_one_or_none()
        if consumed is None: raise HTTPException(400,'Invitation could not be decided.')
        row.status='accepted' if data.action=='accept_invitation' else 'rejected'
        if row.status=='accepted':
            session.add(TeamMember(team_id=team.id,academic_cycle_id=cycle.id,student_id=person.id,full_name=person.name.strip(),registration_number=person.registration_number.strip().upper(),university_email=person.university_email.strip().lower(),is_creator=False,is_active=True))
            session.flush()
            session.execute(update(Invitation).where(Invitation.student_id == person.id, Invitation.cycle_id == cycle.id, Invitation.status == 'pending', Invitation.id != row.id).values(status='cancelled'))
            from .models import JoinRequest
            session.execute(update(JoinRequest).where(JoinRequest.student_id == person.id, JoinRequest.cycle_id == cycle.id, JoinRequest.status == 'pending').values(status='cancelled'))
            refresh_team_status(session, team)
            session.add(Module2Notification(recipient_user_id=team.shared_user_id, kind='invitation_decided', payload={'team_id': team.id, 'invitation_id': row.id, 'status': row.status}))
        session.add(InvitationAudit(invitation_id=row.id,actor_student_id=person.id,action=row.status));session.commit();return {'id':row.id,'status':row.status}
    except HTTPException: session.rollback();raise
    except Exception: session.rollback();raise HTTPException(500,'Invitation could not be decided.') from None

@router.get('/team/{team_id}')
def list_invitations(team_id:int,actor:User=Depends(get_current_user),session:Session=Depends(get_db)):
    team=session.scalar(select(Team).where(Team.id==team_id,Team.shared_user_id==actor.id))
    if not team: raise HTTPException(403,'Team access is required.')
    session.execute(update(Invitation).where(Invitation.team_id == team.id, Invitation.status == 'pending', Invitation.expires_at.is_not(None), Invitation.expires_at <= utc_now()).values(status='expired'))
    rows=session.execute(select(Invitation,ApprovedStudent,InvitationOutbox).join(ApprovedStudent,ApprovedStudent.id==Invitation.student_id).outerjoin(InvitationOutbox,InvitationOutbox.invitation_id==Invitation.id).where(Invitation.team_id==team.id).order_by(Invitation.id.desc()).limit(100)).all()
    return [{'id':row.id,'status':row.status,'delivery':outbox.status if outbox else 'unknown','student_name':person.name,'registration_number':person.registration_number} for row,person,outbox in rows]
