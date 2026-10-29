"""Authorized Coordinator/Admin FYP student and proposal registry views."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import String, cast, exists, func, or_, select
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles, validate_mutating_origin
from .database import get_db
from .models import (
    AcademicCycle,
    AdminAuditEvent,
    ArchivedProject,
    FypRegistryMetadata,
    SupervisorAssignment,
    SupervisorRequest,
    SupervisorRequestDocument,
    SupervisorRequestMessage,
    SupervisorRequestStatusHistory,
    Team,
    TeamMember,
    User,
    UserRole,
)

router = APIRouter(prefix="/api/v1/fyp-registry")
REGISTRY_ROLES = (UserRole.ADMIN, UserRole.COORDINATOR, UserRole.SUPERVISOR, UserRole.STUDENT)
VALID_STATUSES = {"DRAFT", "SUBMITTED", "CHANGES_REQUESTED", "ACCEPTED", "REJECTED", "WITHDRAWN"}
NOT_AVAILABLE = "Not Available"
NO_PROGRESS = "Progress tracking is not configured yet."


class RegistryMetadataWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_section: str | None = Field(default=None, max_length=255)
    project_scope: str | None = Field(default=None, max_length=255)
    team_label: str | None = Field(default=None, max_length=255)
    administrative_notes: str | None = Field(default=None, max_length=4000)
    correction_reason: str = Field(min_length=1, max_length=2000)

    @field_validator("department_section", "project_scope", "team_label", "administrative_notes", "correction_reason")
    @classmethod
    def trim_values(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class RegistryRow(BaseModel):
    id: int
    student_or_team: str
    registration_number: str | None
    university_email: str | None
    academic_cycle: str | None
    department_section: str | None
    team_members: list[dict[str, Any]]
    proposal_title: str | None
    proposal_type: str
    proposal_status: str
    assigned_supervisor: str | None
    supervisor_decision: str
    request_submitted_at: datetime | None
    supervisor_decision_at: datetime | None
    last_updated_at: datetime
    completion_stage: str
    remaining_gaps: str
    assignment_status: str
    actions: list[str]


class RegistryDetail(RegistryRow):
    requester_user_id: int
    team_id: int | None
    academic_cycle_id: int
    supervisor_id: int
    proposal_summary: str | None
    original_proposal_pdf: dict[str, Any] | None
    extracted_proposal_fields: dict[str, Any]
    student_message: str | None
    supervisor_feedback: list[dict[str, Any]]
    conversation_history: list[dict[str, Any]]
    status_history: list[dict[str, Any]]
    submitted_reviewed_dates: dict[str, datetime | None]
    audit_history: list[dict[str, Any]]
    related_archived_reference_matches: list[dict[str, Any]]
    module03_compliance_report: dict[str, Any] | None
    administrative_notes: str | None
    correction_reason: str | None


def _error(code: str, message: str, code_status: int = status.HTTP_409_CONFLICT) -> HTTPException:
    return HTTPException(code_status, detail={"code": code, "message": message})


def _team_for_actor(session: Session, actor: User) -> Team | None:
    if actor.role != UserRole.STUDENT:
        return None
    return session.scalar(select(Team).where(Team.shared_user_id == actor.id).order_by(Team.id))


def _authorized_row(session: Session, row: SupervisorRequest, actor: User) -> bool:
    if actor.role in (UserRole.ADMIN, UserRole.COORDINATOR):
        return True
    if actor.role == UserRole.SUPERVISOR:
        return row.supervisor_id == actor.id
    if actor.role == UserRole.STUDENT:
        team = _team_for_actor(session, actor)
        return row.requester_user_id == actor.id or (team is not None and row.team_id == team.id)
    return False


def _metadata(session: Session, request_id: int) -> FypRegistryMetadata | None:
    return session.scalar(select(FypRegistryMetadata).where(FypRegistryMetadata.request_id == request_id))


def _members(session: Session, team_id: int | None) -> list[dict[str, Any]]:
    if team_id is None:
        return []
    rows = session.scalars(select(TeamMember).where(TeamMember.team_id == team_id).order_by(TeamMember.is_creator.desc(), TeamMember.id)).all()
    return [{"id": item.id, "full_name": item.full_name, "registration_number": item.registration_number, "university_email": item.university_email, "is_creator": item.is_creator, "is_active": item.is_active} for item in rows]


def _history(session: Session, request_id: int) -> list[dict[str, Any]]:
    rows = session.execute(select(SupervisorRequestStatusHistory, User.full_name).join(User, User.id == SupervisorRequestStatusHistory.actor_id).where(SupervisorRequestStatusHistory.request_id == request_id).order_by(SupervisorRequestStatusHistory.created_at, SupervisorRequestStatusHistory.id)).all()
    return [{"id": item.id, "from_status": item.from_status, "to_status": item.to_status, "comment": item.comment, "actor_name": name, "created_at": item.created_at} for item, name in rows]


def _conversation(session: Session, request_id: int) -> list[dict[str, Any]]:
    rows = session.execute(select(SupervisorRequestMessage, User.full_name, User.role).join(User, User.id == SupervisorRequestMessage.sender_id).where(SupervisorRequestMessage.request_id == request_id).order_by(SupervisorRequestMessage.id)).all()
    return [{"id": item.id, "sender_id": item.sender_id, "sender_name": name, "sender_role": role.value, "body": item.body, "created_at": item.created_at} for item, name, role in rows]


def _audit(session: Session, request_id: int) -> list[dict[str, Any]]:
    rows = session.scalars(select(AdminAuditEvent).where(AdminAuditEvent.target_type == "SUPERVISOR_REQUEST", AdminAuditEvent.target_id == request_id).order_by(AdminAuditEvent.created_at, AdminAuditEvent.id)).all()
    return [{"id": item.id, "action": item.action, "created_at": item.created_at, "changed_values": item.changed_values} for item in rows]


def _decision_dates(history: list[dict[str, Any]], row: SupervisorRequest) -> dict[str, datetime | None]:
    result: dict[str, datetime | None] = {"submitted": row.submitted_at, "reviewed": row.reviewed_at, "accepted": None, "changes_requested": None, "rejected": None}
    for item in history:
        if item["to_status"] in result and result[item["to_status"]] is None:
            result[item["to_status"]] = item["created_at"]
    return result


def _row(session: Session, row: SupervisorRequest) -> dict[str, Any]:
    requester = session.get(User, row.requester_user_id)
    cycle = session.get(AcademicCycle, row.academic_cycle_id)
    supervisor = session.get(User, row.supervisor_id)
    team = session.get(Team, row.team_id) if row.team_id is not None else None
    metadata = _metadata(session, row.id)
    assignment = session.scalar(select(SupervisorAssignment).where(SupervisorAssignment.team_id == row.team_id, SupervisorAssignment.academic_cycle_id == row.academic_cycle_id, SupervisorAssignment.ended_at.is_(None))) if row.team_id is not None else None
    history = _history(session, row.id)
    members = _members(session, row.team_id)
    title = row.title or None
    return {
        "id": row.id,
        "student_or_team": metadata.team_label if metadata and metadata.team_label else (team and f"Team {team.id}") or (requester.full_name if requester else NOT_AVAILABLE),
        "registration_number": requester.registration_number if requester else None,
        "university_email": requester.email if requester else None,
        "academic_cycle": cycle.display_name if cycle else None,
        "department_section": metadata.department_section if metadata else None,
        "team_members": members,
        "proposal_title": title,
        "proposal_type": "SUPERVISOR_REQUEST",
        "proposal_status": row.status,
        "assigned_supervisor": supervisor.full_name if supervisor else None,
        "supervisor_decision": row.status if row.status in {"ACCEPTED", "REJECTED", "CHANGES_REQUESTED"} else NOT_AVAILABLE,
        "request_submitted_at": row.submitted_at,
        "supervisor_decision_at": row.reviewed_at,
        "last_updated_at": row.updated_at,
        "completion_stage": NOT_AVAILABLE,
        "remaining_gaps": NO_PROGRESS,
        "assignment_status": "Assigned" if assignment else NOT_AVAILABLE,
        "actions": ["view"],
    }


def _detail(session: Session, row: SupervisorRequest) -> dict[str, Any]:
    result = _row(session, row)
    requester = session.get(User, row.requester_user_id)
    document = session.get(SupervisorRequestDocument, row.document_id) if row.document_id else None
    history = _history(session, row.id)
    conversation = _conversation(session, row.id)
    archived: list[dict[str, Any]] = []
    if row.title:
        archived_rows = session.scalars(select(ArchivedProject).where(ArchivedProject.is_active.is_(True), ArchivedProject.normalized_title.ilike(f"%{row.title.casefold()}%"), ArchivedProject.id != -1).limit(10)).all()
        archived = [{"id": item.id, "title": item.title, "academic_year": item.academic_year, "project_scope": item.project_scope, "source_label": item.source_label} for item in archived_rows]
    result.update({
        "requester_user_id": row.requester_user_id,
        "team_id": row.team_id,
        "academic_cycle_id": row.academic_cycle_id,
        "supervisor_id": row.supervisor_id,
        "proposal_summary": row.summary,
        "original_proposal_pdf": {"filename": document.filename, "document_url": f"/api/v1/supervisor-requests/document/{row.id}", "file_size": document.file_size, "page_count": document.page_count, "extraction_status": document.extraction_status} if document else None,
        "extracted_proposal_fields": document.extracted_fields if document else {},
        "student_message": row.submission_note,
        "supervisor_feedback": [item for item in history if item["actor_name"] != (requester.full_name if requester else None) and item["comment"]],
        "conversation_history": conversation,
        "status_history": history,
        "submitted_reviewed_dates": _decision_dates(history, row),
        "audit_history": _audit(session, row.id),
        "related_archived_reference_matches": archived,
        "module03_compliance_report": None,
        "administrative_notes": _metadata(session, row.id).administrative_notes if _metadata(session, row.id) else None,
        "correction_reason": _metadata(session, row.id).correction_reason if _metadata(session, row.id) else None,
    })
    return result


def _statement(session: Session, actor: User, *, academic_cycle_id: int | None, department_section: str | None, supervisor_id: int | None, student_status: str | None, proposal_status: str | None, assignment_status: str | None, completion_stage: str | None, from_date: datetime | None, to_date: datetime | None, search: str | None):
    statement = select(SupervisorRequest).order_by(SupervisorRequest.updated_at.desc(), SupervisorRequest.id.desc())
    if actor.role == UserRole.SUPERVISOR:
        statement = statement.where(
            exists(
                select(SupervisorAssignment.id).where(
                    SupervisorAssignment.team_id == SupervisorRequest.team_id,
                    SupervisorAssignment.supervisor_id == actor.id,
                    SupervisorAssignment.academic_cycle_id == SupervisorRequest.academic_cycle_id,
                    SupervisorAssignment.ended_at.is_(None),
                )
            )
        )
    elif actor.role == UserRole.STUDENT:
        team = _team_for_actor(session, actor)
        statement = statement.where(or_(SupervisorRequest.requester_user_id == actor.id, SupervisorRequest.team_id == team.id if team else False))
    if academic_cycle_id is not None:
        statement = statement.where(SupervisorRequest.academic_cycle_id == academic_cycle_id)
    if supervisor_id is not None:
        statement = statement.where(SupervisorRequest.supervisor_id == supervisor_id)
    if proposal_status is not None:
        if proposal_status not in VALID_STATUSES:
            raise _error("invalid_status", "Unknown proposal status.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        statement = statement.where(SupervisorRequest.status == proposal_status)
    if student_status is not None:
        active = student_status.casefold() in {"active", "enabled"}
        if student_status.casefold() not in {"active", "enabled", "inactive", "disabled"}:
            raise _error("invalid_student_status", "Unknown student status.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        statement = statement.where(
            exists(select(User.id).where(User.id == SupervisorRequest.requester_user_id, User.is_active.is_(active)))
        )
    if from_date is not None:
        statement = statement.where(SupervisorRequest.updated_at >= from_date)
    if to_date is not None:
        statement = statement.where(SupervisorRequest.updated_at <= to_date)
    if search:
        value = f"%{search.strip()}%"
        requester_match = exists(
            select(User.id).where(
                User.id == SupervisorRequest.requester_user_id,
                or_(
                    User.full_name.ilike(value),
                    User.email.ilike(value),
                    User.registration_number.ilike(value),
                ),
            )
        )
        team_match = exists(
            select(Team.id).where(
                Team.id == SupervisorRequest.team_id,
                cast(Team.id, String).ilike(value),
            )
        )
        metadata_match = exists(
            select(FypRegistryMetadata.request_id).where(
                FypRegistryMetadata.request_id == SupervisorRequest.id,
                or_(
                    FypRegistryMetadata.team_label.ilike(value),
                    FypRegistryMetadata.project_scope.ilike(value),
                ),
            )
        )
        statement = statement.where(or_(requester_match, SupervisorRequest.title.ilike(value), team_match, metadata_match))
    rows = session.scalars(statement).all()
    if department_section or completion_stage or assignment_status:
        filtered = []
        for row in rows:
            payload = _row(session, row)
            if department_section and (payload["department_section"] or "").casefold() != department_section.casefold():
                continue
            if completion_stage and payload["completion_stage"].casefold() != completion_stage.casefold():
                continue
            if assignment_status and payload["assignment_status"].casefold() != assignment_status.casefold():
                continue
            filtered.append(row)
        return filtered
    return rows


def _list(actor: User, session: Session, **filters: Any) -> list[dict[str, Any]]:
    return [_row(session, row) for row in _statement(session, actor, **filters)]


def _filters(academic_cycle_id: int | None, department_section: str | None, supervisor_id: int | None, student_status: str | None, proposal_status: str | None, assignment_status: str | None, completion_stage: str | None, from_date: datetime | None, to_date: datetime | None, search: str | None) -> dict[str, Any]:
    if from_date and to_date and from_date > to_date:
        raise _error("invalid_date_range", "Start date must not be after end date.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return {"academic_cycle_id": academic_cycle_id, "department_section": department_section, "supervisor_id": supervisor_id, "student_status": student_status, "proposal_status": proposal_status, "assignment_status": assignment_status, "completion_stage": completion_stage, "from_date": from_date, "to_date": to_date, "search": search}


def _list_endpoint(actor: User, session: Session, **filters: Any) -> list[dict[str, Any]]:
    return _list(actor, session, **filters)


@router.get("/coordinator", response_model=list[RegistryRow])
def coordinator_registry(academic_cycle_id: int | None = Query(None, gt=0), department_section: str | None = Query(None, max_length=255), supervisor_id: int | None = Query(None, gt=0), student_status: str | None = Query(None), proposal_status: str | None = Query(None, alias="status"), assignment_status: str | None = Query(None), completion_stage: str | None = Query(None), from_date: datetime | None = Query(None), to_date: datetime | None = Query(None), search: str | None = Query(None, max_length=255), actor: User = Depends(require_roles(UserRole.COORDINATOR)), session: Session = Depends(get_db)):
    return _list_endpoint(actor, session, **_filters(academic_cycle_id, department_section, supervisor_id, student_status, proposal_status, assignment_status, completion_stage, from_date, to_date, search))


@router.get("/admin", response_model=list[RegistryRow])
def admin_registry(academic_cycle_id: int | None = Query(None, gt=0), department_section: str | None = Query(None, max_length=255), supervisor_id: int | None = Query(None, gt=0), student_status: str | None = Query(None), proposal_status: str | None = Query(None, alias="status"), assignment_status: str | None = Query(None), completion_stage: str | None = Query(None), from_date: datetime | None = Query(None), to_date: datetime | None = Query(None), search: str | None = Query(None, max_length=255), actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    return _list_endpoint(actor, session, **_filters(academic_cycle_id, department_section, supervisor_id, student_status, proposal_status, assignment_status, completion_stage, from_date, to_date, search))


@router.get("/supervisor", response_model=list[RegistryRow])
def supervisor_registry(actor: User = Depends(require_roles(UserRole.SUPERVISOR)), session: Session = Depends(get_db)):
    return _list(actor, session, **_filters(None, None, None, None, None, None, None, None, None, None))


@router.get("/student", response_model=list[RegistryRow])
def student_registry(actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    return _list(actor, session, **_filters(None, None, None, None, None, None, None, None, None, None))


@router.get("/{request_id}/coordinator", response_model=RegistryDetail)
def coordinator_detail(request_id: int, actor: User = Depends(require_roles(UserRole.COORDINATOR)), session: Session = Depends(get_db)):
    row = session.get(SupervisorRequest, request_id)
    if row is None:
        raise _error("request_not_found", "Registry record was not found.", status.HTTP_404_NOT_FOUND)
    return _detail(session, row)


@router.get("/{request_id}/admin", response_model=RegistryDetail)
def admin_detail(request_id: int, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    row = session.get(SupervisorRequest, request_id)
    if row is None:
        raise _error("request_not_found", "Registry record was not found.", status.HTTP_404_NOT_FOUND)
    return _detail(session, row)


@router.get("/{request_id}/supervisor", response_model=RegistryDetail)
def supervisor_detail(request_id: int, actor: User = Depends(require_roles(UserRole.SUPERVISOR)), session: Session = Depends(get_db)):
    row = session.get(SupervisorRequest, request_id)
    if row is None or row.supervisor_id != actor.id:
        raise _error("registry_forbidden", "This registry record is outside your assigned scope.", status.HTTP_403_FORBIDDEN)
    return _detail(session, row)


@router.get("/{request_id}/student", response_model=RegistryDetail)
def student_detail(request_id: int, actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    row = session.get(SupervisorRequest, request_id)
    if row is None:
        raise _error("request_not_found", "Registry record was not found.", status.HTTP_404_NOT_FOUND)
    if not _authorized_row(session, row, actor):
        raise _error("registry_forbidden", "This registry record is outside your authorized scope.", status.HTTP_403_FORBIDDEN)
    return _detail(session, row)


@router.patch("/{request_id}/admin/metadata", response_model=RegistryDetail)
def update_admin_metadata(request_id: int, payload: RegistryMetadataWrite, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.execute(select(SupervisorRequest).where(SupervisorRequest.id == request_id).with_for_update()).scalar_one_or_none()
    if row is None:
        raise _error("request_not_found", "Registry record was not found.", status.HTTP_404_NOT_FOUND)
    before_record = _metadata(session, request_id)
    before = {key: getattr(before_record, key) if before_record else None for key in ("department_section", "project_scope", "team_label", "administrative_notes", "correction_reason")}
    record = before_record or FypRegistryMetadata(request_id=request_id, updated_by_id=actor.id)
    values = payload.model_dump()
    for key in before:
        setattr(record, key, values[key])
    record.updated_by_id = actor.id
    session.add(record)
    session.flush()
    from .main import add_admin_audit_event
    add_admin_audit_event(session, actor_id=actor.id, affected_user_id=row.requester_user_id, target_type="SUPERVISOR_REQUEST", target_id=row.id, action="fyp_registry_metadata_updated", changed_values={"before": before, "after": values})
    try:
        session.commit()
        session.refresh(row)
        return _detail(session, row)
    except Exception as error:
        session.rollback()
        raise _error("registry_update_failed", "Administrative registry metadata could not be saved.", status.HTTP_500_INTERNAL_SERVER_ERROR) from error
