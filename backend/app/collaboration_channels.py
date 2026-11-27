"""Private assignment-scoped Module 2 collaboration channels."""

import mimetypes
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .auth import SESSION_COOKIE_NAME, get_current_user, require_roles, utc_now, validate_mutating_origin
from .config import settings
from .database import get_db
from .models import (
    AcademicCycle,
    AdminAuditEvent,
    AuthSession,
    CollaborationChannel,
    CollaborationMemberCredential,
    CollaborationMemberSession,
    CollaborationMessage,
    CollaborationParticipant,
    CollaborationPasswordResetRequest,
    Module2Notification,
    SupervisorAssignment,
    SupervisorRequest,
    Team,
    TeamMember,
    User,
    UserRole,
)
from .security import hash_password, hash_session_token, validate_password, verify_password
from .notification_service import notify, notify_admins, team_student_ids
from .group_display import visible_group_name, visible_group_number

router = APIRouter(prefix="/api/v1", tags=["module-2-private-collaboration"])


class MessageWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_text: str = Field(min_length=1, max_length=4000)
    sender_member_id: StrictInt | None = Field(default=None, gt=0)
    message_kind: Literal["TEXT", "DOCUMENT", "MEDIA", "AUDIO", "CONTACT", "POLL", "EVENT", "STICKER", "CATALOGUE", "QUICK_REPLY"] = "TEXT"
    message_payload: dict[str, object] = Field(default_factory=dict)
    attachment_reference: str | None = Field(default=None, max_length=500)

    @field_validator("message_text")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be blank.")
        # Keep indentation and line breaks in scripts/code; trim only for validation.
        return value


class MessageEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_text: str = Field(min_length=1, max_length=4000)

    @field_validator("message_text")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be blank.")
        return value


class ReadWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: StrictInt = Field(gt=0)


class MemberPasswordSetup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_id: StrictInt = Field(gt=0)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def policy(cls, value: str) -> str:
        validate_password(value)
        return value

    @model_validator(mode="after")
    def matching_passwords(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class MemberPasswordVerify(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_id: StrictInt = Field(gt=0)
    password: str = Field(min_length=1, max_length=128)


class MemberPasswordResetRequestWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_id: StrictInt = Field(gt=0)


def _active_channel(session: Session, channel_id: int) -> CollaborationChannel:
    channel = session.get(CollaborationChannel, channel_id)
    if channel is None:
        raise HTTPException(404, "Collaboration channel was not found.")
    return channel


def _browser_auth_session(session: Session, request: Request, actor: User) -> AuthSession:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Authentication required.")
    auth_session = session.scalar(
        select(AuthSession).where(
            AuthSession.user_id == actor.id,
            AuthSession.token_hash == hash_session_token(token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > utc_now(),
        )
    )
    if auth_session is None:
        raise HTTPException(401, "Authentication required.")
    return auth_session


def _identity_member(session: Session, channel: CollaborationChannel, actor: User, member_id: int) -> TeamMember:
    if actor.role != UserRole.STUDENT:
        raise HTTPException(403, "Only a student group member can use a member identity.")
    member = session.scalar(
        select(TeamMember).where(
            TeamMember.id == member_id,
            TeamMember.team_id == channel.team_id,
            TeamMember.is_active.is_(True),
        )
    )
    if member is None:
        raise HTTPException(422, "The selected group member is not active in this group.")
    team = session.get(Team, channel.team_id)
    if team is not None and team.shared_user_id != actor.id:
        own_member = _student_member(session, actor, channel.team_id)
        if own_member is None or own_member.id != member.id:
            raise HTTPException(403, "You can only use your own group-member identity.")
    return member


def _identity_status(session: Session, channel: CollaborationChannel, actor: User, request: Request | None) -> list[dict]:
    if actor.role != UserRole.STUDENT:
        return []
    members = session.scalars(
        select(TeamMember)
        .where(TeamMember.team_id == channel.team_id, TeamMember.is_active.is_(True))
        .order_by(TeamMember.id)
    ).all()
    credentials = {
        credential.team_member_id: credential
        for credential in session.scalars(
            select(CollaborationMemberCredential).where(CollaborationMemberCredential.channel_id == channel.id)
        ).all()
    }
    pending_ids = {
        row.team_member_id
        for row in session.scalars(
            select(CollaborationPasswordResetRequest).where(
                CollaborationPasswordResetRequest.channel_id == channel.id,
                CollaborationPasswordResetRequest.status == "PENDING",
            )
        ).all()
    }
    verified_member_id = None
    if request is not None:
        auth_session = _browser_auth_session(session, request, actor)
        binding = session.scalar(
            select(CollaborationMemberSession).where(
                CollaborationMemberSession.auth_session_id == auth_session.id,
                CollaborationMemberSession.channel_id == channel.id,
                CollaborationMemberSession.revoked_at.is_(None),
                CollaborationMemberSession.expires_at > utc_now(),
            )
        )
        verified_member_id = binding.team_member_id if binding else None
    return [
        {
            "member_id": member.id,
            "name": member.full_name,
            "registration_number": member.registration_number,
            "password_set": member.id in credentials,
            "is_verified": member.id == verified_member_id,
            "reset_requested": member.id in pending_ids,
        }
        for member in members
    ]


def _bind_identity(session: Session, request: Request, actor: User, channel: CollaborationChannel, member: TeamMember) -> None:
    auth_session = _browser_auth_session(session, request, actor)
    now = utc_now()
    binding = session.scalar(
        select(CollaborationMemberSession).where(
            CollaborationMemberSession.auth_session_id == auth_session.id,
            CollaborationMemberSession.channel_id == channel.id,
        )
    )
    if binding is None:
        binding = CollaborationMemberSession(
            auth_session_id=auth_session.id,
            channel_id=channel.id,
            team_member_id=member.id,
            verified_at=now,
            expires_at=min(auth_session.expires_at, now + timedelta(hours=8)),
        )
        session.add(binding)
    else:
        binding.team_member_id = member.id
        binding.verified_at = now
        binding.expires_at = min(auth_session.expires_at, now + timedelta(hours=8))
        binding.revoked_at = None


def _student_member(session: Session, actor: User, team_id: int) -> TeamMember | None:
    if actor.role != UserRole.STUDENT:
        return None
    return session.scalar(select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.is_active.is_(True), or_(TeamMember.registration_number == actor.registration_number, TeamMember.university_email == actor.email)))


def _authorize(session: Session, channel: CollaborationChannel, actor: User, *, write: bool = False) -> None:
    team = session.get(Team, channel.team_id)
    assignment = session.scalar(select(SupervisorAssignment).where(
        SupervisorAssignment.id == channel.assignment_id,
        SupervisorAssignment.team_id == channel.team_id,
        SupervisorAssignment.supervisor_id == channel.supervisor_id,
        SupervisorAssignment.ended_at.is_(None),
    ))
    # Active assignment (admin-assigned or request-accepted) is enough to open the channel.
    if channel.status != "ACTIVE" or team is None or team.status == "dissolved" or assignment is None:
        raise HTTPException(403, "Collaboration channel will be available after a supervisor is assigned.")
    if actor.role == UserRole.STUDENT:
        if team.shared_user_id != actor.id and _student_member(session, actor, team.id) is None:
            raise HTTPException(403, "This collaboration channel is not available to your group.")
    elif actor.role in (UserRole.SUPERVISOR, UserRole.COORDINATOR):
        assignment = session.scalar(select(SupervisorAssignment).where(SupervisorAssignment.id == channel.assignment_id, SupervisorAssignment.team_id == channel.team_id, SupervisorAssignment.supervisor_id == actor.id, SupervisorAssignment.ended_at.is_(None)))
        if assignment is None:
            raise HTTPException(403, "This collaboration channel is not assigned to you.")
    else:
        raise HTTPException(403, "Collaboration channel access is restricted to students and supervisors.")
    if write and channel.status != "ACTIVE":
        raise HTTPException(409, "Archived collaboration channels cannot receive new messages.")


def _accepted_request(session: Session, team_id: int, supervisor_id: int, cycle_id: int) -> SupervisorRequest | None:
    return session.scalar(select(SupervisorRequest).where(SupervisorRequest.team_id == team_id, SupervisorRequest.supervisor_id == supervisor_id, SupervisorRequest.academic_cycle_id == cycle_id, SupervisorRequest.status == "ACCEPTED").order_by(SupervisorRequest.id.desc()))


def ensure_collaboration_channel(session: Session, assignment: SupervisorAssignment, team: Team) -> CollaborationChannel:
    existing = session.scalar(select(CollaborationChannel).where(CollaborationChannel.assignment_id == assignment.id, CollaborationChannel.status == "ACTIVE"))
    if existing is not None:
        return existing
    cycle = session.get(AcademicCycle, assignment.academic_cycle_id)
    year = assignment.academic_year or (cycle.academic_year if cycle else None)
    term = assignment.session or (cycle.session if cycle else None)
    if cycle is None or year is None or not term:
        raise HTTPException(422, "The assigned academic cycle must have a year and session.")
    # A changed assignment archives the previous conversation but never merges it.
    previous = session.scalars(select(CollaborationChannel).where(CollaborationChannel.team_id == team.id, CollaborationChannel.status == "ACTIVE")).all()
    for channel in previous:
        channel.status = "ARCHIVED"
    channel = CollaborationChannel(team_id=team.id, supervisor_id=assignment.supervisor_id, academic_year=year, session=term, assignment_id=assignment.id, status="ACTIVE")
    session.add(channel); session.flush()
    members = session.scalars(select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True)).order_by(TeamMember.id)).all()
    for member in members:
        user = session.scalar(select(User).where(User.registration_number == member.registration_number, User.email == member.university_email, User.role == UserRole.STUDENT))
        session.add(CollaborationParticipant(channel_id=channel.id, user_id=user.id if user else None, team_member_id=member.id, participant_role="STUDENT", is_active=True))
    session.add(CollaborationParticipant(channel_id=channel.id, user_id=assignment.supervisor_id, participant_role="SUPERVISOR", is_active=True))
    return channel


def ensure_channels_for_actor(session: Session, actor: User) -> None:
    """Create missing channels for active assignments (admin-assigned counts as accepted)."""
    if actor.role == UserRole.STUDENT:
        membership = select(TeamMember.id).where(TeamMember.team_id == Team.id, TeamMember.is_active.is_(True), or_(TeamMember.registration_number == actor.registration_number, TeamMember.university_email == actor.email)).exists()
        teams = session.scalars(select(Team).where(Team.status != "dissolved", or_(Team.shared_user_id == actor.id, membership))).all()
        for team in teams:
            assignment = session.scalar(select(SupervisorAssignment).where(SupervisorAssignment.team_id == team.id, SupervisorAssignment.ended_at.is_(None)).order_by(SupervisorAssignment.id.desc()))
            if assignment is None:
                continue
            try:
                ensure_collaboration_channel(session, assignment, team)
            except HTTPException:
                continue
        session.commit()
        return
    if actor.role in (UserRole.SUPERVISOR, UserRole.COORDINATOR):
        rows = session.scalars(select(SupervisorAssignment).where(SupervisorAssignment.supervisor_id == actor.id, SupervisorAssignment.ended_at.is_(None))).all()
        for assignment in rows:
            team = session.get(Team, assignment.team_id)
            if team is None or team.status == "dissolved":
                continue
            try:
                ensure_collaboration_channel(session, assignment, team)
            except HTTPException:
                continue
        session.commit()


def _channel_out(session: Session, channel: CollaborationChannel, actor: User) -> dict:
    team = session.get(Team, channel.team_id)
    cycle = session.get(AcademicCycle, team.academic_cycle_id) if team else None
    members = session.scalars(select(TeamMember).where(TeamMember.team_id == channel.team_id, TeamMember.is_active.is_(True)).order_by(TeamMember.id)).all()
    supervisor = session.get(User, channel.supervisor_id)
    request = _accepted_request(session, channel.team_id, channel.supervisor_id, team.academic_cycle_id) if team else None
    last_read = session.scalar(select(CollaborationParticipant.last_read_message_id).where(CollaborationParticipant.channel_id == channel.id, CollaborationParticipant.user_id == actor.id)) or 0
    unread = session.scalar(select(func.count()).select_from(CollaborationMessage).where(CollaborationMessage.channel_id == channel.id, CollaborationMessage.deleted_at.is_(None), CollaborationMessage.sender_user_id != actor.id, CollaborationMessage.id > last_read)) or 0
    leader = next((member for member in members if member.is_creator), None)
    if team is not None:
        team.group_name = visible_group_name(session, team, cycle)
    return {"id": channel.id, "group_id": channel.team_id, "group_name": team.group_name if team else "Group", "assignment_status": "ACCEPTED", "supervisor_id": channel.supervisor_id, "assignment_id": channel.assignment_id, "academic_year": channel.academic_year, "session": channel.session, "status": channel.status, "project_title": request.title if request else None, "group_leader": {"name": leader.full_name, "registration_number": leader.registration_number} if leader else None, "members": [{"id": member.id, "name": member.full_name, "registration_number": member.registration_number, "email": member.university_email, "is_creator": member.is_creator} for member in members], "supervisor": {"id": supervisor.id, "name": supervisor.full_name, "email": supervisor.email} if supervisor else None, "cycle_name": cycle.display_name if cycle else None, "unread_count": unread, "last_read_message_id": last_read}


def _message_out(session: Session, message: CollaborationMessage) -> dict:
    sender = session.get(User, message.sender_user_id)
    member = session.get(TeamMember, message.sender_team_member_id) if message.sender_team_member_id else None
    sender_name = member.full_name if member else (sender.full_name if sender else "Unknown user")
    return {"id": message.id, "channel_id": message.channel_id, "sender_user_id": message.sender_user_id, "sender_member_id": member.id if member else None, "sender_member_name": member.full_name if member else None, "sender_member_registration_number": member.registration_number if member else None, "sender_name": sender_name, "sender_role": sender.role.value if sender else "UNKNOWN", "message_text": message.message_text, "message_kind": message.message_kind, "message_payload": message.message_payload or {}, "attachment_reference": message.attachment_reference, "created_at": message.created_at, "updated_at": message.updated_at, "deleted_at": message.deleted_at}


def _selected_member(session: Session, channel: CollaborationChannel, actor: User, member_id: int | None) -> TeamMember | None:
    """Resolve the member label for a student message.

    The shared group principal may select any active member of its own team.
    If an individual student principal is used in the future, it can only
    select its own matching member record.
    """
    if actor.role in (UserRole.SUPERVISOR, UserRole.COORDINATOR):
        if member_id is not None:
            raise HTTPException(422, "A supervisor message cannot select a group member.")
        return None
    if actor.role != UserRole.STUDENT:
        raise HTTPException(403, "Student or supervisor identity is required.")
    if member_id is None:
        raise HTTPException(422, "Select the group member sending this message.")
    member = session.scalar(select(TeamMember).where(TeamMember.id == member_id, TeamMember.team_id == channel.team_id, TeamMember.is_active.is_(True)))
    if member is None:
        raise HTTPException(422, "The selected group member is not active in this group.")
    team = session.get(Team, channel.team_id)
    if team is not None and team.shared_user_id != actor.id:
        own_member = _student_member(session, actor, channel.team_id)
        if own_member is None or own_member.id != member.id:
            raise HTTPException(403, "You can only send as your own group-member identity.")
    return member


def _verified_member(session: Session, channel: CollaborationChannel, actor: User, request: Request, member_id: int | None) -> TeamMember | None:
    member = _selected_member(session, channel, actor, member_id)
    if member is None or actor.role in (UserRole.SUPERVISOR, UserRole.COORDINATOR):
        return member
    auth_session = _browser_auth_session(session, request, actor)
    binding = session.scalar(
        select(CollaborationMemberSession).where(
            CollaborationMemberSession.auth_session_id == auth_session.id,
            CollaborationMemberSession.channel_id == channel.id,
            CollaborationMemberSession.team_member_id == member.id,
            CollaborationMemberSession.revoked_at.is_(None),
            CollaborationMemberSession.expires_at > utc_now(),
        )
    )
    if binding is None:
        raise HTTPException(403, "Verify the selected member's collaboration password before sending.")
    return member


FILE_MESSAGE_KINDS = {"DOCUMENT", "MEDIA", "AUDIO", "STICKER"}


def _collaboration_file_path(channel_id: int, stored_name: str) -> Path:
    return settings.document_storage_root / "module-2" / "collaboration" / str(channel_id) / Path(stored_name).name


def _attachment_kind(kind: str, content_type: str | None) -> str:
    normalized = kind.upper()
    if normalized not in FILE_MESSAGE_KINDS:
        raise HTTPException(422, "This action requires a document, media, audio, or sticker file.")
    if normalized == "AUDIO" and not (content_type or "").startswith("audio/"):
        raise HTTPException(422, "Choose an audio file for the Audio action.")
    if normalized in {"MEDIA", "STICKER"} and not (content_type or "").startswith("image/") and not (normalized == "MEDIA" and (content_type or "").startswith("video/")):
        raise HTTPException(422, "Choose an image or video for the media action.")
    return normalized


def _list_channels(session: Session, actor: User) -> list[dict]:
    if actor.role == UserRole.STUDENT:
        membership = select(TeamMember.id).where(TeamMember.team_id == Team.id, TeamMember.is_active.is_(True), or_(TeamMember.registration_number == actor.registration_number, TeamMember.university_email == actor.email)).exists()
        teams = select(Team.id).where(Team.status != "dissolved", or_(Team.shared_user_id == actor.id, membership))
        rows = session.scalars(select(CollaborationChannel).where(CollaborationChannel.team_id.in_(teams), CollaborationChannel.status == "ACTIVE").order_by(CollaborationChannel.updated_at.desc(), CollaborationChannel.id.desc())).all()
    else:
        rows = session.scalars(select(CollaborationChannel).where(CollaborationChannel.supervisor_id == actor.id, CollaborationChannel.status == "ACTIVE").order_by(CollaborationChannel.updated_at.desc(), CollaborationChannel.id.desc())).all()
    result = []
    for row in rows:
        try:
            _authorize(session, row, actor)
        except HTTPException as error:
            if error.status_code == 403:
                continue
            raise
        result.append(_channel_out(session, row, actor))
    return result


@router.get("/student/collaboration/channels/{channel_id}/member-identity")
def member_identity_status(channel_id: int, request: Request, actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    channel = _active_channel(session, channel_id)
    _authorize(session, channel, actor)
    return {"channel_id": channel.id, "members": _identity_status(session, channel, actor, request)}


@router.post("/student/collaboration/channels/{channel_id}/member-identity/setup")
def setup_member_identity(channel_id: int, payload: MemberPasswordSetup, request: Request, actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    channel = _active_channel(session, channel_id)
    _authorize(session, channel, actor, write=True)
    member = _identity_member(session, channel, actor, payload.member_id)
    existing = session.scalar(
        select(CollaborationMemberCredential).where(
            CollaborationMemberCredential.channel_id == channel.id,
            CollaborationMemberCredential.team_member_id == member.id,
        )
    )
    if existing is not None:
        raise HTTPException(409, "This member already has a collaboration password. Verify it instead.")
    session.add(
        CollaborationMemberCredential(
            channel_id=channel.id,
            team_member_id=member.id,
            password_hash=hash_password(payload.password),
        )
    )
    _bind_identity(session, request, actor, channel, member)
    session.commit()
    return {"channel_id": channel.id, "member_id": member.id, "status": "VERIFIED"}


@router.post("/student/collaboration/channels/{channel_id}/member-identity/verify")
def verify_member_identity(channel_id: int, payload: MemberPasswordVerify, request: Request, actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    channel = _active_channel(session, channel_id)
    _authorize(session, channel, actor, write=True)
    member = _identity_member(session, channel, actor, payload.member_id)
    credential = session.scalar(
        select(CollaborationMemberCredential).where(
            CollaborationMemberCredential.channel_id == channel.id,
            CollaborationMemberCredential.team_member_id == member.id,
        )
    )
    if credential is None:
        raise HTTPException(409, "Create this member's collaboration password first.")
    if not verify_password(payload.password, credential.password_hash):
        raise HTTPException(401, "The collaboration password is incorrect.")
    _bind_identity(session, request, actor, channel, member)
    session.commit()
    return {"channel_id": channel.id, "member_id": member.id, "status": "VERIFIED"}


@router.post("/student/collaboration/channels/{channel_id}/member-identity/forgot")
def request_member_identity_reset(channel_id: int, payload: MemberPasswordResetRequestWrite, request: Request, actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    channel = _active_channel(session, channel_id)
    _authorize(session, channel, actor, write=True)
    member = _identity_member(session, channel, actor, payload.member_id)
    pending = session.scalar(
        select(CollaborationPasswordResetRequest).where(
            CollaborationPasswordResetRequest.channel_id == channel.id,
            CollaborationPasswordResetRequest.team_member_id == member.id,
            CollaborationPasswordResetRequest.status == "PENDING",
        )
    )
    team = session.get(Team, channel.team_id)
    cycle = session.get(AcademicCycle, team.academic_cycle_id) if team else None
    if team is not None:
        team.group_name = visible_group_name(session, team, cycle)
    group_label = team.group_name if team else "Group"
    new_request = pending is None
    if new_request:
        session.add(
            CollaborationPasswordResetRequest(
                channel_id=channel.id,
                team_member_id=member.id,
                requested_by_user_id=actor.id,
            )
        )
    if new_request:
        admins = session.scalars(
            select(User).where(User.role == UserRole.ADMIN, User.is_active.is_(True))
        ).all()
        for admin in admins:
            session.add(
                Module2Notification(
                    recipient_user_id=admin.id,
                    kind="COLLABORATION_PASSWORD_RESET_REQUESTED",
                    payload={
                        "title": "Collaboration password reset requested",
                        "message": f"{member.full_name} requested a new collaboration password for {group_label}.",
                        "path": f"/admin/student-groups?cycle_id={team.academic_cycle_id}&group_id={channel.team_id}&member_id={member.id}&focus=collaboration-reset",
                        "focus": "collaboration-reset",
                        "channel_id": channel.id,
                        "group_id": channel.team_id,
                        "member_id": member.id,
                        "member_name": member.full_name,
                        "registration_number": member.registration_number,
                        "cycle_id": team.academic_cycle_id if team else None,
                        "cycle_name": cycle.display_name if cycle else None,
                    },
                )
            )
    session.commit()
    return {"channel_id": channel.id, "member_id": member.id, "status": "PENDING", "message": "The reset request was sent to an administrator."}


def _admin_channel(session: Session, group_id: int, cycle_id: int) -> tuple[Team, CollaborationChannel | None]:
    team = session.scalar(select(Team).where(Team.id == group_id, Team.academic_cycle_id == cycle_id))
    if team is None:
        raise HTTPException(404, "The student group was not found in this cycle.")
    channel = session.scalar(
        select(CollaborationChannel)
        .where(CollaborationChannel.team_id == team.id, CollaborationChannel.status == "ACTIVE")
        .order_by(CollaborationChannel.id.desc())
    )
    return team, channel


@router.get("/admin/collaboration-credentials")
def admin_collaboration_credentials_list(
    cycle_id: Annotated[int | None, Query(gt=0)] = None,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
):
    """List active collaboration channels and their member credential status."""
    query = select(Team).where(Team.status != "dissolved").order_by(Team.academic_cycle_id, Team.group_number, Team.id)
    if cycle_id is not None:
        query = query.where(Team.academic_cycle_id == cycle_id)
    teams = session.scalars(query).all()
    items = []
    for team in teams:
        channel = session.scalar(
            select(CollaborationChannel)
            .where(CollaborationChannel.team_id == team.id, CollaborationChannel.status == "ACTIVE")
            .order_by(CollaborationChannel.id.desc())
        )
        if channel is None:
            continue
        cycle = session.get(AcademicCycle, team.academic_cycle_id)
        team.group_name = visible_group_name(session, team, cycle)
        group_user = session.get(User, team.shared_user_id)
        members = session.scalars(
            select(TeamMember)
            .where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True))
            .order_by(TeamMember.is_creator.desc(), TeamMember.id)
        ).all()
        credentials = {
            row.team_member_id: row
            for row in session.scalars(
                select(CollaborationMemberCredential).where(CollaborationMemberCredential.channel_id == channel.id)
            ).all()
        }
        pending = {
            row.team_member_id: row
            for row in session.scalars(
                select(CollaborationPasswordResetRequest).where(
                    CollaborationPasswordResetRequest.channel_id == channel.id,
                    CollaborationPasswordResetRequest.status == "PENDING",
                )
            ).all()
        }
        items.append(
            {
                "group_id": team.id,
                "group_name": team.group_name,
                "group_number": visible_group_number(session, team),
                "group_email": group_user.email if group_user else None,
                "shared_user_id": team.shared_user_id,
                "cycle_id": team.academic_cycle_id,
                "cycle_name": cycle.display_name if cycle else None,
                "channel_id": channel.id,
                "channel_status": channel.status,
                "members": [
                    {
                        "member_id": member.id,
                        "name": member.full_name,
                        "registration_number": member.registration_number,
                        "password_set": member.id in credentials,
                        "reset_requested": member.id in pending,
                        "requested_at": pending[member.id].requested_at if member.id in pending else None,
                    }
                    for member in members
                ],
            }
        )
    return {"items": items}


@router.get("/admin/student-groups/{group_id}/collaboration-credentials")
def admin_collaboration_credentials(group_id: int, cycle_id: Annotated[int, Query(gt=0)], actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    team, channel = _admin_channel(session, group_id, cycle_id)
    members = session.scalars(
        select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True)).order_by(TeamMember.id)
    ).all()
    credentials = {
        row.team_member_id: row
        for row in session.scalars(
            select(CollaborationMemberCredential).where(CollaborationMemberCredential.channel_id == channel.id) if channel else select(CollaborationMemberCredential).where(CollaborationMemberCredential.id == -1)
        ).all()
    }
    pending_ids = {
        row.team_member_id
        for row in session.scalars(
            select(CollaborationPasswordResetRequest).where(
                CollaborationPasswordResetRequest.channel_id == channel.id,
                CollaborationPasswordResetRequest.status == "PENDING",
            ) if channel else select(CollaborationPasswordResetRequest).where(CollaborationPasswordResetRequest.id == -1)
        ).all()
    }
    return {
        "group_id": team.id,
        "channel_id": channel.id if channel else None,
        "channel_status": channel.status if channel else None,
        "members": [
            {
                "member_id": member.id,
                "name": member.full_name,
                "registration_number": member.registration_number,
                "password_set": member.id in credentials,
                "reset_requested": member.id in pending_ids,
            }
            for member in members
        ],
    }


@router.post("/admin/student-groups/{group_id}/collaboration-credentials/{member_id}/reset")
def admin_reset_collaboration_credential(group_id: int, member_id: int, cycle_id: Annotated[int, Query(gt=0)], request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    team, channel = _admin_channel(session, group_id, cycle_id)
    if channel is None:
        raise HTTPException(409, "The collaboration channel is created after a supervisor is assigned.")
    member = session.scalar(
        select(TeamMember).where(
            TeamMember.id == member_id,
            TeamMember.team_id == team.id,
            TeamMember.is_active.is_(True),
        )
    )
    if member is None:
        raise HTTPException(404, "The active group member was not found.")
    credential = session.scalar(
        select(CollaborationMemberCredential).where(
            CollaborationMemberCredential.channel_id == channel.id,
            CollaborationMemberCredential.team_member_id == member.id,
        )
    )
    if credential is not None:
        session.delete(credential)
    for binding in session.scalars(
        select(CollaborationMemberSession).where(
            CollaborationMemberSession.channel_id == channel.id,
            CollaborationMemberSession.team_member_id == member.id,
            CollaborationMemberSession.revoked_at.is_(None),
        )
    ).all():
        binding.revoked_at = utc_now()
    pending = session.scalar(
        select(CollaborationPasswordResetRequest).where(
            CollaborationPasswordResetRequest.channel_id == channel.id,
            CollaborationPasswordResetRequest.team_member_id == member.id,
            CollaborationPasswordResetRequest.status == "PENDING",
        )
    )
    if pending is not None:
        pending.status = "RESOLVED"
        pending.resolved_at = utc_now()
        pending.resolved_by_user_id = actor.id
    team.group_name = visible_group_name(session, team)
    group_label = team.group_name
    session.add(
        Module2Notification(
            recipient_user_id=team.shared_user_id,
            kind="COLLABORATION_PASSWORD_RESET_RESOLVED",
            payload={
                "title": "Collaboration password reset approved",
                "message": f"An administrator cleared the collaboration password for {member.full_name} in {group_label}. Open the collaboration channel and create a new password.",
                "path": f"/student/collaboration?focus=collaboration-password&member_id={member.id}",
                "focus": "collaboration-password",
                "channel_id": channel.id,
                "group_id": team.id,
                "member_id": member.id,
                "member_name": member.full_name,
                "registration_number": member.registration_number,
                "cycle_id": team.academic_cycle_id,
            },
        )
    )
    session.add(
        AdminAuditEvent(
            actor_id=actor.id,
            affected_user_id=None,
            target_type="COLLABORATION_MEMBER",
            target_id=member.id,
            action="collaboration_member_password_revoked",
            changed_values={"channel_id": channel.id, "team_member_id": member.id, "password_removed": True},
        )
    )
    session.commit()
    return {"group_id": team.id, "channel_id": channel.id, "member_id": member.id, "member_name": member.full_name, "password_removed": True, "status": "RESET"}


@router.get("/student/collaboration/channels")
def student_channels(actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    ensure_channels_for_actor(session, actor)
    return _list_channels(session, actor)


@router.get("/supervisor/collaboration/channels")
def supervisor_channels(actor: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.COORDINATOR)), session: Session = Depends(get_db)):
    ensure_channels_for_actor(session, actor)
    return _list_channels(session, actor)


@router.get("/student/collaboration/channels/{channel_id}")
@router.get("/supervisor/collaboration/channels/{channel_id}")
def collaboration_channel(channel_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    channel = _active_channel(session, channel_id); _authorize(session, channel, actor)
    return _channel_out(session, channel, actor)


@router.get("/student/collaboration/channels/{channel_id}/messages")
@router.get("/supervisor/collaboration/channels/{channel_id}/messages")
def collaboration_messages(channel_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db), before_id: Annotated[int | None, Query(gt=0)] = None, limit: Annotated[int | None, Query(ge=1, le=200)] = None):
    channel = _active_channel(session, channel_id); _authorize(session, channel, actor)
    statement = select(CollaborationMessage).where(CollaborationMessage.channel_id == channel.id, CollaborationMessage.deleted_at.is_(None))
    if before_id is not None:
        statement = statement.where(CollaborationMessage.id < before_id)
    statement = statement.order_by(CollaborationMessage.id.desc())
    if limit is not None:
        statement = statement.limit(limit)
    rows = session.scalars(statement).all()
    return [_message_out(session, row) for row in reversed(rows)]


@router.post("/student/collaboration/channels/{channel_id}/messages", status_code=201)
@router.post("/supervisor/collaboration/channels/{channel_id}/messages", status_code=201)
def send_collaboration_message(channel_id: int, payload: MessageWrite, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    channel = _active_channel(session, channel_id); _authorize(session, channel, actor, write=True)
    member = _verified_member(session, channel, actor, request, payload.sender_member_id)
    message = CollaborationMessage(channel_id=channel.id, sender_user_id=actor.id, sender_team_member_id=member.id if member else None, message_text=payload.message_text, message_kind=payload.message_kind, message_payload=payload.message_payload, attachment_reference=payload.attachment_reference)
    session.add(message); session.flush()
    team = session.get(Team, channel.team_id)
    if team is not None:
        team.group_name = visible_group_name(session, team)
    group_label = team.group_name if team else "Group"
    sender_label = member.full_name if member else actor.full_name
    message_preview = payload.message_text.strip() or ("Shared an attachment." if payload.attachment_reference else "Sent a collaboration message.")
    common = {"channel_id": channel.id, "group_id": channel.team_id, "message_id": message.id, "sender_id": actor.id}
    notify(
        session,
        team_student_ids(session, channel.team_id),
        kind="COLLABORATION_MESSAGE_RECEIVED",
        title=f"New collaboration message · {group_label}",
        message=f"{sender_label}: {message_preview}",
        path="/student/collaboration",
        exclude={actor.id},
        **common,
    )
    notify(
        session,
        {channel.supervisor_id},
        kind="COLLABORATION_MESSAGE_RECEIVED",
        title=f"New collaboration message · {group_label}",
        message=f"{sender_label}: {message_preview}",
        path=f"/supervisor/groups/{channel.team_id}?tab=discussion",
        exclude={actor.id},
        **common,
    )
    notify_admins(
        session,
        kind="COLLABORATION_MESSAGE_RECEIVED",
        title=f"Collaboration activity · {group_label}",
        message=f"{sender_label} posted in {group_label}: {message_preview}",
        path=f"/admin/student-groups?cycle_id={team.academic_cycle_id if team else ''}&group_id={channel.team_id}",
        exclude={actor.id},
        **common,
    )
    channel.updated_at = func.now(); session.commit(); session.refresh(message)
    return _message_out(session, message)


def _owned_message(session: Session, channel: CollaborationChannel, message_id: int, actor: User) -> CollaborationMessage:
    message = session.scalar(select(CollaborationMessage).where(CollaborationMessage.id == message_id, CollaborationMessage.channel_id == channel.id, CollaborationMessage.deleted_at.is_(None)))
    if message is None:
        raise HTTPException(404, "Message was not found in this channel.")
    if message.sender_user_id != actor.id:
        raise HTTPException(403, "You can only change your own messages.")
    return message


@router.patch("/student/collaboration/channels/{channel_id}/messages/{message_id}")
@router.patch("/supervisor/collaboration/channels/{channel_id}/messages/{message_id}")
def edit_collaboration_message(channel_id: int, message_id: int, payload: MessageEdit, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    channel = _active_channel(session, channel_id); _authorize(session, channel, actor, write=True)
    message = _owned_message(session, channel, message_id, actor)
    message.message_text = payload.message_text
    channel.updated_at = func.now()
    session.commit(); session.refresh(message)
    return _message_out(session, message)


@router.delete("/student/collaboration/channels/{channel_id}/messages/{message_id}")
@router.delete("/supervisor/collaboration/channels/{channel_id}/messages/{message_id}")
def delete_collaboration_message(channel_id: int, message_id: int, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    channel = _active_channel(session, channel_id); _authorize(session, channel, actor, write=True)
    message = _owned_message(session, channel, message_id, actor)
    message.deleted_at = utc_now()
    channel.updated_at = func.now()
    session.commit()
    return {"id": message.id, "deleted_at": message.deleted_at}


@router.post("/student/collaboration/channels/{channel_id}/files", status_code=201)
@router.post("/supervisor/collaboration/channels/{channel_id}/files", status_code=201)
async def upload_collaboration_file(
    channel_id: int,
    request: Request,
    upload: UploadFile = File(...),
    message_kind: str = Form("DOCUMENT"),
    caption: str = Form(""),
    sender_member_id: int | None = Form(None),
    actor: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    validate_mutating_origin(request)
    channel = _active_channel(session, channel_id); _authorize(session, channel, actor, write=True)
    member = _verified_member(session, channel, actor, request, sender_member_id)
    kind = _attachment_kind(message_kind, upload.content_type)
    data = await upload.read()
    if not data or len(data) > 25 * 1024 * 1024:
        raise HTTPException(422, "The shared file must be non-empty and 25 MiB or smaller.")
    original = Path(upload.filename or "shared-file").name[:180]
    stored = f"{uuid4().hex}-{original}"
    path = _collaboration_file_path(channel.id, stored)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_bytes(data)
        message = CollaborationMessage(
            channel_id=channel.id,
            sender_user_id=actor.id,
            sender_team_member_id=member.id if member else None,
            message_text=caption.strip() or original,
            message_kind=kind,
            message_payload={"name": original, "mime_type": upload.content_type or "application/octet-stream", "size": len(data)},
            attachment_reference=f"/api/v1/collaboration/channels/{channel.id}/files/{stored}",
        )
        session.add(message); session.flush()
        team = session.get(Team, channel.team_id)
        if team is not None:
            team.group_name = visible_group_name(session, team)
        group_label = team.group_name if team else "Group"
        sender_label = member.full_name if member else actor.full_name
        common = {"channel_id": channel.id, "group_id": channel.team_id, "message_id": message.id, "sender_id": actor.id}
        notify(
            session,
            team_student_ids(session, channel.team_id),
            kind="COLLABORATION_FILE_RECEIVED",
            title=f"New collaboration file · {group_label}",
            message=f"{sender_label} shared {original} in {group_label}.",
            path="/student/collaboration",
            exclude={actor.id},
            **common,
        )
        notify(
            session,
            {channel.supervisor_id},
            kind="COLLABORATION_FILE_RECEIVED",
            title=f"New collaboration file · {group_label}",
            message=f"{sender_label} shared {original} in {group_label}.",
            path=f"/supervisor/groups/{channel.team_id}?tab=discussion",
            exclude={actor.id},
            **common,
        )
        notify_admins(
            session,
            kind="COLLABORATION_FILE_RECEIVED",
            title=f"Collaboration file activity · {group_label}",
            message=f"{sender_label} shared {original} in {group_label}.",
            path=f"/admin/student-groups?cycle_id={team.academic_cycle_id if team else ''}&group_id={channel.team_id}",
            exclude={actor.id},
            **common,
        )
        channel.updated_at = func.now(); session.commit(); session.refresh(message)
        return _message_out(session, message)
    except HTTPException:
        session.rollback()
        path.unlink(missing_ok=True)
        raise
    except Exception as error:
        session.rollback()
        path.unlink(missing_ok=True)
        raise HTTPException(500, "The shared file could not be saved.") from error


@router.get("/collaboration/channels/{channel_id}/files/{stored_name}")
def download_collaboration_file(channel_id: int, stored_name: str, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    channel = _active_channel(session, channel_id); _authorize(session, channel, actor)
    path = _collaboration_file_path(channel.id, stored_name)
    if not path.is_file():
        raise HTTPException(404, "The shared file was not found.")
    filename = path.name.split("-", 1)[-1].replace('"', "")
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=filename, headers={"Content-Disposition": f'inline; filename="{filename}"'})


@router.post("/student/collaboration/channels/{channel_id}/read")
@router.post("/supervisor/collaboration/channels/{channel_id}/read")
def mark_collaboration_read(channel_id: int, payload: ReadWrite, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    channel = _active_channel(session, channel_id)
    _authorize(session, channel, actor)
    message = session.scalar(select(CollaborationMessage).where(CollaborationMessage.id == payload.message_id, CollaborationMessage.channel_id == channel.id, CollaborationMessage.deleted_at.is_(None)))
    if message is None:
        raise HTTPException(404, "Message was not found in this channel.")
    statement = insert(CollaborationParticipant).values(channel_id=channel.id, user_id=actor.id, participant_role=actor.role.value, is_active=True, last_read_message_id=message.id, last_read_at=func.now())
    session.execute(statement.on_conflict_do_update(constraint="uq_collaboration_participant_user", set_={"last_read_message_id": func.greatest(func.coalesce(CollaborationParticipant.last_read_message_id, 0), message.id), "last_read_at": func.now(), "is_active": True}))
    session.commit()
    return {"channel_id": channel.id, "last_read_message_id": session.scalar(select(CollaborationParticipant.last_read_message_id).where(CollaborationParticipant.channel_id == channel.id, CollaborationParticipant.user_id == actor.id))}
