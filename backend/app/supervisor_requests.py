"""Cycle-scoped supervisor selection and proposal-request workflow."""

from datetime import datetime
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles, utc_now, validate_mutating_origin
from .database import get_db
from .pdf_extraction import EXTRACTION_RUNTIME, PdfExtractionError, extract_one_page_pdf
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
    User,
    UserRole,
)

router = APIRouter(prefix="/api/v1/supervisor-requests")

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


def _normalize_submission_note(value: str | None) -> str | None:
    normalized = value.strip() if value else ""
    return normalized or None


def failure(code: str, message: str, http_status: int = status.HTTP_409_CONFLICT) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "message": message})


def _team_for_student(session: Session, actor: User) -> Team | None:
    return session.execute(select(Team).where(Team.shared_user_id == actor.id).order_by(Team.id)).scalar_one_or_none()


def _cycle_for_request(session: Session, cycle_id: int, *, lock: bool = False) -> AcademicCycle:
    statement = select(AcademicCycle).where(AcademicCycle.id == cycle_id)
    if lock:
        statement = statement.with_for_update()
    cycle = session.execute(statement).scalar_one_or_none()
    if cycle is None:
        raise failure("academic_cycle_not_found", "Academic cycle was not found.", status.HTTP_404_NOT_FOUND)
    if not cycle.registration_open:
        raise failure("academic_cycle_closed", "This academic cycle is not accepting supervisor requests.")
    return cycle


def _lock_capacity(session: Session, supervisor_id: int, cycle_id: int) -> tuple[User, SupervisorCapacityPolicy]:
    supervisor = session.execute(
        select(User).where(User.id == supervisor_id).with_for_update()
    ).scalar_one_or_none()
    if supervisor is None or supervisor.role != UserRole.SUPERVISOR or not supervisor.is_active:
        raise failure("supervisor_ineligible", "The selected supervisor is not active.")
    policy = session.execute(
        select(SupervisorCapacityPolicy)
        .where(
            SupervisorCapacityPolicy.supervisor_id == supervisor_id,
            SupervisorCapacityPolicy.academic_cycle_id == cycle_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if policy is None:
        raise failure("capacity_policy_missing", "No capacity policy exists for this supervisor and cycle.")
    return supervisor, policy


def _capacity_used(session: Session, supervisor_id: int, cycle_id: int, *, exclude_request_id: int | None = None) -> int:
    assignment_count = session.scalar(
        select(func.count(SupervisorAssignment.id)).where(
            SupervisorAssignment.supervisor_id == supervisor_id,
            SupervisorAssignment.academic_cycle_id == cycle_id,
            SupervisorAssignment.ended_at.is_(None),
        )
    ) or 0
    individual_request = select(func.count(SupervisorRequest.id)).where(
        SupervisorRequest.supervisor_id == supervisor_id,
        SupervisorRequest.academic_cycle_id == cycle_id,
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
    team_owner = session.scalar(
        select(Team.id).where(
            Team.id == row.team_id,
            Team.academic_cycle_id == row.academic_cycle_id,
            Team.shared_user_id == actor.id,
        )
    ) if row.team_id is not None else None
    if team_owner is None:
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
    reviewer = session.get(User, row.reviewer_id) if row.reviewer_id is not None else None
    capacity_used = _capacity_used(session, row.supervisor_id, row.academic_cycle_id, exclude_request_id=row.id if row.status == SupervisorRequestStatus.SUBMITTED.value else None)
    capacity_policy = session.scalar(
        select(SupervisorCapacityPolicy).where(
            SupervisorCapacityPolicy.supervisor_id == row.supervisor_id,
            SupervisorCapacityPolicy.academic_cycle_id == row.academic_cycle_id,
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
        "supervisor_id": row.supervisor_id,
        "supervisor_name": supervisor.full_name if supervisor else None,
        "title": row.title,
        "summary": row.summary,
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
def active_cycles(_: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    cycles = session.scalars(
        select(AcademicCycle).where(AcademicCycle.registration_open.is_(True)).order_by(AcademicCycle.display_name, AcademicCycle.id)
    ).all()
    return [{"id": cycle.id, "code": cycle.code, "display_name": cycle.display_name} for cycle in cycles]


@router.get("/supervisors")
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
            SupervisorCapacityPolicy.academic_cycle_id == cycle.id,
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
def my_requests(actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    team = _team_for_student(session, actor)
    statement = select(SupervisorRequest).where(SupervisorRequest.requester_user_id == actor.id)
    if team is not None:
        statement = statement.where(or_(SupervisorRequest.team_id == team.id, SupervisorRequest.team_id.is_(None)))
    rows = session.scalars(statement.order_by(SupervisorRequest.updated_at.desc(), SupervisorRequest.id.desc())).all()
    return [_out(session, row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_request(
    request: Request,
    academic_cycle_id: int = Form(..., gt=0),
    supervisor_id: int = Form(..., gt=0),
    submission_note: str | None = Form(default=None, max_length=4000),
    proposal_file: UploadFile = File(...),
    actor: User = Depends(require_roles(UserRole.STUDENT)),
    session: Session = Depends(get_db),
):
    validate_mutating_origin(request)
    try:
        data = await proposal_file.read(5 * 1024 * 1024 + 1)
        extraction = extract_one_page_pdf(data, proposal_file.content_type, proposal_file.filename)
        cycle = _cycle_for_request(session, academic_cycle_id, lock=True)
        team = _team_for_student(session, actor)
        if team is not None and team.academic_cycle_id != cycle.id:
            raise failure("cycle_mismatch", "The student team does not belong to the selected cycle.")
        supervisor, policy = _lock_capacity(session, supervisor_id, cycle.id)
        _ensure_capacity(session, supervisor.id, cycle.id, policy)
        duplicate = session.scalar(
            select(SupervisorRequest.id).where(
                SupervisorRequest.academic_cycle_id == cycle.id,
                SupervisorRequest.requester_user_id == actor.id,
                SupervisorRequest.supervisor_id == supervisor.id,
                SupervisorRequest.status.in_(ACTIVE_REQUEST_STATUSES),
            )
        )
        if duplicate is not None:
            raise failure("duplicate_active_request", "An active request already exists for this supervisor and cycle.")
        row = SupervisorRequest(
            academic_cycle_id=cycle.id,
            requester_user_id=actor.id,
            team_id=team.id if team else None,
            supervisor_id=supervisor.id,
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
        raise failure("request_save_failed", "The supervisor request could not be saved.", status.HTTP_500_INTERNAL_SERVER_ERROR) from error


@router.post("/draft/{request_id}/document")
async def update_draft_document(
    request_id: int,
    request: Request,
    revision: int = Form(..., gt=0),
    submission_note: str | None = Form(default=None, max_length=4000),
    proposal_file: UploadFile = File(...),
    actor: User = Depends(require_roles(UserRole.STUDENT)),
    session: Session = Depends(get_db),
):
    validate_mutating_origin(request)
    try:
        data = await proposal_file.read(5 * 1024 * 1024 + 1)
        extraction = extract_one_page_pdf(data, proposal_file.content_type, proposal_file.filename)
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
        if payload.action in ("reject", "request_changes") and not payload.comment:
            raise failure("comment_required", "A comment is required for this decision.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        if payload.action == "accept":
            cycle = _cycle_for_request(session, row.academic_cycle_id, lock=True)
            team = session.execute(
                select(Team)
                .where(Team.id == row.team_id, Team.academic_cycle_id == cycle.id)
                .with_for_update()
            ).scalar_one_or_none() if row.team_id is not None else None
            if team is None or team.shared_user_id != row.requester_user_id:
                raise failure("team_required", "A registered team is required before supervisor assignment.", status.HTTP_422_UNPROCESSABLE_CONTENT)
            supervisor, policy = _lock_capacity(session, row.supervisor_id, cycle.id)
            _ensure_capacity(session, supervisor.id, cycle.id, policy, exclude_request_id=row.id)
            if session.scalar(select(SupervisorAssignment.id).where(SupervisorAssignment.team_id == team.id, SupervisorAssignment.ended_at.is_(None))) is not None:
                raise failure("team_already_assigned", "This team already has an active supervisor assignment.")
            assignment = SupervisorAssignment(team_id=team.id, academic_cycle_id=cycle.id, supervisor_id=actor.id, assigned_by_id=actor.id)
            session.add(assignment)
            session.flush()
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
    return StreamingResponse(BytesIO(document.content), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})


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
