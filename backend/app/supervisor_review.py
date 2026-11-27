"""Module 6: assigned-supervisor proposal review workflow.

This router owns supervisor-authored feedback, formal revision requests,
revision-specific discussions, evidence-based AI assessments, and the final
human decision.  It deliberately reuses Module 3's immutable proposal
submission versions instead of creating a second document store.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from .ai_provider import run_ai_json
from .auth import get_current_user, require_roles, utc_now, validate_mutating_origin
from .database import get_db
from .models import (
    ProposalComplianceSubmission,
    ProposalRevisionAssessment,
    ProposalRevisionDecision,
    ProposalRevisionMessage,
    ProposalRevisionRequest,
    ProposalReviewFeedback,
    ProposalReviewAnnotation,
    SupervisorAssignment,
    Team,
    TeamMember,
    User,
    UserRole,
)
from .notification_service import notify, notify_team_students, notify_team_supervisors
from .group_display import visible_group_name, visible_group_number


router = APIRouter(prefix="/api/v1/supervisor-review", tags=["module-6-supervisor-review"])
SUPERVISOR_ROLES = (UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.COORDINATOR, UserRole.PLATFORM_ADMIN)
ACTIVE_REVISION_STATUSES = {
    "OPEN",
    "IN_PROGRESS",
    "SUBMITTED_FOR_REVIEW",
    "AI_ASSESSMENT_PENDING",
    "AWAITING_SUPERVISOR_VERIFICATION",
    "REOPENED",
    "CHANGES_REQUIRED",
}


class FeedbackWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: int = Field(gt=0)
    feedback_level: Literal["PARAGRAPH", "SECTION", "MODULE", "FULL_PROPOSAL"] = "FULL_PROPOSAL"
    feedback_type: Literal["GENERAL_COMMENT", "EDITING_SUGGESTION", "FORMAL_REVISION", "CLARIFICATION_REQUEST"] = "GENERAL_COMMENT"
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=12000)
    suggested_text: str | None = Field(default=None, max_length=12000)
    selected_text: str | None = Field(default=None, max_length=12000)
    location: dict[str, Any] = Field(default_factory=dict)
    publish: bool = True


class AnnotationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: int = Field(gt=0)
    annotation_type: Literal["HIGHLIGHT", "UNDERLINE", "STRIKETHROUGH", "PEN", "RECTANGLE", "CIRCLE", "ARROW", "TEXT_BOX", "STICKY_NOTE", "EDITING_SUGGESTION", "REVISION_REQUEST"]
    page_number: int = Field(gt=0)
    geometry: dict[str, Any] = Field(default_factory=dict)
    drawing: dict[str, Any] = Field(default_factory=dict)
    selected_text: str | None = Field(default=None, max_length=12000)
    content: str | None = Field(default=None, max_length=12000)
    suggested_text: str | None = Field(default=None, max_length=12000)
    color: str = Field(default="#F5C542", pattern=r"^#[0-9A-Fa-f]{6}$")
    stroke_width: float = Field(default=2, ge=1, le=16)
    publication_status: Literal["DRAFT", "PUBLISHED"] = "DRAFT"
    feedback_id: int | None = Field(default=None, gt=0)
    revision_request_id: int | None = Field(default=None, gt=0)


class RevisionRequestWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_submission_id: int | None = Field(default=None, gt=0)
    feedback_id: int | None = Field(default=None, gt=0)
    target_level: Literal["PARAGRAPH", "SECTION", "MODULE", "FULL_PROPOSAL"] = "FULL_PROPOSAL"
    target_locator: dict[str, Any] = Field(default_factory=dict)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=12000)
    expected_outcome: str | None = Field(default=None, max_length=12000)
    priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    due_at: datetime | None = None


class RevisionMessageWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=12000)


class RevisionSubmissionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: int = Field(gt=0)
    explanation: str = Field(min_length=1, max_length=12000)


class RevisionDecisionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["ACCEPTED", "CHANGES_REQUIRED", "WITHDRAWN", "REOPENED"]
    reason: str | None = Field(default=None, max_length=12000)
    classification: Literal["RESOLVED", "PARTIALLY_RESOLVED", "UNRESOLVED", "MANUAL_VERIFICATION"] | None = None


class AssessmentRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement: str = Field(min_length=1, max_length=1000)
    status: Literal["ADDRESSED", "PARTIALLY_ADDRESSED", "NOT_ADDRESSED", "INSUFFICIENT_EVIDENCE"]
    evidence: str = ""
    location: str | None = None


class AssessmentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: Literal["RESOLVED", "PARTIALLY_RESOLVED", "UNRESOLVED", "MANUAL_VERIFICATION"]
    requirements: list[AssessmentRequirement] = Field(min_length=1, max_length=20)
    explanation: str = Field(min_length=1, max_length=5000)
    manual_verification_required: bool = True


def _error(code: str, message: str, http_status: int = 400) -> HTTPException:
    return HTTPException(http_status, detail={"code": code, "message": message})


def _student_team(session: Session, actor: User) -> Team | None:
    member_match = select(TeamMember.id).where(
        TeamMember.team_id == Team.id,
        TeamMember.academic_cycle_id == Team.academic_cycle_id,
        TeamMember.is_active.is_(True),
        (TeamMember.registration_number == actor.registration_number) | (TeamMember.university_email == actor.email),
    ).exists()
    return session.scalar(
        select(Team).where(
            Team.status != "dissolved",
            (Team.shared_user_id == actor.id) | member_match,
        ).order_by(Team.id).limit(1)
    )


def _supervisor_team_ids(session: Session, actor: User) -> set[int]:
    return set(session.scalars(select(SupervisorAssignment.team_id).where(SupervisorAssignment.supervisor_id == actor.id, SupervisorAssignment.ended_at.is_(None))).all())


def _can_access_team(session: Session, actor: User, team_id: int, *, supervisor_write: bool = False) -> bool:
    if actor.role in {UserRole.ADMIN, UserRole.COORDINATOR, UserRole.PLATFORM_ADMIN}:
        return not supervisor_write or actor.role in {UserRole.ADMIN, UserRole.PLATFORM_ADMIN}
    if actor.role == UserRole.SUPERVISOR:
        return team_id in _supervisor_team_ids(session, actor)
    if actor.role == UserRole.STUDENT:
        team = _student_team(session, actor)
        return team is not None and team.id == team_id and not supervisor_write
    return False


def _require_team_access(session: Session, actor: User, team_id: int, *, supervisor_write: bool = False) -> Team:
    team = session.get(Team, team_id)
    if team is None or not _can_access_team(session, actor, team_id, supervisor_write=supervisor_write):
        raise _error("review_access_denied", "You are not authorized to access this proposal review.", 403)
    return team


def _latest_submission(session: Session, team_id: int, proposal_key: str | None = None) -> ProposalComplianceSubmission | None:
    query = select(ProposalComplianceSubmission).where(
        ProposalComplianceSubmission.team_id == team_id,
        ProposalComplianceSubmission.status.not_in(("DRAFT", "WITHDRAWN")),
    )
    if proposal_key:
        query = query.where(ProposalComplianceSubmission.proposal_key == proposal_key)
    return session.scalar(query.order_by(desc(ProposalComplianceSubmission.version), desc(ProposalComplianceSubmission.id)).limit(1))


def _submission(session: Session, submission_id: int, team_id: int) -> ProposalComplianceSubmission:
    row = session.scalar(select(ProposalComplianceSubmission).where(ProposalComplianceSubmission.id == submission_id, ProposalComplianceSubmission.team_id == team_id))
    if row is None:
        raise _error("submission_not_found", "The proposal version was not found for this group.", 404)
    return row


def _is_overdue(row: ProposalRevisionRequest) -> bool:
    return bool(row.due_at and row.due_at < datetime.now(timezone.utc) and row.status not in {"ACCEPTED", "WITHDRAWN"})


def _feedback_out(session: Session, row: ProposalReviewFeedback) -> dict[str, Any]:
    author = session.get(User, row.author_id)
    return {
        "id": row.id,
        "submission_id": row.submission_id,
        "author": {"id": row.author_id, "name": author.full_name if author else "Supervisor"},
        "feedback_level": row.feedback_level,
        "feedback_type": row.feedback_type,
        "title": row.title,
        "content": row.content,
        "suggested_text": row.suggested_text,
        "selected_text": row.selected_text,
        "location": row.location or {},
        "publication_status": row.publication_status,
        "created_at": row.created_at,
        "published_at": row.published_at,
    }


def _assessment_out(row: ProposalRevisionAssessment | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row.id,
        "revision_request_id": row.revision_request_id,
        "source_submission_id": row.source_submission_id,
        "current_submission_id": row.current_submission_id,
        "classification": row.classification,
        "requirements": row.requirements or [],
        "evidence": row.evidence or [],
        "explanation": row.explanation,
        "manual_verification_required": row.manual_verification_required,
        "status": row.status,
        "source": row.source,
        "provider": row.provider,
        "model": row.model,
        "created_at": row.created_at,
    }


def _request_out(session: Session, row: ProposalRevisionRequest, *, detail: bool = False) -> dict[str, Any]:
    creator = session.get(User, row.created_by_id)
    assessment = session.scalar(select(ProposalRevisionAssessment).where(ProposalRevisionAssessment.revision_request_id == row.id).order_by(desc(ProposalRevisionAssessment.created_at), desc(ProposalRevisionAssessment.id)).limit(1))
    result: dict[str, Any] = {
        "id": row.id,
        "revision_code": row.revision_code,
        "team_id": row.team_id,
        "proposal_key": row.proposal_key,
        "source_submission_id": row.source_submission_id,
        "source_version": row.source_version,
        "latest_submission_id": row.latest_submission_id,
        "created_by": {"id": row.created_by_id, "name": creator.full_name if creator else "Supervisor"},
        "target_level": row.target_level,
        "target_locator": row.target_locator or {},
        "title": row.title,
        "description": row.description,
        "expected_outcome": row.expected_outcome,
        "priority": row.priority,
        "due_at": row.due_at,
        "is_overdue": _is_overdue(row),
        "status": row.status,
        "student_explanation": row.student_explanation,
        "assessment": _assessment_out(assessment),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
    if detail:
        messages = session.scalars(select(ProposalRevisionMessage).where(ProposalRevisionMessage.revision_request_id == row.id).order_by(ProposalRevisionMessage.created_at, ProposalRevisionMessage.id)).all()
        result["messages"] = [{
            "id": item.id,
            "sender_id": item.sender_id,
            "sender_name": session.get(User, item.sender_id).full_name if session.get(User, item.sender_id) else "User",
            "body": item.body,
            "created_at": item.created_at,
            "edited_at": item.edited_at,
        } for item in messages if item.deleted_at is None]
    return result


def _team_out(session: Session, team: Team) -> dict[str, Any]:
    members = session.scalars(select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True)).order_by(TeamMember.id)).all()
    latest = _latest_submission(session, team.id)
    requests = session.scalars(select(ProposalRevisionRequest).where(ProposalRevisionRequest.team_id == team.id).order_by(desc(ProposalRevisionRequest.created_at))).all()
    return {
        "id": team.id,
        "name": visible_group_name(session, team),
        "group_number": visible_group_number(session, team),
        "academic_cycle_id": team.academic_cycle_id,
        "members": [{"id": member.id, "full_name": member.full_name, "registration_number": member.registration_number, "email": member.university_email} for member in members],
        "proposal": None if latest is None else {"id": latest.id, "proposal_key": latest.proposal_key, "title": latest.title, "proposal_type": latest.proposal_type, "version": latest.version, "filename": latest.filename, "created_at": latest.created_at, "text": latest.extracted_text},
        "revision_counts": {
            "total": len(requests),
            "open": sum(1 for item in requests if item.status in ACTIVE_REVISION_STATUSES),
            "awaiting_verification": sum(1 for item in requests if item.status == "AWAITING_SUPERVISOR_VERIFICATION"),
            "accepted": sum(1 for item in requests if item.status == "ACCEPTED"),
        },
        "revision_requests": [_request_out(session, item) for item in requests],
    }


def _require_request(session: Session, actor: User, revision_id: int, *, supervisor_write: bool = False) -> ProposalRevisionRequest:
    row = session.get(ProposalRevisionRequest, revision_id)
    if row is None or not _can_access_team(session, actor, row.team_id, supervisor_write=supervisor_write):
        raise _error("revision_not_found", "The revision request was not found.", 404)
    return row


def _instruction_requirements(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text.strip())
    parts = re.split(r"(?:\n|;|(?<!\d)[.!?](?:\s+|$)|\s+\d+[.)]\s+)", cleaned)
    values = [part.strip(" -•") for part in parts if len(part.strip(" -•")) >= 8]
    return values[:12] or [cleaned[:1000]]


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9]{4,}", text.casefold()) if token not in {"that", "this", "with", "from", "into", "should", "must", "proposal"}}


def _deterministic_assessment(request_row: ProposalRevisionRequest, source: ProposalComplianceSubmission, current: ProposalComplianceSubmission) -> dict[str, Any]:
    requirements = _instruction_requirements(f"{request_row.description}. {request_row.expected_outcome or ''}")
    revised_text = current.extracted_text or ""
    revised_tokens = _tokens(revised_text)
    items: list[dict[str, Any]] = []
    for requirement in requirements:
        required_tokens = _tokens(requirement)
        overlap = len(required_tokens & revised_tokens) / max(1, len(required_tokens))
        if overlap >= 0.65:
            state = "ADDRESSED"
        elif overlap >= 0.25:
            state = "PARTIALLY_ADDRESSED"
        else:
            state = "NOT_ADDRESSED"
        evidence = ""
        if state != "NOT_ADDRESSED":
            for sentence in re.split(r"(?<=[.!?])\s+", revised_text):
                if len(_tokens(sentence) & required_tokens) >= max(1, min(3, len(required_tokens))):
                    evidence = sentence.strip()[:700]
                    break
        items.append({"requirement": requirement, "status": state, "evidence": evidence, "location": "Latest submitted proposal" if evidence else None})
    addressed = sum(item["status"] == "ADDRESSED" for item in items)
    partial = sum(item["status"] == "PARTIALLY_ADDRESSED" for item in items)
    if addressed == len(items):
        classification = "RESOLVED"
    elif addressed or partial:
        classification = "PARTIALLY_RESOLVED"
    else:
        classification = "UNRESOLVED"
    return {
        "classification": classification,
        "requirements": items,
        "evidence": [item for item in items if item["evidence"]],
        "explanation": f"The deterministic review found {addressed} of {len(items)} requested requirement(s) fully addressed and {partial} partially addressed. Supervisor verification is required.",
        "manual_verification_required": True,
    }


def _assessment_prompt(request_row: ProposalRevisionRequest, source: ProposalComplianceSubmission, current: ProposalComplianceSubmission, messages: list[ProposalRevisionMessage]) -> str:
    discussion = "\n".join(f"{message.body[:800]}" for message in messages[-8:]) or "No discussion messages."
    return f"""Evaluate one supervisor revision request. Do not approve it; provide an advisory assessment only.

Revision code: {request_row.revision_code}
Supervisor instruction: {request_row.description}
Expected outcome: {request_row.expected_outcome or 'Not specified'}
Target: {request_row.target_level} {request_row.target_locator or {}}
Previous proposal content:
{(source.extracted_text or '')[:10000]}

Revised proposal content:
{(current.extracted_text or '')[:14000]}

Relevant discussion:
{discussion}

Return the requested JSON schema. Evaluate each concrete requirement in the instruction and cite short supporting evidence from the revised proposal. Use MANUAL_VERIFICATION when evidence is ambiguous."""


def _save_assessment(session: Session, request_row: ProposalRevisionRequest, source: ProposalComplianceSubmission, current: ProposalComplianceSubmission, payload: dict[str, Any], *, source_name: str, provider: str | None, model: str | None, raw_result: dict[str, Any]) -> ProposalRevisionAssessment:
    saved = session.scalar(select(ProposalRevisionAssessment).where(ProposalRevisionAssessment.revision_request_id == request_row.id, ProposalRevisionAssessment.current_submission_id == current.id).with_for_update())
    if saved is None:
        saved = ProposalRevisionAssessment(revision_request_id=request_row.id, source_submission_id=source.id, current_submission_id=current.id)
        session.add(saved)
    saved.classification = payload["classification"]
    saved.requirements = payload["requirements"]
    saved.evidence = payload.get("evidence", [])
    saved.explanation = payload["explanation"]
    saved.manual_verification_required = bool(payload.get("manual_verification_required", True))
    saved.status = "COMPLETED"
    saved.source = source_name
    saved.provider = provider
    saved.model = model
    saved.raw_result = raw_result
    request_row.status = "AWAITING_SUPERVISOR_VERIFICATION"
    request_row.latest_submission_id = current.id
    session.flush()
    return saved


@router.get("/supervisor/groups")
def supervisor_groups(actor: User = Depends(require_roles(*SUPERVISOR_ROLES)), session: Session = Depends(get_db)):
    team_ids = _supervisor_team_ids(session, actor) if actor.role == UserRole.SUPERVISOR else set(session.scalars(select(Team.id).where(Team.status != "dissolved")).all())
    teams = session.scalars(select(Team).where(Team.id.in_(team_ids), Team.status != "dissolved").order_by(Team.academic_cycle_id, Team.group_number, Team.id)).all() if team_ids else []
    return [_team_out(session, team) for team in teams]


@router.get("/student")
def student_review(actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    team = _student_team(session, actor)
    if team is None:
        return {"team": None, "proposal": None, "feedback": [], "revision_requests": []}
    latest = _latest_submission(session, team.id)
    feedback = session.scalars(select(ProposalReviewFeedback).where(ProposalReviewFeedback.team_id == team.id, ProposalReviewFeedback.publication_status == "PUBLISHED").order_by(desc(ProposalReviewFeedback.created_at))).all()
    requests = session.scalars(select(ProposalRevisionRequest).where(ProposalRevisionRequest.team_id == team.id).order_by(desc(ProposalRevisionRequest.created_at))).all()
    return {
        "team": _team_out(session, team),
        "proposal": None if latest is None else {"id": latest.id, "proposal_key": latest.proposal_key, "title": latest.title, "proposal_type": latest.proposal_type, "version": latest.version, "filename": latest.filename},
        "feedback": [_feedback_out(session, item) for item in feedback],
        "revision_requests": [_request_out(session, item) for item in requests],
    }


@router.get("/groups/{team_id}")
def group_review(team_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    team = _require_team_access(session, actor, team_id)
    return _team_out(session, team)


@router.get("/revision-requests")
def list_revision_requests(actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    query = select(ProposalRevisionRequest).order_by(desc(ProposalRevisionRequest.created_at))
    if actor.role == UserRole.STUDENT:
        team = _student_team(session, actor)
        query = query.where(ProposalRevisionRequest.team_id == team.id if team else False)
    elif actor.role == UserRole.SUPERVISOR:
        ids = _supervisor_team_ids(session, actor)
        query = query.where(ProposalRevisionRequest.team_id.in_(ids) if ids else False)
    elif actor.role not in {UserRole.ADMIN, UserRole.COORDINATOR, UserRole.PLATFORM_ADMIN}:
        query = query.where(False)
    return [_request_out(session, row) for row in session.scalars(query).all()]


@router.get("/revision-requests/{revision_id}")
def revision_detail(revision_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    row = _require_request(session, actor, revision_id)
    return _request_out(session, row, detail=True)


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
def create_feedback(payload: FeedbackWrite, request: Request, actor: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.PLATFORM_ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    submission = session.get(ProposalComplianceSubmission, payload.submission_id)
    if submission is None:
        raise _error("submission_not_found", "The proposal version was not found.", 404)
    _require_team_access(session, actor, submission.team_id, supervisor_write=True)
    now = utc_now() if payload.publish else None
    row = ProposalReviewFeedback(team_id=submission.team_id, submission_id=submission.id, author_id=actor.id, feedback_level=payload.feedback_level, feedback_type=payload.feedback_type, title=payload.title.strip(), content=payload.content.strip(), suggested_text=payload.suggested_text.strip() if payload.suggested_text else None, selected_text=payload.selected_text.strip() if payload.selected_text else None, location=payload.location, publication_status="PUBLISHED" if payload.publish else "DRAFT", published_at=now)
    session.add(row)
    session.flush()
    if payload.publish:
        notify_team_students(session, submission.team_id, kind="UPDATE", title="New supervisor proposal feedback", message=f"{actor.full_name} published feedback on {submission.title}.", path="/student/supervisor-review", team_id=submission.team_id, submission_id=submission.id, feedback_id=row.id)
    session.commit()
    session.refresh(row)
    return _feedback_out(session, row)


@router.post("/revision-requests", status_code=status.HTTP_201_CREATED)
def create_revision_request(payload: RevisionRequestWrite, request: Request, actor: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.PLATFORM_ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    feedback = session.get(ProposalReviewFeedback, payload.feedback_id) if payload.feedback_id else None
    if payload.feedback_id and feedback is None:
        raise _error("feedback_not_found", "The feedback item was not found.", 404)
    submission_id = payload.source_submission_id or (feedback.submission_id if feedback else None)
    if submission_id is None:
        raise _error("source_submission_required", "Select the proposal version that contains the requested change.", 422)
    submission = session.get(ProposalComplianceSubmission, submission_id)
    if submission is None or submission.team_id is None:
        raise _error("source_submission_not_found", "The source proposal version was not found.", 404)
    _require_team_access(session, actor, submission.team_id, supervisor_write=True)
    if feedback and feedback.team_id != submission.team_id:
        raise _error("feedback_scope_mismatch", "Feedback and proposal version must belong to the same group.", 422)
    title = payload.title.strip()
    description = payload.description.strip()
    row = ProposalRevisionRequest(revision_code=f"REV-{uuid.uuid4().hex[:10].upper()}", team_id=submission.team_id, proposal_key=submission.proposal_key, source_submission_id=submission.id, source_version=submission.version, created_by_id=actor.id, target_level=payload.target_level, target_locator=payload.target_locator, title=title, description=description, expected_outcome=payload.expected_outcome.strip() if payload.expected_outcome else None, priority=payload.priority, due_at=payload.due_at, status="OPEN")
    session.add(row)
    session.flush()
    notify_team_students(session, submission.team_id, kind="UPDATE", title="New proposal revision request", message=f"{actor.full_name} requested a proposal revision: {title}.", path=f"/student/supervisor-review?revision={row.id}", team_id=submission.team_id, revision_id=row.id, revision_code=row.revision_code)
    session.commit()
    session.refresh(row)
    return _request_out(session, row, detail=True)


@router.post("/revision-requests/{revision_id}/messages", status_code=status.HTTP_201_CREATED)
def create_message(revision_id: int, payload: RevisionMessageWrite, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = _require_request(session, actor, revision_id)
    message = ProposalRevisionMessage(revision_request_id=row.id, sender_id=actor.id, body=payload.body.strip())
    session.add(message)
    if actor.role == UserRole.STUDENT:
        notify_team_supervisors(session, row.team_id, kind="MESSAGE", title=f"New message on {row.revision_code}", message=f"{actor.full_name} sent a message about {row.title}.", path=f"/supervisor/review?revision={row.id}", revision_id=row.id, revision_code=row.revision_code)
    else:
        notify_team_students(session, row.team_id, kind="MESSAGE", title=f"Supervisor replied on {row.revision_code}", message=f"{actor.full_name} replied about {row.title}.", path=f"/student/supervisor-review?revision={row.id}", revision_id=row.id, revision_code=row.revision_code)
    session.commit()
    session.refresh(message)
    return {"id": message.id, "sender_id": actor.id, "sender_name": actor.full_name, "body": message.body, "created_at": message.created_at}


@router.post("/revision-requests/{revision_id}/submit")
def submit_revision(revision_id: int, payload: RevisionSubmissionWrite, request: Request, actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = _require_request(session, actor, revision_id)
    submission = session.get(ProposalComplianceSubmission, payload.submission_id)
    if submission is None or submission.team_id != row.team_id or submission.proposal_key != row.proposal_key or submission.status in {"DRAFT", "WITHDRAWN"} or submission.version <= row.source_version:
        raise _error("invalid_revision_submission", "Select a submitted proposal version newer than the source version for this revision.", 422)
    row.latest_submission_id = submission.id
    row.student_explanation = payload.explanation.strip()
    row.status = "AI_ASSESSMENT_PENDING"
    notify_team_supervisors(session, row.team_id, kind="UPDATE", title="Proposal revision submitted", message=f"{actor.full_name} submitted {submission.title} v{submission.version} for {row.revision_code}.", path=f"/supervisor/review?revision={row.id}", revision_id=row.id, revision_code=row.revision_code)
    session.commit()
    session.refresh(row)
    return _request_out(session, row, detail=True)


@router.post("/revision-requests/{revision_id}/assess")
async def assess_revision(revision_id: int, request: Request, actor: User = Depends(require_roles(*SUPERVISOR_ROLES)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = _require_request(session, actor, revision_id, supervisor_write=True)
    source = session.get(ProposalComplianceSubmission, row.source_submission_id)
    current = session.get(ProposalComplianceSubmission, row.latest_submission_id) if row.latest_submission_id else _latest_submission(session, row.team_id, row.proposal_key)
    if source is None or current is None or current.version <= source.version:
        raise _error("revision_submission_missing", "The student has not submitted a newer proposal version for assessment.", 409)
    messages = session.scalars(select(ProposalRevisionMessage).where(ProposalRevisionMessage.revision_request_id == row.id, ProposalRevisionMessage.deleted_at.is_(None)).order_by(ProposalRevisionMessage.created_at)).all()
    deterministic = _deterministic_assessment(row, source, current)
    ai_result = await run_ai_json(_assessment_prompt(row, source, current, messages), AssessmentPayload, model_kind="proposal", rate_key=f"module6-revision:{actor.id}:{row.id}")
    if ai_result.get("status") == "COMPLETED" and isinstance(ai_result.get("payload"), dict):
        payload = AssessmentPayload.model_validate(ai_result["payload"]).model_dump()
        source_name = "AI"
    else:
        payload = deterministic
        source_name = "DETERMINISTIC_FALLBACK"
    saved = _save_assessment(session, row, source, current, payload, source_name=source_name, provider=ai_result.get("provider"), model=ai_result.get("model"), raw_result=ai_result)
    notify_team_students(session, row.team_id, kind="UPDATE", title="Revision assessment ready", message=f"An assessment is ready for {row.revision_code}. Your supervisor will make the final decision.", path=f"/student/supervisor-review?revision={row.id}", revision_id=row.id, revision_code=row.revision_code)
    session.commit()
    session.refresh(saved)
    return _request_out(session, row, detail=True)


@router.post("/revision-requests/{revision_id}/decision")
def decide_revision(revision_id: int, payload: RevisionDecisionWrite, request: Request, actor: User = Depends(require_roles(*SUPERVISOR_ROLES)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = _require_request(session, actor, revision_id, supervisor_write=True)
    if payload.decision in {"CHANGES_REQUIRED", "WITHDRAWN", "REOPENED"} and not (payload.reason or "").strip():
        raise _error("decision_reason_required", "Provide a reason for this revision decision.", 422)
    if payload.decision == "ACCEPTED":
        row.status = "ACCEPTED"
        row.closed_at = utc_now()
    elif payload.decision == "CHANGES_REQUIRED":
        row.status = "CHANGES_REQUIRED"
        row.closed_at = None
    elif payload.decision == "WITHDRAWN":
        row.status = "WITHDRAWN"
        row.closed_at = utc_now()
    else:
        row.status = "REOPENED"
        row.closed_at = None
        row.last_reopen_reason = payload.reason.strip() if payload.reason else None
    decision = ProposalRevisionDecision(revision_request_id=row.id, actor_id=actor.id, decision=payload.decision, classification=payload.classification, reason=payload.reason.strip() if payload.reason else None)
    session.add(decision)
    notify_team_students(session, row.team_id, kind="UPDATE", title=f"Revision {row.revision_code} updated", message=f"{actor.full_name} marked {row.revision_code} as {row.status.replace('_', ' ').lower()}.", path=f"/student/supervisor-review?revision={row.id}", revision_id=row.id, revision_code=row.revision_code, decision=row.status)
    session.commit()
    session.refresh(row)
    return _request_out(session, row, detail=True)


@router.get("/revision-requests/{revision_id}/history")
def revision_history(revision_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    row = _require_request(session, actor, revision_id)
    decisions = session.scalars(select(ProposalRevisionDecision).where(ProposalRevisionDecision.revision_request_id == row.id).order_by(ProposalRevisionDecision.created_at, ProposalRevisionDecision.id)).all()
    return [{"id": item.id, "decision": item.decision, "classification": item.classification, "reason": item.reason, "actor_id": item.actor_id, "actor_name": session.get(User, item.actor_id).full_name if session.get(User, item.actor_id) else "User", "created_at": item.created_at} for item in decisions]


def _annotation_out(session: Session, row: ProposalReviewAnnotation) -> dict[str, Any]:
    author = session.get(User, row.author_id)
    return {
        "id": row.id,
        "team_id": row.team_id,
        "submission_id": row.submission_id,
        "author_id": row.author_id,
        "author_name": author.full_name if author else "Supervisor",
        "annotation_type": row.annotation_type,
        "page_number": row.page_number,
        "geometry": row.geometry or {},
        "drawing": row.drawing or {},
        "selected_text": row.selected_text,
        "content": row.content,
        "suggested_text": row.suggested_text,
        "color": row.color,
        "stroke_width": row.stroke_width,
        "publication_status": row.publication_status,
        "feedback_id": row.feedback_id,
        "revision_request_id": row.revision_request_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "published_at": row.published_at,
    }


def _annotation_submission(session: Session, actor: User, submission_id: int, *, supervisor_write: bool = False) -> ProposalComplianceSubmission:
    submission = session.get(ProposalComplianceSubmission, submission_id)
    if submission is None:
        raise _error("submission_not_found", "The proposal version was not found.", 404)
    _require_team_access(session, actor, submission.team_id, supervisor_write=supervisor_write)
    return submission


@router.get("/proposals/{submission_id}/annotations")
def list_annotations(submission_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    submission = _annotation_submission(session, actor, submission_id)
    query = select(ProposalReviewAnnotation).where(ProposalReviewAnnotation.submission_id == submission.id).order_by(ProposalReviewAnnotation.page_number, ProposalReviewAnnotation.created_at, ProposalReviewAnnotation.id)
    if actor.role == UserRole.STUDENT:
        query = query.where(ProposalReviewAnnotation.publication_status == "PUBLISHED")
    return [_annotation_out(session, row) for row in session.scalars(query).all()]


@router.post("/proposals/{submission_id}/annotations", status_code=status.HTTP_201_CREATED)
def create_annotation(submission_id: int, payload: AnnotationWrite, request: Request, actor: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.PLATFORM_ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    if payload.submission_id != submission_id:
        raise _error("submission_scope_mismatch", "The annotation does not belong to this proposal version.", 422)
    submission = _annotation_submission(session, actor, submission_id, supervisor_write=True)
    if payload.feedback_id:
        feedback = session.get(ProposalReviewFeedback, payload.feedback_id)
        if feedback is None or feedback.team_id != submission.team_id or feedback.submission_id != submission.id:
            raise _error("feedback_scope_mismatch", "The selected feedback does not belong to this proposal version.", 422)
    if payload.revision_request_id:
        revision = session.get(ProposalRevisionRequest, payload.revision_request_id)
        if revision is None or revision.team_id != submission.team_id or revision.proposal_key != submission.proposal_key:
            raise _error("revision_scope_mismatch", "The revision request does not belong to this proposal.", 422)
    row = ProposalReviewAnnotation(
        team_id=submission.team_id,
        submission_id=submission.id,
        author_id=actor.id,
        annotation_type=payload.annotation_type,
        page_number=payload.page_number,
        geometry=payload.geometry,
        drawing=payload.drawing,
        selected_text=payload.selected_text.strip() if payload.selected_text else None,
        content=payload.content.strip() if payload.content else None,
        suggested_text=payload.suggested_text.strip() if payload.suggested_text else None,
        color=payload.color,
        stroke_width=payload.stroke_width,
        publication_status=payload.publication_status,
        feedback_id=payload.feedback_id,
        revision_request_id=payload.revision_request_id,
        published_at=utc_now() if payload.publication_status == "PUBLISHED" else None,
    )
    session.add(row)
    session.flush()
    if row.publication_status == "PUBLISHED":
        notify_team_students(session, submission.team_id, kind="UPDATE", title="New proposal annotation", message=f"{actor.full_name} published an annotation on {submission.title}.", path=f"/student/supervisor-review?submission={submission.id}&page={row.page_number}", team_id=submission.team_id, submission_id=submission.id, annotation_id=row.id)
    session.commit()
    session.refresh(row)
    return _annotation_out(session, row)


@router.patch("/annotations/{annotation_id}")
def update_annotation(annotation_id: int, payload: AnnotationWrite, request: Request, actor: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.PLATFORM_ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(ProposalReviewAnnotation, annotation_id)
    if row is None:
        raise _error("annotation_not_found", "The annotation was not found.", 404)
    _require_team_access(session, actor, row.team_id, supervisor_write=True)
    if payload.submission_id != row.submission_id:
        raise _error("submission_scope_mismatch", "An annotation cannot be moved to another proposal version.", 422)
    for key in ("annotation_type", "page_number", "geometry", "drawing", "selected_text", "content", "suggested_text", "color", "stroke_width"):
        setattr(row, key, getattr(payload, key))
    if row.publication_status != "PUBLISHED" and payload.publication_status == "PUBLISHED":
        row.published_at = utc_now()
    row.publication_status = payload.publication_status
    session.commit()
    session.refresh(row)
    return _annotation_out(session, row)


@router.post("/annotations/{annotation_id}/publish")
def publish_annotation(annotation_id: int, request: Request, actor: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.PLATFORM_ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(ProposalReviewAnnotation, annotation_id)
    if row is None:
        raise _error("annotation_not_found", "The annotation was not found.", 404)
    _require_team_access(session, actor, row.team_id, supervisor_write=True)
    row.publication_status = "PUBLISHED"
    row.published_at = utc_now()
    row.withdrawn_at = None
    notify_team_students(session, row.team_id, kind="UPDATE", title="New proposal annotation", message=f"{actor.full_name} published feedback on proposal page {row.page_number}.", path=f"/student/supervisor-review?submission={row.submission_id}&page={row.page_number}", team_id=row.team_id, submission_id=row.submission_id, annotation_id=row.id)
    session.commit()
    session.refresh(row)
    return _annotation_out(session, row)


@router.post("/annotations/{annotation_id}/withdraw")
def withdraw_annotation(annotation_id: int, request: Request, actor: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.PLATFORM_ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(ProposalReviewAnnotation, annotation_id)
    if row is None:
        raise _error("annotation_not_found", "The annotation was not found.", 404)
    _require_team_access(session, actor, row.team_id, supervisor_write=True)
    row.publication_status = "WITHDRAWN"
    row.withdrawn_at = utc_now()
    session.commit()
    session.refresh(row)
    return _annotation_out(session, row)
