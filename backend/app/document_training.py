"""Document-linked supervisor training and guidance endpoints."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles, validate_mutating_origin, utc_now
from .database import get_db
from .models import (
    DocumentSubmission,
    DocumentTrainingSession,
    DocumentUploadRequirement,
    SupervisorAssignment,
    Team,
    TeamMember,
    User,
    UserRole,
)
from .group_display import visible_group_name
from .notification_service import notify, team_student_ids

router = APIRouter(prefix="/api/v1", tags=["document-training"])
SUPERVISOR_ROLES = (UserRole.SUPERVISOR, UserRole.COORDINATOR)


class TrainingWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=8000)
    scheduled_at: datetime | None = None
    duration_minutes: int = Field(default=60, ge=15, le=480)
    meeting_url: str | None = Field(default=None, max_length=500)
    requirement_id: int | None = Field(default=None, gt=0)
    submission_id: int | None = Field(default=None, gt=0)


class TrainingStatusWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SCHEDULED", "COMPLETED", "CANCELLED"]


def _supervisor_group(session: Session, actor: User, group_id: int) -> Team:
    assignment = session.scalar(
        select(SupervisorAssignment).where(
            SupervisorAssignment.team_id == group_id,
            SupervisorAssignment.supervisor_id == actor.id,
            SupervisorAssignment.ended_at.is_(None),
        )
    )
    team = session.get(Team, group_id) if assignment else None
    if team is None:
        raise HTTPException(404, "Assigned group was not found.")
    return team


def _student_group(session: Session, actor: User) -> Team | None:
    member_match = select(TeamMember.id).where(
        TeamMember.team_id == Team.id,
        TeamMember.academic_cycle_id == Team.academic_cycle_id,
        TeamMember.is_active.is_(True),
        or_(TeamMember.registration_number == actor.registration_number, TeamMember.university_email == actor.email),
    ).exists()
    return session.scalar(select(Team).where(Team.status != "dissolved", or_(Team.shared_user_id == actor.id, member_match)).order_by(Team.id).limit(1))


def _out(session: Session, row: DocumentTrainingSession) -> dict:
    requirement = session.get(DocumentUploadRequirement, row.requirement_id) if row.requirement_id else None
    supervisor = session.get(User, row.supervisor_id)
    return {
        "id": row.id,
        "team_id": row.team_id,
        "supervisor_id": row.supervisor_id,
        "supervisor_name": supervisor.full_name if supervisor else "Supervisor",
        "requirement_id": row.requirement_id,
        "requirement_title": requirement.title if requirement else None,
        "submission_id": row.submission_id,
        "title": row.title,
        "description": row.description,
        "scheduled_at": row.scheduled_at,
        "duration_minutes": row.duration_minutes,
        "meeting_url": row.meeting_url,
        "status": row.status,
        "completed_at": row.completed_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _validate_links(session: Session, team: Team, payload: TrainingWrite) -> int | None:
    if payload.requirement_id is not None:
        requirement = session.get(DocumentUploadRequirement, payload.requirement_id)
        if requirement is None or requirement.academic_cycle_id != team.academic_cycle_id:
            raise HTTPException(422, "The selected document requirement does not belong to this group cycle.")
        if requirement.assigned_group_id not in (None, team.id):
            raise HTTPException(422, "The selected document requirement is assigned to another group.")
    submission_id = payload.submission_id
    if submission_id is not None:
        submission = session.get(DocumentSubmission, submission_id)
        if submission is None or submission.group_id != team.id:
            raise HTTPException(422, "The selected document submission does not belong to this group.")
        if payload.requirement_id is not None and submission.requirement_id != payload.requirement_id:
            raise HTTPException(422, "The submission and document requirement do not match.")
    elif payload.requirement_id is not None:
        submission_id = session.scalar(
            select(DocumentSubmission.id)
            .where(DocumentSubmission.requirement_id == payload.requirement_id, DocumentSubmission.group_id == team.id)
            .order_by(DocumentSubmission.updated_at.desc(), DocumentSubmission.id.desc())
            .limit(1)
        )
    return submission_id


@router.get("/supervisor/groups/{group_id}/document-training")
def list_supervisor_training(group_id: int, actor: User = Depends(require_roles(*SUPERVISOR_ROLES)), session: Session = Depends(get_db)) -> list[dict]:
    _supervisor_group(session, actor, group_id)
    rows = session.scalars(
        select(DocumentTrainingSession)
        .where(DocumentTrainingSession.team_id == group_id)
        .order_by(DocumentTrainingSession.scheduled_at.asc().nulls_last(), DocumentTrainingSession.created_at.desc())
    ).all()
    return [_out(session, row) for row in rows]


@router.post("/supervisor/groups/{group_id}/document-training", status_code=201)
def create_training(group_id: int, payload: TrainingWrite, request: Request, actor: User = Depends(require_roles(*SUPERVISOR_ROLES)), session: Session = Depends(get_db)) -> dict:
    validate_mutating_origin(request)
    team = _supervisor_group(session, actor, group_id)
    submission_id = _validate_links(session, team, payload)
    row = DocumentTrainingSession(
        team_id=team.id,
        supervisor_id=actor.id,
        requirement_id=payload.requirement_id,
        submission_id=submission_id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        scheduled_at=_normalize_datetime(payload.scheduled_at),
        duration_minutes=payload.duration_minutes,
        meeting_url=payload.meeting_url.strip() if payload.meeting_url else None,
    )
    session.add(row)
    session.flush()
    notify(
        session,
        team_student_ids(session, team.id),
        kind="DOCUMENT_TRAINING_CREATED",
        title="New document training session",
        message=f"{actor.full_name} scheduled '{row.title}' for {visible_group_name(session, team)}.",
        path="/student/documents",
        team_id=team.id,
        training_id=row.id,
        requirement_id=row.requirement_id,
    )
    session.commit()
    session.refresh(row)
    return _out(session, row)


@router.patch("/supervisor/document-training/{training_id}")
def update_training(training_id: int, payload: TrainingStatusWrite, request: Request, actor: User = Depends(require_roles(*SUPERVISOR_ROLES)), session: Session = Depends(get_db)) -> dict:
    validate_mutating_origin(request)
    row = session.get(DocumentTrainingSession, training_id)
    if row is None:
        raise HTTPException(404, "Training session was not found.")
    _supervisor_group(session, actor, row.team_id)
    row.status = payload.status
    row.completed_at = utc_now() if payload.status == "COMPLETED" else None
    session.commit()
    session.refresh(row)
    return _out(session, row)


@router.get("/student/group/document-training")
def student_training(actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)) -> list[dict]:
    team = _student_group(session, actor)
    if team is None:
        return []
    rows = session.scalars(
        select(DocumentTrainingSession)
        .where(DocumentTrainingSession.team_id == team.id, DocumentTrainingSession.status != "CANCELLED")
        .order_by(DocumentTrainingSession.scheduled_at.asc().nulls_last(), DocumentTrainingSession.created_at.desc())
    ).all()
    return [_out(session, row) for row in rows]
