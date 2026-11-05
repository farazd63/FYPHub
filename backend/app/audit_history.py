"""Read-only, allowlisted administrator audit history."""
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, literal, select, true
from sqlalchemy.orm import Session
from .auth import require_roles
from .database import get_db
from .models import AdminAuditEvent, User, UserRole

router = APIRouter(prefix="/api/v1/admin/audit-events")
# Historical and current writers' documented scalar keys; unknown data is withheld.
SAFE_KEYS = {
    "supervisor_request_document_uploaded": {"document_version", "extraction_status", "file_size"},
    "supervisor_request_extracted": {"document_version", "extraction_status", "file_size"},
    "supervisor_request_extraction_confirmed": {"document_version", "extraction_status"},
    "supervisor_request_draft_created": {"supervisor_id"},
    "supervisor_request_submitted": {"previous_status"},
    "supervisor_request_resubmitted": {"previous_status"},
    "supervisor_request_withdrawn": {"previous_status"},
    "supervisor_request_accepted": {"previous_status"},
    "supervisor_request_rejected": {"previous_status"},
    "supervisor_request_changes_requested": {"previous_status"},
    "supervisor_assignment_created": {"team_id", "academic_cycle_id", "supervisor_id"},
    "supervisor_assignment_ended": {"team_id", "academic_cycle_id", "supervisor_id"},
    "workflow_policy_version_created": {"version", "name", "state_count", "transition_count"},
    "student_roster_imported": {"academic_cycle_id", "record_count"},
    "account_created": {"email", "role", "is_active"},
    "account_status_changed": {"is_active", "previous_is_active"},
    "account_role_changed": {"role", "previous_role"},
    "password_reset_requested": {"identifier_type", "delivery"},
    "password_reset_completed": {"sessions_revoked"},
    "academic_cycle_created": {"code", "display_name", "registration_open"},
    "academic_cycle_updated": {"before", "after"},
    "group_policy_created": {"academic_cycle_id", "max_group_size", "previous_max_group_size"},
    "group_policy_updated": {"academic_cycle_id", "max_group_size", "previous_max_group_size"},
    "supervisor_capacity_created": {"academic_cycle_id", "max_group_capacity"},
    "supervisor_capacity_updated": {"before", "after"},
    "academic_rule_version_created": {"version", "provenance"},
    "evaluation_rubric_version_created": {"version", "name", "criteria"},
    "academic_deadline_version_created": {"academic_cycle_id", "version", "name", "due_at_utc", "time_zone", "utc_offset", "operational"},
    "reminder_rule_version_created": {"version", "academic_cycle_id", "deadline_version_id", "category", "direction", "elapsed_minutes", "operational"},
    "archived_project_created": {"source_label", "title", "academic_year"},
    "archived_project_updated": {"before", "after"},
    "archived_project_metadata_rolled_back": {"source_event_id", "before", "after"},
    "archived_project_activated": {"is_active"},
    "archived_project_deactivated": {"is_active"},
    "archived_project_document_uploaded": {"document_type", "version", "file_hash"},
    "fyp_registry_metadata_updated": {"before", "after"},
}
NESTED_KEYS = {"academic_cycle_updated": {"code", "display_name", "registration_open"}, "supervisor_capacity_updated": {"academic_cycle_id", "supervisor_id", "max_group_capacity"}, "archived_project_updated": {"title", "abstract_summary", "keywords", "academic_year", "department_program", "project_scope", "completion_stage", "implemented_scope", "remaining_gaps", "future_work", "supervisor_display_reference", "source_label", "source_metadata"}, "archived_project_metadata_rolled_back": {"title", "abstract_summary", "keywords", "academic_year", "department_program", "project_scope", "completion_stage", "implemented_scope", "remaining_gaps", "future_work", "supervisor_display_reference", "source_label", "source_metadata"}, "fyp_registry_metadata_updated": {"department_section", "project_scope", "team_label", "administrative_notes", "correction_reason"}}

def scalar(value: Any) -> bool:
    return value is None or type(value) in (str, int, float, bool)

def safe_changes(event: AdminAuditEvent) -> dict[str, Any]:
    raw = event.changed_values
    if not isinstance(raw, dict):
        return {}
    result: dict[str, Any] = {}
    for key in SAFE_KEYS.get(event.action, set()):
        if key not in raw:
            continue
        value = raw[key]
        if key in ("before", "after") and isinstance(value, dict):
            result[key] = {k: v for k, v in value.items() if k in NESTED_KEYS.get(event.action, set()) and scalar(v)}
        elif key == "criteria" and isinstance(value, list):
            result[key] = [{k: v for k, v in item.items() if k in {"name", "order"} and scalar(v)} for item in value if isinstance(item, dict)]
        elif scalar(value):
            result[key] = value
    return result

def output(event: AdminAuditEvent) -> dict[str, Any]:
    return {"id": event.id, "actor_id": event.actor_id, "affected_user_id": event.affected_user_id, "action": event.action, "target_type": event.target_type, "target_id": event.target_id, "created_at": event.created_at, "changed_values": safe_changes(event)}

def parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise HTTPException(status_code=422, detail={"code": "invalid_date_range", "message": "Dates must include a valid UTC offset."}) from None

@router.get("")
def list_events(request: Request, actor_id: int | None = Query(None, gt=0), action: str | None = Query(None, min_length=1, max_length=64), target_type: str | None = Query(None, min_length=1, max_length=32), target_id: int | None = Query(None, gt=0), from_at: str | None = Query(None, min_length=1, max_length=40), to_at: str | None = Query(None, min_length=1, max_length=40), page: int = Query(1, ge=1, le=1000000), page_size: int = Query(20, ge=1, le=100), _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    allowed = {"actor_id", "action", "target_type", "target_id", "from_at", "to_at", "page", "page_size"}
    if any(key not in allowed or len(request.query_params.getlist(key)) != 1 for key in request.query_params):
        raise HTTPException(status_code=422, detail={"code": "invalid_query", "message": "Invalid or duplicate filter."})
    if (action is not None and not action.strip()) or (target_type is not None and not target_type.strip()):
        raise HTTPException(status_code=422, detail={"code": "invalid_query", "message": "Filter values must not be blank."})
    start, end = parse_time(from_at), parse_time(to_at)
    if start and end and start > end:
        raise HTTPException(status_code=422, detail={"code": "invalid_date_range", "message": "Start must not be after end."})
    filters = []
    for column, value in ((AdminAuditEvent.actor_id, actor_id), (AdminAuditEvent.action, action), (AdminAuditEvent.target_type, target_type), (AdminAuditEvent.target_id, target_id)):
        if value is not None:
            filters.append(column == value)
    if start is not None: filters.append(AdminAuditEvent.created_at >= start)
    if end is not None: filters.append(AdminAuditEvent.created_at <= end)
    # Count and page share one statement snapshot, including when the page is empty.
    count = select(func.count()).select_from(AdminAuditEvent).where(*filters).scalar_subquery()
    page_ids = select(AdminAuditEvent.id).where(*filters).order_by(AdminAuditEvent.created_at.desc(), AdminAuditEvent.id.desc()).offset((page - 1) * page_size).limit(page_size).subquery()
    anchor = select(literal(1).label("one")).subquery()
    rows = session.execute(select(count, AdminAuditEvent).select_from(anchor).outerjoin(page_ids, true()).outerjoin(AdminAuditEvent, AdminAuditEvent.id == page_ids.c.id).order_by(AdminAuditEvent.created_at.desc(), AdminAuditEvent.id.desc())).all()
    total = rows[0][0]
    return {"items": [output(event) for _, event in rows if event is not None], "page": page, "page_size": page_size, "total": total, "total_pages": (total + page_size - 1) // page_size}

@router.get("/{event_id}")
def event_detail(event_id: int, _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    if event_id <= 0:
        raise HTTPException(status_code=422, detail={"code": "invalid_event_id", "message": "Event ID must be positive."})
    event = session.get(AdminAuditEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail={"code": "event_not_found", "message": "Audit event was not found."})
    return output(event)
