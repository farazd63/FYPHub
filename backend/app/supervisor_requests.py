"""Cycle-scoped supervisor selection and proposal-request workflow."""

import asyncio
import logging
import os
from datetime import datetime
from io import BytesIO
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles, utc_now, validate_mutating_origin
from .collaboration_channels import ensure_collaboration_channel
from .database import get_db
from .config import settings
from .pdf_extraction import EXTRACTION_RUNTIME, PdfExtractionError, extract_proposal_document
from .models import (
    AcademicCycle,
    SupervisorAssignment,
    SupervisorCapacityPolicy,
    SupervisorRequest,
    SupervisorRequestDocument,
    SupervisorRequestExtractionStatus,
    SupervisorRequestStatus,
    SupervisorRequestStatusHistory,
    SupervisorRequestSubmissionNoteVersion,
    Team,
    TeamMember,
    User,
    UserRole,
)
from .models.proposal_ai_review import ProposalAIReviewRun
from .ai_provider import ProposalProviderPayload, run_ai_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/supervisor-requests")
proposal_router = APIRouter(prefix="/api/v1/proposals")

ACTIVE_REQUEST_STATUSES = (
    SupervisorRequestStatus.DRAFT.value,
    SupervisorRequestStatus.SUBMITTED.value,
    SupervisorRequestStatus.CHANGES_REQUESTED.value,
    SupervisorRequestStatus.ACCEPTED.value,
)
DECISION_STATUSES = (
    SupervisorRequestStatus.SUBMITTED.value,
    SupervisorRequestStatus.CHANGES_REQUESTED.value,
)


class RevisionAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: StrictInt = Field(gt=0)


class DecisionAction(RevisionAction):
    action: str = Field(pattern="^(accept|reject|request_changes)$")
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


REVIEW_SECTIONS = ("problem_statement", "objectives", "scope", "methodology", "abstract_purpose", "expected_outcomes", "proposed_solution")


class ProposalAIReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int | None
    source: Literal["AI", "DETERMINISTIC"]
    status: Literal["PASS", "WARNING", "FAIL"]
    section: str
    evidence: str
    feedback: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    suggestion: str = Field(min_length=1)


class ProposalAIReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_id: int
    proposal_id: str
    status: Literal["COMPLETED", "UNAVAILABLE"]
    provider: str
    model: str
    source: Literal["AI", "DETERMINISTIC_FALLBACK"]
    message: str
    advisory: bool
    findings: list[ProposalAIReviewFinding] = Field(min_length=7, max_length=7)
    timestamp: datetime | None
    error_type: str | None
    latency_ms: float | None
    request_id: str | None
    retry_count: int | None
    fallback_reason: str | None

    @model_validator(mode="after")
    def validate_contract(self):
        if tuple(item.section for item in self.findings) != REVIEW_SECTIONS:
            raise ValueError("proposal review findings must contain the canonical seven sections")
        expected_source = "AI" if self.source == "AI" else "DETERMINISTIC"
        if self.status == "COMPLETED" and self.source != "AI":
            raise ValueError("completed reviews must use source AI")
        if self.status == "UNAVAILABLE" and self.source != "DETERMINISTIC_FALLBACK":
            raise ValueError("unavailable reviews must use deterministic fallback")
        if any(item.source != expected_source for item in self.findings):
            raise ValueError("finding source does not match review source")
        return self


def _normalize_submission_note(value: str | None) -> str | None:
    normalized = value.strip() if value else ""
    return normalized or None


def _reject_text_for_supervisor_selection(request: Request, filename: str | None, content_type: str | None = None) -> None:
    """Keep the legacy supervisor-selection upload contract PDF/DOCX-only.

    The supervisor selection workflow intentionally remains a one-page
    proposal-document workflow with its existing PDF/DOCX contract.
    """
    is_text_filename = (filename or "").casefold().endswith((".txt", ".text", ".md"))
    is_text_content = (content_type or "").casefold() in {"text/plain", "text/markdown"}
    if request.url.path.startswith("/api/v1/supervisor-requests") and (is_text_filename or is_text_content):
        raise PdfExtractionError("invalid_pdf", "Supervisor selection accepts PDF or DOCX documents only.")


def failure(code: str, message: str, http_status: int = status.HTTP_409_CONFLICT) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "message": message})


def _ai_fallback(row: SupervisorRequest, document: SupervisorRequestDocument | None) -> dict[str, object]:
    fields = document.extracted_fields if document is not None and isinstance(document.extracted_fields, dict) else {}
    checks = {
        "problem_statement": (row.problem_statement or fields.get("purpose"), "Add a clear problem statement with context, gap, and impact."),
        "objectives": (row.objectives or fields.get("objectives"), "State specific, measurable objectives."),
        "scope": (row.scope, "Define what is in scope and what is explicitly excluded."),
        "methodology": (row.methodology or fields.get("methodology"), "Describe the method, data, evaluation approach, and validation procedure."),
        "abstract_purpose": (fields.get("purpose"), "Clarify the proposal purpose and expected contribution."),
        "expected_outcomes": (fields.get("expected_outcomes"), "Describe concrete expected outcomes and how they will be evaluated."),
        "proposed_solution": (fields.get("proposed_solution") or fields.get("solution"), "Explain the proposed system features and how they solve the stated problem."),
    }
    findings = []
    for section, (value, suggestion) in checks.items():
        present = bool(value and (not isinstance(value, dict) or value.get("value")))
        findings.append({"section": section, "status": "PASS" if present else "WARNING", "feedback": "Content was detected for this section." if present else "No sufficiently clear content was detected for this section.", "suggestion": "No correction suggested." if present else suggestion, "page": 1 if present else None, "evidence": str(value)[:500] if present else "No evidence was detected.", "confidence": 0.9 if present else 0.65, "source": "DETERMINISTIC"})
    return {"status": "UNAVAILABLE", "source": "DETERMINISTIC_FALLBACK", "message": "AI review unavailable; deterministic section checks are shown.", "provider": "ollama", "model": settings.ollama_fallback_model, "findings": findings, "advisory": True}


def _review_prompt(row: SupervisorRequest, document: SupervisorRequestDocument | None) -> str:
    fields = document.extracted_fields if document is not None and isinstance(document.extracted_fields, dict) else {}
    values = {
        "problem_statement": row.problem_statement or fields.get("problem_statement") or fields.get("problem"),
        "objectives": row.objectives or fields.get("objectives"),
        "scope": row.scope or fields.get("scope"),
        "methodology": row.methodology or fields.get("methodology"),
        "abstract_purpose": fields.get("abstract_purpose") or fields.get("purpose"),
        "expected_outcomes": fields.get("expected_outcomes"),
        "proposed_solution": fields.get("proposed_solution") or fields.get("solution"),
    }
    lines = ["Act as an academic proposal reviewer. Evaluate quality, relevance, completeness, and alignment; do not mark PASS merely because text exists. Use only supplied content, do not invent evidence, and provide concise actionable feedback. Required sections must be reviewed in exact order."]
    for section, value in values.items():
        if isinstance(value, dict): value = value.get("value")
        lines.append(f"{section}: {str(value).strip()[:1800] if value and str(value).strip() else '[MISSING]'}")
    return "\n".join(lines)


def _ai_out(run: ProposalAIReviewRun) -> dict[str, object]:
    result = run.result if isinstance(run.result, dict) else {}
    payload = {"review_id": run.id, "proposal_id": run.proposal_id, "status": result.get("status", run.status), "provider": result.get("provider", run.runtime), "model": result.get("model", run.model) or settings.ollama_proposal_model, "source": result.get("source"), "message": result.get("message", "AI review completed."), "advisory": bool(result.get("advisory", True)), "findings": result.get("findings", []), "timestamp": result.get("timestamp", run.finished_at or run.started_at), "error_type": result.get("error_type"), "latency_ms": result.get("latency_ms"), "request_id": result.get("request_id"), "retry_count": result.get("retry_count"), "fallback_reason": result.get("fallback_reason")}
    response = ProposalAIReviewResponse.model_validate(payload).model_dump(mode="json")
    logger.info("ai_review.response request_id=%s status=%s source=%s finding_count=%s fallback_reason=%s error_type=%s latency_ms=%s sections=%s", response.get("request_id"), response.get("status"), response.get("source"), len(response.get("findings", [])), response.get("fallback_reason"), response.get("error_type"), response.get("latency_ms"), [item.get("section") for item in response.get("findings", [])])
    return response


def _team_for_student(session: Session, actor: User) -> Team | None:
    """Resolve the existing shared group for either its login or an active member."""
    member_match = select(TeamMember.id).where(
        TeamMember.team_id == Team.id,
        TeamMember.academic_cycle_id == Team.academic_cycle_id,
        TeamMember.is_active.is_(True),
        or_(TeamMember.registration_number == actor.registration_number, TeamMember.university_email == actor.email),
    ).exists() if actor.registration_number else None
    conditions = [Team.shared_user_id == actor.id]
    if member_match is not None:
        conditions.append(member_match)
    return session.execute(select(Team).where(or_(*conditions), Team.status != "dissolved").order_by(Team.id)).scalars().first()


def _actor_has_team_access(session: Session, team: Team, actor: User) -> bool:
    if team.shared_user_id == actor.id:
        return True
    if actor.role != UserRole.STUDENT or not actor.registration_number:
        return False
    return session.scalar(select(TeamMember.id).where(
        TeamMember.team_id == team.id,
        TeamMember.academic_cycle_id == team.academic_cycle_id,
        TeamMember.registration_number == actor.registration_number,
        TeamMember.is_active.is_(True),
    ).limit(1)) is not None


def _cycle_for_request(session: Session, cycle_id: int, *, lock: bool = False, require_open: bool = True) -> AcademicCycle:
    statement = select(AcademicCycle).where(AcademicCycle.id == cycle_id)
    if lock:
        statement = statement.with_for_update()
    cycle = session.execute(statement).scalar_one_or_none()
    if cycle is None:
        raise failure("academic_cycle_not_found", "Academic cycle was not found.", status.HTTP_404_NOT_FOUND)
    if cycle.academic_year is None or not cycle.session:
        raise failure("academic_cycle_metadata_missing", "Ask an administrator to configure this academic cycle's year and session before sending a supervisor request.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if require_open and not cycle.registration_open:
        raise failure("academic_cycle_closed", "This academic cycle is not accepting supervisor requests.")
    return cycle


def _lock_capacity(session: Session, supervisor_id: int, cycle_id: int) -> tuple[User, SupervisorCapacityPolicy]:
    supervisor = session.execute(
        select(User).where(User.id == supervisor_id).with_for_update()
    ).scalar_one_or_none()
    if supervisor is None or supervisor.role != UserRole.SUPERVISOR or not supervisor.is_active:
        raise failure("supervisor_ineligible", "The selected supervisor is not active.")
    cycle = session.get(AcademicCycle, cycle_id)
    policy = session.execute(
        select(SupervisorCapacityPolicy)
        .where(
            SupervisorCapacityPolicy.supervisor_id == supervisor_id,
            or_(SupervisorCapacityPolicy.academic_year == cycle.academic_year, SupervisorCapacityPolicy.academic_cycle_id == cycle_id) if cycle and cycle.academic_year is not None else SupervisorCapacityPolicy.academic_cycle_id == cycle_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if policy is None:
        raise failure("capacity_policy_missing", "No capacity policy exists for this supervisor and cycle.")
    return supervisor, policy


def _capacity_used(session: Session, supervisor_id: int, cycle_id: int, *, exclude_request_id: int | None = None) -> int:
    cycle = session.get(AcademicCycle, cycle_id)
    assignment_count = session.scalar(
        select(func.count(SupervisorAssignment.id)).outerjoin(AcademicCycle, AcademicCycle.id == SupervisorAssignment.academic_cycle_id).where(
            SupervisorAssignment.supervisor_id == supervisor_id,
            SupervisorAssignment.ended_at.is_(None),
            (or_(SupervisorAssignment.academic_year == cycle.academic_year, (SupervisorAssignment.academic_year.is_(None)) & (AcademicCycle.academic_year == cycle.academic_year)) if cycle and cycle.academic_year is not None else SupervisorAssignment.academic_cycle_id == cycle_id),
        )
    ) or 0
    individual_request = select(func.count(SupervisorRequest.id)).where(
        SupervisorRequest.supervisor_id == supervisor_id,
        SupervisorRequest.academic_cycle_id.in_(select(AcademicCycle.id).where(AcademicCycle.academic_year == cycle.academic_year)) if cycle and cycle.academic_year is not None else SupervisorRequest.academic_cycle_id == cycle_id,
        SupervisorRequest.status == SupervisorRequestStatus.ACCEPTED.value,
        SupervisorRequest.assignment_id.is_(None),
    )
    if exclude_request_id is not None:
        individual_request = individual_request.where(SupervisorRequest.id != exclude_request_id)
    return int(assignment_count + (session.scalar(individual_request) or 0))


def _ensure_capacity(session: Session, supervisor_id: int, cycle_id: int, policy: SupervisorCapacityPolicy, *, exclude_request_id: int | None = None) -> None:
    if _capacity_used(session, supervisor_id, cycle_id, exclude_request_id=exclude_request_id) >= policy.max_group_capacity:
        raise failure("capacity_full", "Supervisor capacity is full for this cycle.")


def _owner_request(session: Session, request_id: int, actor: User, *, lock: bool = False) -> SupervisorRequest:
    statement = select(SupervisorRequest).where(SupervisorRequest.id == request_id)
    if lock:
        statement = statement.with_for_update()
    row = session.execute(statement).scalar_one_or_none()
    if row is None:
        raise failure("request_not_found", "Supervisor request was not found.", status.HTTP_404_NOT_FOUND)
    if row.requester_user_id == actor.id:
        return row
    team = session.scalar(select(Team).where(Team.id == row.team_id, Team.academic_cycle_id == row.academic_cycle_id)) if row.team_id is not None else None
    if team is None or not _actor_has_team_access(session, team, actor):
        raise failure("request_forbidden", "This supervisor request is not accessible.", status.HTTP_403_FORBIDDEN)
    return row


def _append_history(session: Session, row: SupervisorRequest, actor: User, to_status: str, comment: str | None = None) -> None:
    session.add(
        SupervisorRequestStatusHistory(
            request_id=row.id,
            actor_id=actor.id,
            from_status=row.status,
            to_status=to_status,
            comment=comment,
        )
    )


def _audit(session: Session, actor: User, row: SupervisorRequest, action: str, **values: object) -> None:
    from .main import add_admin_audit_event

    add_admin_audit_event(
        session,
        actor_id=actor.id,
        affected_user_id=row.supervisor_id,
        target_type="SUPERVISOR_REQUEST",
        target_id=row.id,
        action=action,
        changed_values={"status": row.status, "academic_cycle_id": row.academic_cycle_id, **values},
    )


def _history_out(session: Session, request_id: int) -> list[dict[str, Any]]:
    rows = session.execute(
        select(SupervisorRequestStatusHistory, User.full_name)
        .join(User, User.id == SupervisorRequestStatusHistory.actor_id)
        .where(SupervisorRequestStatusHistory.request_id == request_id)
        .order_by(SupervisorRequestStatusHistory.created_at, SupervisorRequestStatusHistory.id)
    ).all()
    return [
        {
            "id": history.id,
            "from_status": history.from_status,
            "to_status": history.to_status,
            "comment": history.comment,
            "actor_name": actor_name,
            "created_at": history.created_at,
        }
        for history, actor_name in rows
    ]


def _document_out(session: Session, row: SupervisorRequest) -> dict[str, Any] | None:
    if row.document_id is None:
        return None
    document = session.get(SupervisorRequestDocument, row.document_id)
    if document is None:
        return None
    return {
        "id": document.id,
        "version": document.version,
        "filename": document.filename,
        "content_type": document.content_type,
        "file_size": document.file_size,
        "sha256": document.sha256,
        "page_count": document.page_count,
        "extracted_text": document.extracted_text,
        "extracted_fields": document.extracted_fields,
        "extraction_status": document.extraction_status,
        "extraction_runtime": document.extraction_runtime,
        "extracted_at": document.extracted_at,
        "confirmed_at": row.extraction_confirmed_at,
        "document_url": f"/api/v1/supervisor-requests/document/{row.id}",
    }


def _missing_required(document: SupervisorRequestDocument | None) -> list[str]:
    if document is None:
        return ["proposal document"]
    fields = document.extracted_fields or {}
    missing = [str(item) for item in fields.get("missing_required_fields", [])] if isinstance(fields.get("missing_required_fields", []), list) else []
    for name in ("title", "purpose"):
        value = fields.get(name)
        extracted_value = value.get("value") if isinstance(value, dict) else None
        if not isinstance(extracted_value, str) or not extracted_value.strip():
            label = "proposal title" if name == "title" else "problem statement or purpose"
            if label not in missing:
                missing.append(label)
    return missing


def _apply_document_snapshot(row: SupervisorRequest, document: SupervisorRequestDocument) -> None:
    row.ai_summary = None
    fields = document.extracted_fields or {}
    title = fields.get("title", {})
    purpose = fields.get("purpose", {})
    row.title = title.get("value") if isinstance(title, dict) else None
    row.summary = purpose.get("value") if isinstance(purpose, dict) else None
    row.document_id = document.id
    row.extraction_status = document.extraction_status


def _next_document_version(session: Session, request_id: int) -> int:
    current = session.scalar(select(func.max(SupervisorRequestDocument.version)).where(SupervisorRequestDocument.request_id == request_id))
    return int(current or 0) + 1


def _next_note_version(session: Session, request_id: int) -> int:
    current = session.scalar(select(func.max(SupervisorRequestSubmissionNoteVersion.version)).where(SupervisorRequestSubmissionNoteVersion.request_id == request_id))
    return int(current or 0) + 1


def _note_versions_out(session: Session, request_id: int) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(SupervisorRequestSubmissionNoteVersion)
        .where(SupervisorRequestSubmissionNoteVersion.request_id == request_id)
        .order_by(SupervisorRequestSubmissionNoteVersion.version)
    ).all()
    return [{"id": row.id, "version": row.version, "body": row.body, "created_by_id": row.created_by_id, "submitted_at": row.submitted_at} for row in rows]


def _audit_document(session: Session, actor: User, row: SupervisorRequest, action: str, document: SupervisorRequestDocument) -> None:
    _audit(
        session,
        actor,
        row,
        action,
        document_version=document.version,
        extraction_status=document.extraction_status,
        file_size=document.file_size,
    )


def _out(session: Session, row: SupervisorRequest, *, include_history: bool = True) -> dict[str, Any]:
    cycle = session.get(AcademicCycle, row.academic_cycle_id)
    requester = session.get(User, row.requester_user_id)
    supervisor = session.get(User, row.supervisor_id)
    team = session.get(Team, row.team_id) if row.team_id is not None else None
    shared_user = session.get(User, team.shared_user_id) if team is not None else None
    members = session.scalars(select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.academic_cycle_id == team.academic_cycle_id, TeamMember.is_active.is_(True)).order_by(TeamMember.id)).all() if team is not None else []
    reviewer = session.get(User, row.reviewer_id) if row.reviewer_id is not None else None
    capacity_used = _capacity_used(session, row.supervisor_id, row.academic_cycle_id, exclude_request_id=row.id if row.status == SupervisorRequestStatus.SUBMITTED.value else None)
    capacity_policy = session.scalar(
        select(SupervisorCapacityPolicy).where(
            SupervisorCapacityPolicy.supervisor_id == row.supervisor_id,
            or_(SupervisorCapacityPolicy.academic_year == cycle.academic_year, SupervisorCapacityPolicy.academic_cycle_id == row.academic_cycle_id) if cycle and cycle.academic_year is not None else SupervisorCapacityPolicy.academic_cycle_id == row.academic_cycle_id,
        )
    )
    capacity_limit = capacity_policy.max_group_capacity if capacity_policy else None
    result: dict[str, Any] = {
        "id": row.id,
        "academic_cycle_id": row.academic_cycle_id,
        "academic_cycle_name": cycle.display_name if cycle else None,
        "requester_user_id": row.requester_user_id,
        "requester_name": requester.full_name if requester else None,
        "requester_registration_number": requester.registration_number if requester else None,
        "team_id": team.id if team else None,
        "group_email": shared_user.email if shared_user else None,
        "group_members": [{"id": member.id, "name": member.full_name, "registration_number": member.registration_number, "email": member.university_email} for member in members],
        "supervisor_id": row.supervisor_id,
        "proposal_type": row.proposal_type,
        "problem_statement": row.problem_statement,
        "objectives": row.objectives,
        "scope": row.scope,
        "methodology": row.methodology,
        "supervisor_name": supervisor.full_name if supervisor else None,
        "title": row.title,
        "summary": row.summary,
        "ai_summary": row.ai_summary,
        "submission_note": row.submission_note,
        "submission_note_versions": _note_versions_out(session, row.id),
        "status": row.status,
        "revision": row.revision,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "submitted_at": row.submitted_at,
        "reviewed_at": row.reviewed_at,
        "reviewer_name": reviewer.full_name if reviewer else None,
        "capacity_used": capacity_used,
        "capacity_limit": capacity_limit,
        "capacity_remaining": max(capacity_limit - capacity_used, 0) if capacity_limit is not None else None,
        "capacity_warning": capacity_limit is not None and capacity_used >= capacity_limit,
        "extraction_status": row.extraction_status,
        "document": _document_out(session, row),
    }
    if include_history:
        result["status_history"] = _history_out(session, row.id)
    return result


def _load_for_view(session: Session, request_id: int) -> SupervisorRequest:
    row = session.get(SupervisorRequest, request_id)
    if row is None:
        raise failure("request_not_found", "Supervisor request was not found.", status.HTTP_404_NOT_FOUND)
    return row


@router.get("/cycles")
@proposal_router.get("/cycles")
def active_cycles(_: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    cycles = session.scalars(
        select(AcademicCycle).where(AcademicCycle.registration_open.is_(True)).order_by(AcademicCycle.display_name, AcademicCycle.id)
    ).all()
    return [{"id": cycle.id, "code": cycle.code, "display_name": cycle.display_name} for cycle in cycles]


@router.get("/supervisors")
@proposal_router.get("/supervisors")
def eligible_supervisors(
    academic_cycle_id: int = Query(gt=0),
    _: User = Depends(require_roles(UserRole.STUDENT)),
    session: Session = Depends(get_db),
):
    cycle = _cycle_for_request(session, academic_cycle_id)
    policies = session.scalars(
        select(SupervisorCapacityPolicy)
        .join(User, User.id == SupervisorCapacityPolicy.supervisor_id)
        .where(
            or_(SupervisorCapacityPolicy.academic_year == cycle.academic_year, SupervisorCapacityPolicy.academic_cycle_id == cycle.id) if cycle.academic_year is not None else SupervisorCapacityPolicy.academic_cycle_id == cycle.id,
            User.role == UserRole.SUPERVISOR,
            User.is_active.is_(True),
        )
        .order_by(User.full_name, User.id)
    ).all()
    result = []
    for policy in policies:
        used = _capacity_used(session, policy.supervisor_id, cycle.id)
        remaining = max(policy.max_group_capacity - used, 0)
        result.append(
            {
                "id": policy.supervisor_id,
                "name": policy.supervisor.full_name,
                "academic_cycle_id": cycle.id,
                "max_capacity": policy.max_group_capacity,
                "assigned_count": used,
                "remaining_capacity": remaining,
                "available": remaining > 0,
            }
        )
    return result


@router.get("/mine")
@proposal_router.get("/mine")
def my_requests(actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    team = _team_for_student(session, actor)
    team_ids = select(Team.id).where(Team.status != "dissolved")
    if actor.registration_number:
        team_ids = team_ids.where(or_(Team.shared_user_id == actor.id, select(TeamMember.id).where(
            TeamMember.team_id == Team.id,
            TeamMember.academic_cycle_id == Team.academic_cycle_id,
            or_(TeamMember.registration_number == actor.registration_number, TeamMember.university_email == actor.email),
            TeamMember.is_active.is_(True),
        ).exists()))
    else:
        team_ids = team_ids.where(Team.shared_user_id == actor.id)
    statement = select(SupervisorRequest).where(or_(SupervisorRequest.requester_user_id == actor.id, SupervisorRequest.team_id.in_(team_ids)))
    rows = session.scalars(statement.order_by(SupervisorRequest.updated_at.desc(), SupervisorRequest.id.desc())).all()
    return [_out(session, row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
@proposal_router.post("", status_code=status.HTTP_201_CREATED)
async def create_request(
    request: Request,
    academic_cycle_id: int = Form(..., gt=0),
    supervisor_id: int = Form(..., gt=0),
    proposal_type: str = Form("SHORT"),
    problem_statement: str | None = Form(None, max_length=10000),
    objectives: str | None = Form(None, max_length=10000),
    scope: str | None = Form(None, max_length=10000),
    methodology: str | None = Form(None, max_length=10000),
    submission_note: str | None = Form(default=None, max_length=4000),
    proposal_file: UploadFile = File(...),
    actor: User = Depends(require_roles(UserRole.STUDENT)),
    session: Session = Depends(get_db),
):
    validate_mutating_origin(request)
    try:
        data = await proposal_file.read(5 * 1024 * 1024 + 1)
        _reject_text_for_supervisor_selection(request, proposal_file.filename, proposal_file.content_type)
        extraction = extract_proposal_document(data, proposal_file.content_type, proposal_file.filename)
        cycle = _cycle_for_request(session, academic_cycle_id, lock=True)
        team = _team_for_student(session, actor)
        if team is not None and team.academic_cycle_id != cycle.id:
            raise failure("cycle_mismatch", "The student team does not belong to the selected cycle.")
        supervisor, policy = _lock_capacity(session, supervisor_id, cycle.id)
        _ensure_capacity(session, supervisor.id, cycle.id, policy)
        duplicate_filters = [SupervisorRequest.academic_cycle_id == cycle.id, SupervisorRequest.supervisor_id == supervisor.id, SupervisorRequest.status.in_(ACTIVE_REQUEST_STATUSES)]
        duplicate_filters.append(SupervisorRequest.team_id == team.id if team is not None else SupervisorRequest.requester_user_id == actor.id)
        duplicate = session.scalar(select(SupervisorRequest.id).where(*duplicate_filters))
        if duplicate is not None:
            raise failure("duplicate_active_request", "An active request already exists for this supervisor and cycle.")
        proposal_type = proposal_type.strip().upper()
        if proposal_type not in {"SHORT", "LONG"}:
            raise failure("invalid_proposal_type", "Proposal type must be SHORT or LONG.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        row = SupervisorRequest(
            academic_cycle_id=cycle.id,
            requester_user_id=actor.id,
            team_id=team.id if team else None,
            supervisor_id=supervisor.id,
            proposal_type=proposal_type,
            problem_statement=problem_statement.strip() if problem_statement else None,
            objectives=objectives.strip() if objectives else None,
            scope=scope.strip() if scope else None,
            methodology=methodology.strip() if methodology else None,
            submission_note=_normalize_submission_note(submission_note),
            status=SupervisorRequestStatus.DRAFT.value,
            extraction_status=SupervisorRequestExtractionStatus.EXTRACTED.value,
            revision=1,
        )
        session.add(row)
        session.flush()
        document = SupervisorRequestDocument(
            request_id=row.id,
            version=1,
            filename=(proposal_file.filename or "proposal.pdf")[:255],
            content_type=extraction.content_type,
            file_size=extraction.file_size,
            sha256=extraction.sha256,
            page_count=extraction.page_count,
            content=data,
            extracted_text=extraction.extracted_text,
            extracted_fields=extraction.extracted_fields,
            extraction_status=SupervisorRequestExtractionStatus.EXTRACTED.value,
            extraction_runtime=EXTRACTION_RUNTIME,
            extracted_at=extraction.extracted_at,
        )
        session.add(document)
        session.flush()
        _apply_document_snapshot(row, document)
        _append_history(session, row, actor, SupervisorRequestStatus.DRAFT.value)
        _audit_document(session, actor, row, "supervisor_request_document_uploaded", document)
        _audit_document(session, actor, row, "supervisor_request_extracted", document)
        _audit(session, actor, row, "supervisor_request_draft_created", supervisor_id=supervisor.id)
        session.commit()
        session.refresh(row)
        return _out(session, row)
    except PdfExtractionError as error:
        session.rollback()
        raise failure(error.code, error.message, status.HTTP_422_UNPROCESSABLE_CONTENT) from error
    except HTTPException:
        session.rollback()
        raise
    except IntegrityError as error:
        session.rollback()
        raise failure("duplicate_active_request", "An active request already exists for this supervisor and cycle.") from error
    except Exception as error:
        session.rollback()
        logger.exception("supervisor_request.create_failed actor_id=%s cycle_id=%s supervisor_id=%s", actor.id, academic_cycle_id, supervisor_id)
        raise failure("request_save_failed", "The supervisor request could not be saved.", status.HTTP_500_INTERNAL_SERVER_ERROR) from error


@router.post("/draft/{request_id}/document")
@proposal_router.post("/draft/{request_id}/document")
async def update_draft_document(
    request_id: int,
    request: Request,
    revision: int = Form(..., gt=0),
    submission_note: str | None = Form(default=None, max_length=4000),
    problem_statement: str | None = Form(None, max_length=10000),
    objectives: str | None = Form(None, max_length=10000),
    scope: str | None = Form(None, max_length=10000),
    methodology: str | None = Form(None, max_length=10000),
    proposal_file: UploadFile = File(...),
    actor: User = Depends(require_roles(UserRole.STUDENT)),
    session: Session = Depends(get_db),
):
    validate_mutating_origin(request)
    try:
        data = await proposal_file.read(5 * 1024 * 1024 + 1)
        _reject_text_for_supervisor_selection(request, proposal_file.filename, proposal_file.content_type)
        extraction = extract_proposal_document(data, proposal_file.content_type, proposal_file.filename)
        row = _owner_request(session, request_id, actor, lock=True)
        if row.status not in (SupervisorRequestStatus.DRAFT.value, SupervisorRequestStatus.CHANGES_REQUESTED.value):
            raise failure("request_not_editable", "Only draft or changes-requested requests can be edited.")
        if row.revision != revision:
            raise failure("stale_request", "This request changed elsewhere; reload it before editing.")
        document = SupervisorRequestDocument(
            request_id=row.id,
            version=_next_document_version(session, row.id),
            filename=(proposal_file.filename or "proposal.pdf")[:255],
            content_type=extraction.content_type,
            file_size=extraction.file_size,
            sha256=extraction.sha256,
            page_count=extraction.page_count,
            content=data,
            extracted_text=extraction.extracted_text,
            extracted_fields=extraction.extracted_fields,
            extraction_status=SupervisorRequestExtractionStatus.EXTRACTED.value,
            extraction_runtime=EXTRACTION_RUNTIME,
            extracted_at=extraction.extracted_at,
        )
        session.add(document)
        session.flush()
        _apply_document_snapshot(row, document)
        row.submission_note = _normalize_submission_note(submission_note)
        row.problem_statement = problem_statement.strip() if problem_statement is not None else row.problem_statement
        row.objectives = objectives.strip() if objectives is not None else row.objectives
        row.scope = scope.strip() if scope is not None else row.scope
        row.methodology = methodology.strip() if methodology is not None else row.methodology
        row.revision += 1
        _audit_document(session, actor, row, "supervisor_request_document_uploaded", document)
        _audit_document(session, actor, row, "supervisor_request_extracted", document)
        session.commit()
        session.refresh(row)
        return _out(session, row)
    except PdfExtractionError as error:
        session.rollback()
        raise failure(error.code, error.message, status.HTTP_422_UNPROCESSABLE_CONTENT) from error
    except HTTPException:
        session.rollback()
        raise
    except Exception as error:
        session.rollback()
        raise failure("request_save_failed", "The supervisor request could not be saved.", status.HTTP_500_INTERNAL_SERVER_ERROR) from error


@router.post("/{request_id}/confirm")
@proposal_router.post("/{request_id}/confirm")
def confirm_extraction(
    request_id: int,
    payload: RevisionAction,
    request: Request,
    actor: User = Depends(require_roles(UserRole.STUDENT)),
    session: Session = Depends(get_db),
):
    validate_mutating_origin(request)
    try:
        row = _owner_request(session, request_id, actor, lock=True)
        if row.status not in (SupervisorRequestStatus.DRAFT.value, SupervisorRequestStatus.CHANGES_REQUESTED.value):
            raise failure("request_not_confirmable", "Only draft or changes-requested requests can be confirmed.")
        if row.revision != payload.revision:
            raise failure("stale_request", "This request changed elsewhere; reload it before confirming.")
        document = session.get(SupervisorRequestDocument, row.document_id) if row.document_id else None
        missing = _missing_required(document)
        if document is None or document.extraction_status != SupervisorRequestExtractionStatus.EXTRACTED.value:
            raise failure("extraction_unavailable", "The proposal extraction is not ready for confirmation.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        if missing:
            raise failure("required_fields_missing", f"Required fields were not detected in the PDF: {', '.join(missing)}.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        row.extraction_status = SupervisorRequestExtractionStatus.CONFIRMED.value
        row.extraction_confirmed_at = utc_now()
        row.extraction_confirmed_by_id = actor.id
        row.revision += 1
        _audit_document(session, actor, row, "supervisor_request_extraction_confirmed", document)
        session.commit()
        session.refresh(row)
        return _out(session, row)
    except HTTPException:
        session.rollback()
        raise
    except Exception as error:
        session.rollback()
        raise failure("confirmation_save_failed", "The proposal confirmation could not be saved.", status.HTTP_500_INTERNAL_SERVER_ERROR) from error


@router.post("/{request_id}/submit")
@proposal_router.post("/{request_id}/submit")
def submit_request(
    request_id: int,
    payload: RevisionAction,
    request: Request,
    actor: User = Depends(require_roles(UserRole.STUDENT)),
    session: Session = Depends(get_db),
):
    validate_mutating_origin(request)
    try:
        row = _owner_request(session, request_id, actor, lock=True)
        if row.status not in (SupervisorRequestStatus.DRAFT.value, SupervisorRequestStatus.CHANGES_REQUESTED.value):
            raise failure("request_not_submittable", "Only draft or changes-requested requests can be submitted.")
        if row.revision != payload.revision:
            raise failure("stale_request", "This request changed elsewhere; reload it before submitting.")
        if row.extraction_status != SupervisorRequestExtractionStatus.CONFIRMED.value:
            raise failure("extraction_not_confirmed", "Review and confirm the extracted proposal preview before submitting.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        _cycle_for_request(session, row.academic_cycle_id, lock=True)
        supervisor, policy = _lock_capacity(session, row.supervisor_id, row.academic_cycle_id)
        _ensure_capacity(session, supervisor.id, row.academic_cycle_id, policy)
        duplicate = session.scalar(
            select(SupervisorRequest.id).where(
                SupervisorRequest.academic_cycle_id == row.academic_cycle_id,
                SupervisorRequest.requester_user_id == row.requester_user_id,
                SupervisorRequest.supervisor_id == row.supervisor_id,
                SupervisorRequest.status.in_(ACTIVE_REQUEST_STATUSES),
                SupervisorRequest.id != row.id,
            )
        )
        if duplicate is not None:
            raise failure("duplicate_active_request", "An active request already exists for this supervisor and cycle.")
        previous = row.status
        if row.submission_note:
            note_version = _next_note_version(session, row.id)
            session.add(
                SupervisorRequestSubmissionNoteVersion(
                    request_id=row.id,
                    version=note_version,
                    body=row.submission_note,
                    created_by_id=actor.id,
                )
            )
            _audit(session, actor, row, "supervisor_request_submission_note_submitted", note_version=note_version)
        row.status = SupervisorRequestStatus.SUBMITTED.value
        row.submitted_at = utc_now()
        row.reviewed_at = None
        row.reviewer_id = None
        row.revision += 1
        _append_history(session, row, actor, row.status)
        _audit(session, actor, row, "supervisor_request_resubmitted" if previous == SupervisorRequestStatus.CHANGES_REQUESTED.value else "supervisor_request_submitted", previous_status=previous)
        session.commit()
        session.refresh(row)
        return _out(session, row)
    except HTTPException:
        session.rollback()
        raise
    except IntegrityError as error:
        session.rollback()
        raise failure("duplicate_active_request", "An active request already exists for this supervisor and cycle.") from error
    except Exception as error:
        session.rollback()
        raise failure("request_submit_failed", "The supervisor request could not be submitted.", status.HTTP_500_INTERNAL_SERVER_ERROR) from error


@router.post("/{request_id}/withdraw")
@proposal_router.post("/{request_id}/withdraw")
def withdraw_request(
    request_id: int,
    payload: RevisionAction,
    request: Request,
    actor: User = Depends(require_roles(UserRole.STUDENT)),
    session: Session = Depends(get_db),
):
    validate_mutating_origin(request)
    try:
        row = _owner_request(session, request_id, actor, lock=True)
        if row.status not in (SupervisorRequestStatus.DRAFT.value, SupervisorRequestStatus.SUBMITTED.value, SupervisorRequestStatus.CHANGES_REQUESTED.value):
            raise failure("request_not_withdrawable", "This request cannot be withdrawn in its current state.")
        if row.revision != payload.revision:
            raise failure("stale_request", "This request changed elsewhere; reload it before withdrawing.")
        previous = row.status
        row.status = SupervisorRequestStatus.WITHDRAWN.value
        row.revision += 1
        _append_history(session, row, actor, row.status)
        _audit(session, actor, row, "supervisor_request_withdrawn", previous_status=previous)
        session.commit()
        session.refresh(row)
        return _out(session, row)
    except HTTPException:
        session.rollback()
        raise
    except Exception as error:
        session.rollback()
        raise failure("request_withdraw_failed", "The supervisor request could not be withdrawn.", status.HTTP_500_INTERNAL_SERVER_ERROR) from error


@router.get("/supervisor/queue")
def supervisor_queue(
    status_filter: str | None = Query(None, alias="status"),
    actor: User = Depends(require_roles(UserRole.SUPERVISOR)),
    session: Session = Depends(get_db),
):
    statement = select(SupervisorRequest).where(SupervisorRequest.supervisor_id == actor.id)
    if status_filter is not None:
        if status_filter not in ACTIVE_REQUEST_STATUSES + (SupervisorRequestStatus.REJECTED.value, SupervisorRequestStatus.WITHDRAWN.value):
            raise failure("invalid_status", "Unknown supervisor request status.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        statement = statement.where(SupervisorRequest.status == status_filter)
    else:
        statement = statement.where(SupervisorRequest.status.in_(DECISION_STATUSES))
    rows = session.scalars(statement.order_by(SupervisorRequest.updated_at, SupervisorRequest.id)).all()
    return [_out(session, row) for row in rows]


@router.post("/{request_id}/decision")
@proposal_router.post("/{request_id}/decision")
def decide_request(
    request_id: int,
    payload: DecisionAction,
    request: Request,
    actor: User = Depends(require_roles(UserRole.SUPERVISOR)),
    session: Session = Depends(get_db),
):
    validate_mutating_origin(request)
    try:
        row = session.execute(select(SupervisorRequest).where(SupervisorRequest.id == request_id).with_for_update()).scalar_one_or_none()
        if row is None:
            raise failure("request_not_found", "Supervisor request was not found.", status.HTTP_404_NOT_FOUND)
        if row.supervisor_id != actor.id:
            raise failure("request_forbidden", "Only the selected supervisor may review this request.", status.HTTP_403_FORBIDDEN)
        if row.status not in DECISION_STATUSES:
            raise failure("request_not_decidable", "This request is not awaiting a supervisor decision.")
        if row.revision != payload.revision:
            raise failure("stale_request", "This request changed elsewhere; reload it before deciding.")
        if payload.action == "accept":
            # Closing registration blocks new submissions, not a supervisor's
            # decision on an already submitted, owned request.
            cycle = _cycle_for_request(session, row.academic_cycle_id, lock=True, require_open=False)
            team = session.execute(
                select(Team)
                .where(Team.id == row.team_id, Team.academic_cycle_id == cycle.id)
                .with_for_update()
            ).scalar_one_or_none() if row.team_id is not None else None
            if team is None:
                raise failure("team_required", "A registered team is required before supervisor assignment.", status.HTTP_422_UNPROCESSABLE_CONTENT)
            supervisor, policy = _lock_capacity(session, row.supervisor_id, cycle.id)
            _ensure_capacity(session, supervisor.id, cycle.id, policy, exclude_request_id=row.id)
            if session.scalar(select(SupervisorAssignment.id).where(SupervisorAssignment.team_id == team.id, SupervisorAssignment.ended_at.is_(None))) is not None:
                raise failure("team_already_assigned", "This team already has an active supervisor assignment.")
            assignment = SupervisorAssignment(team_id=team.id, academic_cycle_id=cycle.id, supervisor_id=actor.id, assigned_by_id=actor.id, academic_year=cycle.academic_year, session=cycle.session)
            session.add(assignment)
            session.flush()
            ensure_collaboration_channel(session, assignment, team)
            row.assignment_id = assignment.id
            _audit(
                session,
                actor,
                row,
                "supervisor_assignment_created",
                assignment_id=assignment.id,
                team_id=team.id,
                academic_cycle_id=cycle.id,
                supervisor_id=actor.id,
            )
        target = {"accept": SupervisorRequestStatus.ACCEPTED.value, "reject": SupervisorRequestStatus.REJECTED.value, "request_changes": SupervisorRequestStatus.CHANGES_REQUESTED.value}[payload.action]
        previous = row.status
        row.status = target
        row.reviewed_at = utc_now()
        row.reviewer_id = actor.id
        row.revision += 1
        _append_history(session, row, actor, target, payload.comment)
        _audit(session, actor, row, {"accept": "supervisor_request_accepted", "reject": "supervisor_request_rejected", "request_changes": "supervisor_request_changes_requested"}[payload.action], previous_status=previous, comment=payload.comment)
        session.commit()
        session.refresh(row)
        return _out(session, row)
    except HTTPException:
        session.rollback()
        raise
    except IntegrityError as error:
        session.rollback()
        raise failure("request_conflict", "The supervisor decision conflicts with another active change.") from error
    except Exception as error:
        session.rollback()
        raise failure("decision_save_failed", "The supervisor decision could not be saved.", status.HTTP_500_INTERNAL_SERVER_ERROR) from error


@router.get("/document/{request_id}")
@proposal_router.get("/document/{request_id}")
def proposal_document(
    request_id: int,
    actor: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    row = _load_for_view(session, request_id)
    team = _team_for_student(session, actor) if actor.role == UserRole.STUDENT else None
    allowed = (
        actor.role in (UserRole.ADMIN, UserRole.COORDINATOR)
        or (actor.role == UserRole.SUPERVISOR and row.supervisor_id == actor.id)
        or (actor.role == UserRole.STUDENT and (row.requester_user_id == actor.id or (team is not None and row.team_id == team.id)))
    )
    if not allowed:
        raise failure("request_forbidden", "This proposal document is not accessible.", status.HTTP_403_FORBIDDEN)
    document = session.get(SupervisorRequestDocument, row.document_id) if row.document_id else None
    if document is None:
        raise failure("document_not_found", "The proposal document was not found.", status.HTTP_404_NOT_FOUND)
    filename = document.filename.replace('"', "'").replace("\r", "").replace("\n", "")
    media_type = document.content_type or "application/octet-stream"
    return StreamingResponse(BytesIO(document.content), media_type=media_type, headers={"Content-Disposition": f'inline; filename="{filename}"'})


def _monitor_statement(
    session: Session,
    *,
    cycle_id: int | None,
    supervisor_id: int | None,
    status_filter: str | None,
    from_date: datetime | None,
    to_date: datetime | None,
):
    statement = select(SupervisorRequest).order_by(SupervisorRequest.updated_at.desc(), SupervisorRequest.id.desc())
    if cycle_id is not None:
        if session.get(AcademicCycle, cycle_id) is None:
            raise failure("academic_cycle_not_found", "Academic cycle was not found.", status.HTTP_404_NOT_FOUND)
        statement = statement.where(SupervisorRequest.academic_cycle_id == cycle_id)
    if supervisor_id is not None:
        statement = statement.where(SupervisorRequest.supervisor_id == supervisor_id)
    if status_filter is not None:
        if status_filter not in ACTIVE_REQUEST_STATUSES + (SupervisorRequestStatus.REJECTED.value, SupervisorRequestStatus.WITHDRAWN.value):
            raise failure("invalid_status", "Unknown supervisor request status.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        statement = statement.where(SupervisorRequest.status == status_filter)
    if from_date is not None:
        statement = statement.where(SupervisorRequest.created_at >= from_date)
    if to_date is not None:
        statement = statement.where(SupervisorRequest.created_at <= to_date)
    return session.scalars(statement).all()


@router.get("/admin/monitor")
@proposal_router.get("/admin/monitor")
def admin_monitor(
    academic_cycle_id: int | None = Query(None, gt=0),
    supervisor_id: int | None = Query(None, gt=0),
    status_filter: str | None = Query(None, alias="status"),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    _: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
):
    rows = _monitor_statement(session, cycle_id=academic_cycle_id, supervisor_id=supervisor_id, status_filter=status_filter, from_date=from_date, to_date=to_date)
    return [_out(session, row) for row in rows]


@router.get("/coordinator/monitor")
@proposal_router.get("/coordinator/monitor")
def coordinator_monitor(
    academic_cycle_id: int | None = Query(None, gt=0),
    supervisor_id: int | None = Query(None, gt=0),
    status_filter: str | None = Query(None, alias="status"),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    _: User = Depends(require_roles(UserRole.COORDINATOR)),
    session: Session = Depends(get_db),
):
    rows = _monitor_statement(session, cycle_id=academic_cycle_id, supervisor_id=supervisor_id, status_filter=status_filter, from_date=from_date, to_date=to_date)
    return [_out(session, row) for row in rows]


@router.get("/detail/{request_id}")
@proposal_router.get("/{request_id}")
def read_request(
    request_id: int,
    actor: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    row = _load_for_view(session, request_id)
    team = _team_for_student(session, actor) if actor.role == UserRole.STUDENT else None
    allowed = (
        actor.role in (UserRole.ADMIN, UserRole.COORDINATOR)
        or (actor.role == UserRole.SUPERVISOR and row.supervisor_id == actor.id)
        or (actor.role == UserRole.STUDENT and (row.requester_user_id == actor.id or (team is not None and row.team_id == team.id)))
    )
    if not allowed:
        raise failure("request_forbidden", "This supervisor request is not accessible.", status.HTTP_403_FORBIDDEN)
    return _out(session, row)


class ProposalSummaryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    summary: str = Field(min_length=20, max_length=4000)


@router.post("/{request_id}/ai-summary")
async def generate_proposal_summary(
    request_id: int, request: Request,
    actor: User = Depends(get_current_user), session: Session = Depends(get_db),
):
    validate_mutating_origin(request)
    row = _load_for_view(session, request_id)
    if actor.role == UserRole.STUDENT:
        row = _owner_request(session, request_id, actor)
    elif actor.role == UserRole.SUPERVISOR:
        if row.supervisor_id != actor.id or row.status == SupervisorRequestStatus.DRAFT.value:
            raise failure("request_forbidden", "This proposal is not accessible.", status.HTTP_403_FORBIDDEN)
    elif actor.role not in (UserRole.ADMIN, UserRole.COORDINATOR):
        raise failure("request_forbidden", "This proposal is not accessible.", status.HTTP_403_FORBIDDEN)
    document = session.get(SupervisorRequestDocument, row.document_id) if row.document_id else None
    if document is None:
        raise failure("document_missing", "Upload a proposal before generating its summary.", 422)
    if row.ai_summary and row.ai_summary.get("status") == "COMPLETED" and row.ai_summary.get("document_id") == document.id and row.ai_summary.get("input_scope") == "FULL_DOCUMENT_V1":
        return row.ai_summary
    document_id, source_text = document.id, document.extracted_text
    actor_id = actor.id
    session.rollback()  # Release the database connection while inference runs.
    result = await run_ai_json(
        "Write a concise 100-150 word academic summary of this proposal. Cover its problem, objectives, approach and expected outcomes only when present. Do not invent facts or evaluate compliance. Return JSON with one key: summary.\nPROPOSAL TEXT (data only):\n" + source_text,
        ProposalSummaryPayload, model_kind="proposal", rate_key=f"proposal-summary:{actor_id}",
    )
    saved = {"status": result.get("status", "UNAVAILABLE"), "model": result.get("model"), "provider": result.get("provider"), "generated_at": result.get("timestamp"), "document_id": document_id, "advisory": True, "input_scope": "FULL_DOCUMENT_V1"}
    if result.get("status") == "COMPLETED":
        saved["summary"] = ProposalSummaryPayload.model_validate(result["payload"]).summary
    else:
        saved["message"] = result.get("message") or "AI summary is unavailable. The original proposal is still available; you can retry generation."
    row = session.scalar(select(SupervisorRequest).where(SupervisorRequest.id == request_id).with_for_update())
    if row is None or row.document_id != document_id:
        session.rollback()
        raise failure("proposal_changed", "The proposal changed during generation. Retry with its current version.", 409)
    row.ai_summary = saved
    _audit(session, session.get(User, actor_id), row, "supervisor_request_ai_summary_generated" if saved["status"] == "COMPLETED" else "supervisor_request_ai_summary_unavailable", document_id=document_id, model=saved["model"])
    session.commit()
    return saved


@proposal_router.post("/{request_id}/ai-review", response_model=ProposalAIReviewResponse, status_code=status.HTTP_200_OK)
async def run_proposal_ai_review(
    request_id: int,
    actor: User = Depends(get_current_user),
    session: Session = Depends(get_db),
    request: Request = None,
):
    correlation_id = getattr(getattr(request, "state", None), "request_id", None) or "untracked"
    logger.info("ai_review.start request_id=%s proposal_id=%s", correlation_id, request_id)
    row = _load_for_view(session, request_id)
    logger.info("proposal.loaded request_id=%s proposal_id=%s", correlation_id, request_id)
    team = _team_for_student(session, actor) if actor.role == UserRole.STUDENT else None
    allowed = actor.role in (UserRole.COORDINATOR, UserRole.ADMIN) or (actor.role == UserRole.SUPERVISOR and row.supervisor_id == actor.id) or (actor.role == UserRole.STUDENT and (row.requester_user_id == actor.id or (team is not None and row.team_id == team.id)))
    if not allowed:
        raise failure("proposal_forbidden", "This proposal is outside your authorized scope.", status.HTTP_403_FORBIDDEN)
    document = session.get(SupervisorRequestDocument, row.document_id) if row.document_id else None
    logger.info("document.loaded request_id=%s proposal_id=%s present=%s", correlation_id, request_id, document is not None)
    proposal_key = f"supervisor-request:{row.id}"
    existing = session.scalar(select(ProposalAIReviewRun).where(ProposalAIReviewRun.proposal_id == proposal_key, ProposalAIReviewRun.status == "RUNNING"))
    if existing is not None:
        raise failure("review_in_progress", "An AI review is already running for this proposal.")
    run = ProposalAIReviewRun(proposal_id=proposal_key, status="RUNNING", runtime="ollama", model=settings.ollama_proposal_model, result={"status": "RUNNING", "advisory": True})
    session.add(run); session.commit(); session.refresh(run)
    try:
        extracted_text = document.extracted_text.strip() if document is not None and document.extracted_text else ""
        logger.info("extracted_content.ready request_id=%s proposal_id=%s present=%s length=%s", correlation_id, request_id, bool(extracted_text), len(extracted_text))
        logger.info("deterministic_findings.ready request_id=%s proposal_id=%s", correlation_id, request_id)
        if not extracted_text:
            result = {**_ai_fallback(row, document), "fallback_reason": "missing_document" if document is None else "invalid_response", "error_type": "MissingDocument" if document is None else "EmptyExtractedText", "request_id": correlation_id}
        else:
            logger.info("ollama.request.start request_id=%s proposal_id=%s", correlation_id, request_id)
            provider = await run_ai_json(_review_prompt(row, document), ProposalProviderPayload, model_kind="proposal", rate_key=f"proposal:{actor.id}")
            logger.info("ollama.response.received request_id=%s proposal_id=%s status=%s", correlation_id, request_id, provider.get("status"))
            logger.info("schema.validation request_id=%s proposal_id=%s valid=%s", correlation_id, request_id, provider.get("source") == "AI")
            if provider.get("status") in ("AVAILABLE", "COMPLETED"):
                provider = {"status": "AVAILABLE", "runtime": provider.get("provider"), "model": provider.get("model"), "timestamp": provider.get("timestamp"), "findings": provider.get("payload", {}).get("findings", []), "metadata": {key: provider.get(key) for key in ("request_id", "http_status", "latency_ms", "retry_count")}}
            if provider.get("status") not in ("AVAILABLE", "COMPLETED"):
                logger.warning("ai_review.fallback request_id=%s model=%s fallback_reason=%s error_type=%s", provider.get("request_id", correlation_id), provider.get("model", settings.ollama_proposal_model), provider.get("fallback_reason", "provider_failure"), provider.get("error_type", "UnknownError"))
                result = {**_ai_fallback(row, document), **{key: provider.get(key) for key in ("provider", "source", "fallback_reason", "error_type", "http_status", "request_id", "retry_count", "latency_ms", "model", "timestamp") if provider.get(key) is not None}}
            else:
                findings = provider.get("findings", [])
                result = {"status": "COMPLETED", "source": "AI", "provider": provider.get("runtime", "ollama"), "model": provider.get("model"), "findings": findings, "advisory": True}
        run.status = "COMPLETED"; run.runtime = str(result.get("provider", "deterministic")); run.model = result.get("model"); run.result = result
    except Exception as error:
        logger.exception("ai_review.failure request_id=%s proposal_id=%s error_type=%s", correlation_id, request_id, type(error).__name__)
        run.status = "COMPLETED"; run.runtime = "ollama"; run.model = settings.ollama_proposal_model
        run.result = {**_ai_fallback(row, document), "fallback_reason": "provider_unavailable", "error_type": type(error).__name__, "request_id": correlation_id}
    run.finished_at = utc_now(); session.commit(); session.refresh(run)
    logger.info("review.persisted request_id=%s proposal_id=%s status=%s", correlation_id, request_id, run.status)
    return _ai_out(run)


@proposal_router.get("/{request_id}/ai-review")
def latest_proposal_ai_review(request_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    row = _load_for_view(session, request_id)
    team = _team_for_student(session, actor) if actor.role == UserRole.STUDENT else None
    allowed = actor.role in (UserRole.COORDINATOR, UserRole.ADMIN) or (actor.role == UserRole.SUPERVISOR and row.supervisor_id == actor.id) or (actor.role == UserRole.STUDENT and (row.requester_user_id == actor.id or (team is not None and row.team_id == team.id)))
    if not allowed:
        raise failure("proposal_forbidden", "This proposal is outside your authorized scope.", status.HTTP_403_FORBIDDEN)
    run = session.scalar(select(ProposalAIReviewRun).where(ProposalAIReviewRun.proposal_id == f"supervisor-request:{row.id}").order_by(ProposalAIReviewRun.id.desc()))
    if run is None:
        raise failure("review_not_found", "No AI review has been run for this proposal.", status.HTTP_404_NOT_FOUND)
    return _ai_out(run)
