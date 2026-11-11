from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones
import json
import logging
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .database import engine, get_db
from .config import settings
from .models import AdminAuditEvent, AuthSession, Team, TeamMember, User, UserRole
from .models import AcademicCycle, AcademicGroupPolicy, SupervisorCapacityPolicy, SupervisorAssignment, SupervisorRequest, SupervisorRequestStatus
from .models import TemplateReference, TemplateReferenceVersion, AcademicRuleVersion, TemplateType
from .schemas.templates import TemplateCreate, TemplateVersionCreate, RuleCreate, TemplateListOut, TemplateOut, RuleOut, TemplateDetail
from .models import EvaluationRubric, EvaluationRubricCriterion, EvaluationRubricVersion
from .models import AcademicDeadline, AcademicDeadlineVersion
from .schemas.evaluation_rubrics import RubricDetailOut, RubricListOut, RubricVersionOut, RubricVersionWrite
from .schemas.academic_deadlines import DeadlineCreate, DeadlineDetailOut, DeadlineListOut, DeadlinePreviewOut, DeadlinePreviewRequest, DeadlineVersionOut, DeadlineWrite
from .dashboard_requirements import router as dashboard_requirements_router
from .document_requirements import router as document_requirements_router, student_router as student_document_requirements_router
from .coordinator_operations import router as coordinator_operations_router
from .academic_cycle_overview import router as academic_cycle_overview_router
from .schemas.academic import CycleCreate, CycleOut, CycleUpdate, PolicyOut, PolicyUpdate
from .schemas.auth import CurrentUserResponse, LoginRequest, RegistrationRequest, RegistrationResponse
from .schemas.admin_users import AdminUserCreate, AdminUserPage, AdminUserResponse, AdminUserRoleChange, AdminUserStatusChange
from .schemas.supervisor_capacity import CapacitySession, SupervisorCapacityOut, SupervisorCapacityWrite
from .schemas.team_registration import StudentGroupRegistrationRequest, TeamMemberInput, TeamRegistrationRequest, TeamRegistrationResponse
from .security import generate_session_token, hash_password, hash_session_token, validate_password, verify_password
from .registration_policy import DEMO_MODE_WARNING, RegistrationMode, registration_mode
from .project_workflow import router as project_workflow_router
from .evaluations import router as evaluations_router
from .modules.module_03_proposal.router import router as proposal_compliance_router
from .auth import (
    ALLOWED_BROWSER_ORIGINS,
    SESSION_COOKIE_NAME,
    SESSION_LIFETIME_HOURS,
    clear_session_cookie,
    get_current_user,
    require_roles,
    session_cookie_secure,
    set_session_cookie,
    utc_now,
    validate_mutating_origin,
    log_temporary_auth_diagnostic,
)

app = FastAPI(title="FYPHub API")
settings.document_storage_root.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("fyphub.request")


def _workflow_name(path: str) -> str:
    if "/proposals" in path: return "proposal"
    if "/agent-supervision" in path: return "supervision"
    if "/auth/" in path: return "auth"
    if "/academic-cycles" in path: return "academic_cycle"
    return "api"


class StructuredRequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.monotonic()
        path = request.url.path
        logger.info(json.dumps({"event": "request.start", "request_id": request_id, "method": request.method, "path": path, "workflow": _workflow_name(path), "stage": "request", "origin": request.headers.get("origin") if request.method == "OPTIONS" else None, "requested_method": request.headers.get("access-control-request-method") if request.method == "OPTIONS" else None}, separators=(",", ":")))
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.exception(json.dumps({"event": "request.failure", "request_id": request_id, "method": request.method, "path": path, "workflow": _workflow_name(path), "status": 500, "duration_ms": round((time.monotonic() - started) * 1000, 2), "failure_stage": "unhandled_exception", "error_type": type(exc).__name__}, separators=(",", ":")))
            raise
        response.headers["X-Request-ID"] = request_id
        status_code = response.status_code
        level = logging.ERROR if status_code >= 500 else logging.WARNING if status_code >= 400 else logging.INFO
        logger.log(level, json.dumps({"event": "request.complete", "request_id": request_id, "method": request.method, "path": path, "workflow": _workflow_name(path), "status": status_code, "duration_ms": round((time.monotonic() - started) * 1000, 2), "failure_stage": None if status_code < 400 else "response"}, separators=(",", ":")))
        return response


app.add_middleware(StructuredRequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_BROWSER_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Accept", "Authorization", "X-File-Name", "X-Preview-Token"],
)
app.include_router(document_requirements_router)
app.include_router(student_document_requirements_router)
app.include_router(coordinator_operations_router)
app.include_router(academic_cycle_overview_router)
app.include_router(proposal_compliance_router)

_DUMMY_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$FkrCX/M1V29q1Jj4yMHSiw$rONBAdg5KlI9DhIbVoDaHB3lM5HJXojJYVeAaLlbGwI"


@app.exception_handler(RequestValidationError)
async def request_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
    """Expose consistent, field-addressable request validation failures."""
    fields = []
    for item in error.errors():
        location = item.get("loc", ())
        path = ".".join(str(part) for part in location if part != "body")
        fields.append({"path": path, "code": item["type"]})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": {
                "code": "invalid_request",
                "message": "Request validation failed.",
                "fields": fields,
            }
        },
    )


def registration_error(
    status_code: int, code: str, message: str, field: str | None = None
) -> HTTPException:
    """Return a public, structured error without database implementation details."""
    detail: dict[str, str] = {"code": code, "message": message}
    if field is not None:
        detail["field"] = field
    return HTTPException(status_code=status_code, detail=detail)


def normalize_team_member(member: TeamMemberInput, path: str) -> dict[str, str | None]:
    """Apply the established identifier conventions and field-length rules."""
    full_name = member.full_name.strip()
    registration_number = member.registration_number.strip().upper()
    university_email = str(member.university_email).strip().lower() if member.university_email else None

    if not full_name or len(full_name) > 255:
        raise registration_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_full_name",
            "Full name must be between 1 and 255 non-whitespace characters.",
            f"{path}.full_name",
        )
    if not registration_number or len(registration_number) > 100:
        raise registration_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_registration_number",
            "Registration number must be between 1 and 100 non-whitespace characters.",
            f"{path}.registration_number",
        )
    if university_email is not None and len(university_email) > 320:
        raise registration_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_university_email",
            "University email must not exceed 320 characters.",
            f"{path}.university_email",
        )
    return {
        "full_name": full_name,
        "registration_number": registration_number,
        "university_email": university_email,
    }

@app.get("/api/v1/academic-cycles",response_model=list[CycleOut])
def list_cycles(session:Session=Depends(get_db))->list[AcademicCycle]:
 return list(session.query(AcademicCycle).order_by(AcademicCycle.id).all())

@app.get("/api/v1/academic-cycles/{cycle_id}/group-policy",response_model=PolicyOut)
def get_group_policy(cycle_id:int,session:Session=Depends(get_db))->AcademicGroupPolicy:
 cycle=session.get(AcademicCycle,cycle_id)
 if cycle is None: raise HTTPException(status_code=404,detail="Academic cycle not found.")
 if cycle.group_policy is None: raise HTTPException(status_code=404,detail="Academic group policy not configured.")
 return cycle.group_policy


def cycle_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def locked_cycle_and_policy(session: Session, cycle_id: int) -> tuple[AcademicCycle, AcademicGroupPolicy | None]:
    """Use the same cycle-then-policy lock order as team registration."""
    cycle = session.execute(select(AcademicCycle).where(AcademicCycle.id == cycle_id).with_for_update()).scalar_one_or_none()
    if cycle is None:
        raise cycle_error(status.HTTP_404_NOT_FOUND, "cycle_not_found", "Academic cycle was not found.")
    policy = session.execute(select(AcademicGroupPolicy).where(AcademicGroupPolicy.academic_cycle_id == cycle.id).with_for_update()).scalar_one_or_none()
    return cycle, policy


def largest_active_team_size(session: Session, cycle_id: int) -> int:
    sizes = session.execute(select(func.count(TeamMember.id)).where(TeamMember.academic_cycle_id == cycle_id, TeamMember.is_active.is_(True)).group_by(TeamMember.team_id)).scalars().all()
    return max(sizes, default=0)


def deadline_error(status_code: int, code: str, message: str, **extra: object) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message, **extra})


def formatted_utc_offset(value: timedelta) -> str:
    minutes = int(value.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    minutes = abs(minutes)
    return f"{sign}{minutes // 60:02d}:{minutes % 60:02d}"


def require_timezone_data() -> None:
    try:
        ZoneInfo("UTC")
    except ZoneInfoNotFoundError as error:
        raise deadline_error(status.HTTP_503_SERVICE_UNAVAILABLE, "timezone_data_unavailable", "Timezone data is unavailable; contact the service administrator.") from error


def resolve_deadline_time(payload: DeadlinePreviewRequest) -> tuple[datetime, str, str]:
    """Resolve a wall time without guessing a zone, gap, or overlapping offset."""
    require_timezone_data()
    try:
        zone = ZoneInfo(payload.time_zone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise deadline_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_time_zone", "Select a valid IANA time zone.") from error
    wall = datetime.fromisoformat(payload.local_due_at)
    candidates: dict[str, datetime] = {}
    for fold in (0, 1):
        localized = wall.replace(tzinfo=zone, fold=fold)
        utc_value = localized.astimezone(timezone.utc)
        round_trip = utc_value.astimezone(zone)
        if round_trip.replace(tzinfo=None) == wall:
            offset = formatted_utc_offset(localized.utcoffset() or timedelta())
            candidates[offset] = utc_value
    valid_offsets = sorted(candidates)
    if not valid_offsets:
        raise deadline_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "nonexistent_local_time", "That local time does not exist in the selected time zone.")
    if len(valid_offsets) > 1 and payload.utc_offset is None:
        raise deadline_error(status.HTTP_409_CONFLICT, "ambiguous_local_time", "Choose the intended UTC offset for this ambiguous local time.", valid_offsets=valid_offsets)
    selected_offset = payload.utc_offset or valid_offsets[0]
    if selected_offset not in candidates:
        raise deadline_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "offset_timezone_mismatch", "The UTC offset does not match that local time and time zone.", valid_offsets=valid_offsets)
    return candidates[selected_offset], selected_offset, wall.isoformat(timespec="minutes" if wall.second == 0 else "seconds")


def deadline_version_out(version: AcademicDeadlineVersion) -> dict[str, object]:
    require_timezone_data()
    try:
        zone = ZoneInfo(version.time_zone)
    except ZoneInfoNotFoundError as error:
        raise deadline_error(status.HTTP_503_SERVICE_UNAVAILABLE, "timezone_data_unavailable", "Timezone data is unavailable; contact the service administrator.") from error
    local = version.due_at_utc.astimezone(zone)
    return {
        "id": version.id,
        "version_number": version.version_number,
        "name": version.name,
        "description": version.description,
        "due_at_utc": version.due_at_utc,
        "local_due_at": local.replace(tzinfo=None).isoformat(timespec="minutes" if local.second == 0 else "seconds"),
        "time_zone": version.time_zone,
        "utc_offset": formatted_utc_offset(local.utcoffset() or timedelta()),
        "created_at": version.created_at,
    }


def deadline_detail_out(session: Session, deadline: AcademicDeadline) -> dict[str, object]:
    cycle = session.get(AcademicCycle, deadline.academic_cycle_id)
    versions = session.execute(
        select(AcademicDeadlineVersion)
        .where(AcademicDeadlineVersion.academic_deadline_id == deadline.id)
        .order_by(AcademicDeadlineVersion.version_number)
    ).scalars().all()
    return {
        "id": deadline.id,
        "academic_cycle_id": deadline.academic_cycle_id,
        "academic_cycle_name": cycle.display_name if cycle else "Unavailable cycle",
        "created_at": deadline.created_at,
        "versions": [deadline_version_out(version) for version in versions],
    }


def validate_deadline_write(payload: DeadlineWrite) -> tuple[datetime, str]:
    due_at_utc, selected_offset, _ = resolve_deadline_time(payload)
    submitted_utc = payload.due_at_utc.astimezone(timezone.utc)
    if submitted_utc != due_at_utc:
        raise deadline_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "deadline_preview_mismatch", "The canonical due time no longer matches the local-time preview.")
    return due_at_utc, selected_offset


def save_deadline_version(session: Session, deadline: AcademicDeadline, payload: DeadlineWrite, actor: User, number: int) -> AcademicDeadlineVersion:
    due_at_utc, selected_offset = validate_deadline_write(payload)
    version = AcademicDeadlineVersion(
        academic_deadline_id=deadline.id,
        version_number=number,
        name=payload.name,
        description=payload.description,
        due_at_utc=due_at_utc,
        time_zone=payload.time_zone,
        created_by_id=actor.id,
    )
    session.add(version)
    session.flush()
    add_admin_audit_event(
        session,
        actor_id=actor.id,
        affected_user_id=None,
        target_type="ACADEMIC_DEADLINE",
        target_id=deadline.id,
        action="academic_deadline_version_created",
        changed_values={
            "academic_cycle_id": deadline.academic_cycle_id,
            "version": number,
            "name": payload.name,
            "due_at_utc": due_at_utc.isoformat(),
            "time_zone": payload.time_zone,
            "utc_offset": selected_offset,
            "operational": False,
        },
    )
    return version


@app.get("/api/v1/admin/time-zones", response_model=list[str])
def list_time_zones(_: User = Depends(require_roles(UserRole.ADMIN))) -> list[str]:
    require_timezone_data()
    return sorted(available_timezones())


@app.post("/api/v1/admin/academic-deadlines/preview", response_model=DeadlinePreviewOut)
def preview_academic_deadline(
    payload: DeadlinePreviewRequest,
    request: Request,
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> dict[str, object]:
    validate_mutating_origin(request)
    due_at_utc, selected_offset, normalized_local = resolve_deadline_time(payload)
    return {"local_due_at": normalized_local, "time_zone": payload.time_zone, "utc_offset": selected_offset, "due_at_utc": due_at_utc}


@app.get("/api/v1/admin/academic-deadlines", response_model=list[DeadlineListOut])
def list_academic_deadlines(
    academic_cycle_id: int | None = None,
    _: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    if academic_cycle_id is not None and session.get(AcademicCycle, academic_cycle_id) is None:
        raise deadline_error(status.HTTP_404_NOT_FOUND, "cycle_not_found", "Academic cycle was not found.")
    latest = (
        select(AcademicDeadlineVersion.academic_deadline_id, func.max(AcademicDeadlineVersion.version_number).label("number"))
        .group_by(AcademicDeadlineVersion.academic_deadline_id)
        .subquery()
    )
    statement = (
        select(AcademicDeadline, AcademicDeadlineVersion, AcademicCycle, latest.c.number)
        .join(AcademicCycle, AcademicCycle.id == AcademicDeadline.academic_cycle_id)
        .join(latest, latest.c.academic_deadline_id == AcademicDeadline.id)
        .join(AcademicDeadlineVersion, (AcademicDeadlineVersion.academic_deadline_id == AcademicDeadline.id) & (AcademicDeadlineVersion.version_number == latest.c.number))
        .order_by(AcademicDeadline.id)
    )
    if academic_cycle_id is not None:
        statement = statement.where(AcademicDeadline.academic_cycle_id == academic_cycle_id)
    rows = session.execute(statement).all()
    return [
        {
            "id": deadline.id,
            "academic_cycle_id": deadline.academic_cycle_id,
            "academic_cycle_name": cycle.display_name,
            "latest_version_number": number,
            **{key: value for key, value in deadline_version_out(version).items() if key not in {"id", "version_number", "created_at"}},
        }
        for deadline, version, cycle, number in rows
    ]


@app.get("/api/v1/admin/academic-deadlines/{deadline_id}", response_model=DeadlineDetailOut)
def academic_deadline_detail(
    deadline_id: int,
    _: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    deadline = session.get(AcademicDeadline, deadline_id)
    if deadline is None:
        raise deadline_error(status.HTTP_404_NOT_FOUND, "deadline_not_found", "Academic deadline was not found.")
    return deadline_detail_out(session, deadline)


@app.post("/api/v1/admin/academic-deadlines", status_code=status.HTTP_201_CREATED, response_model=DeadlineDetailOut)
def create_academic_deadline(
    payload: DeadlineCreate,
    request: Request,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    validate_mutating_origin(request)
    cycle = session.execute(select(AcademicCycle).where(AcademicCycle.id == payload.academic_cycle_id).with_for_update()).scalar_one_or_none()
    if cycle is None:
        raise deadline_error(status.HTTP_404_NOT_FOUND, "cycle_not_found", "Academic cycle was not found.")
    try:
        deadline = AcademicDeadline(academic_cycle_id=cycle.id)
        session.add(deadline)
        session.flush()
        save_deadline_version(session, deadline, payload, actor, 1)
        session.commit()
        session.refresh(deadline)
        return deadline_detail_out(session, deadline)
    except HTTPException:
        session.rollback()
        raise
    except SQLAlchemyError as error:
        session.rollback()
        raise deadline_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "deadline_save_failed", "Academic deadline could not be saved.") from error
    except Exception as error:
        session.rollback()
        raise deadline_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "deadline_save_failed", "Academic deadline could not be saved.") from error


@app.post("/api/v1/admin/academic-deadlines/{deadline_id}/versions", status_code=status.HTTP_201_CREATED, response_model=DeadlineVersionOut)
def create_academic_deadline_version(
    deadline_id: int,
    payload: DeadlineWrite,
    request: Request,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    validate_mutating_origin(request)
    identity = session.get(AcademicDeadline, deadline_id)
    if identity is None:
        raise deadline_error(status.HTTP_404_NOT_FOUND, "deadline_not_found", "Academic deadline was not found.")
    session.execute(select(AcademicCycle).where(AcademicCycle.id == identity.academic_cycle_id).with_for_update()).scalar_one()
    session.execute(text("SELECT pg_advisory_xact_lock(98138, :deadline_id)"), {"deadline_id": deadline_id})
    deadline = session.execute(select(AcademicDeadline).where(AcademicDeadline.id == deadline_id).with_for_update()).scalar_one()
    number = (session.execute(select(func.max(AcademicDeadlineVersion.version_number)).where(AcademicDeadlineVersion.academic_deadline_id == deadline.id)).scalar_one() or 0) + 1
    try:
        version = save_deadline_version(session, deadline, payload, actor, number)
        session.commit()
        session.refresh(version)
        return deadline_version_out(version)
    except HTTPException:
        session.rollback()
        raise
    except SQLAlchemyError as error:
        session.rollback()
        raise deadline_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "deadline_save_failed", "Academic deadline version could not be saved.") from error
    except Exception as error:
        session.rollback()
        raise deadline_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "deadline_save_failed", "Academic deadline version could not be saved.") from error


@app.delete("/api/v1/admin/academic-deadlines/{deadline_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_academic_deadline(
    deadline_id: int,
    request: Request,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> Response:
    """Remove a deadline and its recorded versions when no rule references it."""
    validate_mutating_origin(request)
    deadline = session.get(AcademicDeadline, deadline_id)
    if deadline is None:
        raise deadline_error(status.HTTP_404_NOT_FOUND, "deadline_not_found", "Academic deadline was not found.")
    referenced = session.scalar(
        select(ReminderRuleVersion.id).where(
            ReminderRuleVersion.deadline_version_id.in_(
                select(AcademicDeadlineVersion.id).where(AcademicDeadlineVersion.academic_deadline_id == deadline_id)
            )
        ).limit(1)
    )
    if referenced is not None:
        raise deadline_error(status.HTTP_409_CONFLICT, "deadline_in_use", "This deadline is referenced by a reminder rule; remove that rule first.")
    try:
        session.execute(delete(AcademicDeadlineVersion).where(AcademicDeadlineVersion.academic_deadline_id == deadline_id))
        session.delete(deadline)
        add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type="ACADEMIC_DEADLINE", target_id=deadline_id, action="academic_deadline_deleted", changed_values={})
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise deadline_error(status.HTTP_409_CONFLICT, "deadline_in_use", "This deadline is referenced by other configuration and cannot be deleted.") from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.get("/api/v1/admin/template-references", response_model=list[TemplateListOut])
def list_template_references(_: User=Depends(require_roles(UserRole.ADMIN)), session: Session=Depends(get_db)):
 return [
  {"reference_id": reference_id, **TemplateOut.model_validate(version).model_dump()}
  for version, reference_id in session.execute(
   select(TemplateReferenceVersion, TemplateReference.id)
   .join(TemplateReference, TemplateReference.id == TemplateReferenceVersion.template_reference_id)
   .order_by(TemplateReference.id, TemplateReferenceVersion.version_number)
  ).all()
 ]
@app.get("/api/v1/admin/template-references/{reference_id}",response_model=TemplateDetail)
def template_reference_detail(
    reference_id: int,
    _: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    reference = session.get(TemplateReference, reference_id)
    if reference is None:
        raise cycle_error(404, "template_reference_not_found", "Template reference was not found.")
    versions = session.execute(
        select(TemplateReferenceVersion)
        .where(TemplateReferenceVersion.template_reference_id == reference.id)
        .order_by(TemplateReferenceVersion.version_number)
    ).scalars().all()
    return {
        "reference_id": reference.id,
        "template_type": reference.template_type,
        "versions": [
            {
                "template": version,
                "rules": session.execute(
                    select(AcademicRuleVersion)
                    .where(AcademicRuleVersion.template_reference_version_id == version.id)
                    .order_by(AcademicRuleVersion.version_number)
                ).scalars().all(),
            }
            for version in versions
        ],
    }
@app.post("/api/v1/admin/template-references",status_code=201,response_model=TemplateDetail)
def create_template_reference(payload:TemplateCreate,request:Request,actor:User=Depends(require_roles(UserRole.ADMIN)),session:Session=Depends(get_db)):
 validate_mutating_origin(request)
 try:
  session.execute(text("SELECT pg_advisory_xact_lock(98137242)"))
  root = session.scalar(select(TemplateReference).where(TemplateReference.template_type == payload.template_type))
  if root is None:
   root = TemplateReference(template_type=payload.template_type)
   session.add(root)
   session.flush()
  number = (session.execute(select(func.max(TemplateReferenceVersion.version_number)).where(TemplateReferenceVersion.template_reference_id == root.id)).scalar_one() or 0) + 1
  ref = TemplateReferenceVersion(template_reference_id=root.id, version_number=number, title=payload.title.strip(), provenance=payload.provenance, source_note=payload.source_note.strip(), created_by_id=actor.id)
  session.add(ref)
  session.flush()
  rule = AcademicRuleVersion(template_reference_version_id=ref.id, version_number=1, provenance=payload.provenance, rules=payload.rules.model_dump(exclude_none=True), created_by_id=actor.id)
  session.add(rule)
  add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type="TEMPLATE_REFERENCE", target_id=ref.id, action="template_reference_version_created", changed_values={"template_type": payload.template_type.value, "version": number, "provenance": payload.provenance})
  session.commit()
  session.refresh(ref)
  session.refresh(rule)
  return {"reference_id": root.id, "template_type": root.template_type, "versions": [{"template": ref, "rules": [rule]}]}
 except Exception as error:
  session.rollback()
  raise HTTPException(status_code=500, detail="Template reference could not be saved.") from error
@app.post("/api/v1/admin/template-references/{reference_id}/versions",status_code=201,response_model=TemplateOut)
def create_template_version(reference_id:int,payload:TemplateVersionCreate,request:Request,actor:User=Depends(require_roles(UserRole.ADMIN)),session:Session=Depends(get_db)):
 validate_mutating_origin(request); root=session.get(TemplateReference,reference_id)
 if root is None: raise cycle_error(404,"template_reference_not_found","Template reference was not found.")
 try:
  session.execute(text("SELECT pg_advisory_xact_lock(98137242)")); number=(session.execute(select(func.max(TemplateReferenceVersion.version_number)).where(TemplateReferenceVersion.template_reference_id==root.id)).scalar_one() or 0)+1; ref=TemplateReferenceVersion(template_reference_id=root.id,version_number=number,title=payload.title.strip(),provenance=payload.provenance,source_note=payload.source_note.strip(),created_by_id=actor.id); session.add(ref); session.flush(); add_admin_audit_event(session,actor_id=actor.id,affected_user_id=None,target_type="TEMPLATE_REFERENCE",target_id=ref.id,action="template_reference_version_created",changed_values={"version":number}); session.commit(); session.refresh(ref); return ref
 except Exception as error: session.rollback(); raise HTTPException(status_code=500,detail="Template reference could not be saved.") from error
@app.post("/api/v1/admin/template-reference-versions/{version_id}/rules",status_code=201,response_model=RuleOut)
def create_rule_version(version_id:int,payload:RuleCreate,request:Request,actor:User=Depends(require_roles(UserRole.ADMIN)),session:Session=Depends(get_db)):
 validate_mutating_origin(request); ref=session.get(TemplateReferenceVersion,version_id)
 if ref is None: raise cycle_error(404,"template_version_not_found","Template version was not found.")
 try:
  number=(session.execute(select(func.max(AcademicRuleVersion.version_number)).where(AcademicRuleVersion.template_reference_version_id==ref.id)).scalar_one() or 0)+1; rule=AcademicRuleVersion(template_reference_version_id=ref.id,version_number=number,provenance=payload.provenance,rules=payload.rules.model_dump(exclude_none=True),created_by_id=actor.id); session.add(rule); session.flush(); add_admin_audit_event(session,actor_id=actor.id,affected_user_id=None,target_type="ACADEMIC_RULE_VERSION",target_id=rule.id,action="academic_rule_version_created",changed_values={"version":number,"provenance":payload.provenance}); session.commit(); session.refresh(rule); return rule
 except Exception as error: session.rollback(); raise HTTPException(status_code=500,detail="Academic rule version could not be saved.") from error


@app.delete("/api/v1/admin/template-reference-versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template_reference_version(version_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> Response:
    validate_mutating_origin(request)
    version = session.get(TemplateReferenceVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail={"code": "template_version_not_found", "message": "Template version was not found."})
    if version.is_active:
        raise HTTPException(status_code=409, detail={"code": "template_active", "message": "Deactivate the active template before deleting it."})
    try:
        session.execute(delete(AcademicRuleVersion).where(AcademicRuleVersion.template_reference_version_id == version_id))
        session.delete(version)
        add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type="TEMPLATE_REFERENCE", target_id=version_id, action="template_reference_version_deleted", changed_values={})
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail={"code": "template_in_use", "message": "This template version is referenced by historical submissions and cannot be deleted."}) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def rubric_version_out(session: Session, version: EvaluationRubricVersion) -> dict[str, object]:
    criteria = session.execute(
        select(EvaluationRubricCriterion)
        .where(EvaluationRubricCriterion.rubric_version_id == version.id)
        .order_by(EvaluationRubricCriterion.display_order, EvaluationRubricCriterion.id)
    ).scalars().all()
    return {
        "id": version.id,
        "version_number": version.version_number,
        "name": version.name,
        "description": version.description,
        "created_at": version.created_at,
        "criteria": [
            {"id": item.id, "name": item.name, "description": item.description, "order": item.display_order}
            for item in criteria
        ],
    }


def rubric_detail_out(session: Session, rubric: EvaluationRubric) -> dict[str, object]:
    versions = session.execute(
        select(EvaluationRubricVersion)
        .where(EvaluationRubricVersion.rubric_id == rubric.id)
        .order_by(EvaluationRubricVersion.version_number)
    ).scalars().all()
    return {
        "id": rubric.id,
        "created_at": rubric.created_at,
        "versions": [rubric_version_out(session, version) for version in versions],
    }


def save_rubric_version(
    session: Session,
    rubric: EvaluationRubric,
    payload: RubricVersionWrite,
    actor: User,
    version_number: int,
) -> EvaluationRubricVersion:
    version = EvaluationRubricVersion(
        rubric_id=rubric.id,
        version_number=version_number,
        name=payload.name,
        description=payload.description,
        created_by_id=actor.id,
    )
    session.add(version)
    session.flush()
    session.add_all([
        EvaluationRubricCriterion(
            rubric_version_id=version.id,
            name=criterion.name,
            description=criterion.description,
            display_order=criterion.order,
        )
        for criterion in payload.criteria
    ])
    session.flush()
    add_admin_audit_event(
        session,
        actor_id=actor.id,
        affected_user_id=None,
        target_type="EVALUATION_RUBRIC",
        target_id=rubric.id,
        action="evaluation_rubric_version_created",
        changed_values={
            "version": version_number,
            "name": payload.name,
            "criteria": [{"name": item.name, "order": item.order} for item in payload.criteria],
            "status": "DRAFT",
        },
    )
    return version


@app.get("/api/v1/admin/evaluation-rubrics", response_model=list[RubricListOut])
def list_evaluation_rubrics(
    _: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    latest = (
        select(
            EvaluationRubricVersion.rubric_id,
            func.max(EvaluationRubricVersion.version_number).label("latest_version_number"),
        )
        .group_by(EvaluationRubricVersion.rubric_id)
        .subquery()
    )
    rows = session.execute(
        select(EvaluationRubric, EvaluationRubricVersion, latest.c.latest_version_number)
        .join(latest, latest.c.rubric_id == EvaluationRubric.id)
        .join(
            EvaluationRubricVersion,
            (EvaluationRubricVersion.rubric_id == EvaluationRubric.id)
            & (EvaluationRubricVersion.version_number == latest.c.latest_version_number),
        )
        .order_by(EvaluationRubric.id)
    ).all()
    return [
        {
            "id": rubric.id,
            "name": version.name,
            "description": version.description,
            "latest_version_number": number,
            "created_at": rubric.created_at,
        }
        for rubric, version, number in rows
    ]


@app.get("/api/v1/admin/evaluation-rubrics/{rubric_id}", response_model=RubricDetailOut)
def evaluation_rubric_detail(
    rubric_id: int,
    _: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    rubric = session.get(EvaluationRubric, rubric_id)
    if rubric is None:
        raise cycle_error(status.HTTP_404_NOT_FOUND, "rubric_not_found", "Evaluation criteria were not found.")
    return rubric_detail_out(session, rubric)


@app.post("/api/v1/admin/evaluation-rubrics", status_code=status.HTTP_201_CREATED, response_model=RubricDetailOut)
def create_evaluation_rubric(
    payload: RubricVersionWrite,
    request: Request,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    validate_mutating_origin(request)
    try:
        rubric = EvaluationRubric()
        session.add(rubric)
        session.flush()
        save_rubric_version(session, rubric, payload, actor, 1)
        session.commit()
        session.refresh(rubric)
        return rubric_detail_out(session, rubric)
    except (IntegrityError, SQLAlchemyError) as error:
        session.rollback()
        raise cycle_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "rubric_save_failed", "Evaluation criteria could not be saved.") from error
    except Exception as error:
        session.rollback()
        raise cycle_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "rubric_save_failed", "Evaluation criteria could not be saved.") from error


@app.post("/api/v1/admin/evaluation-rubrics/{rubric_id}/versions", status_code=status.HTTP_201_CREATED, response_model=RubricVersionOut)
def create_evaluation_rubric_version(
    rubric_id: int,
    payload: RubricVersionWrite,
    request: Request,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    validate_mutating_origin(request)
    try:
        session.execute(text("SELECT pg_advisory_xact_lock(98137, :rubric_id)"), {"rubric_id": rubric_id})
        rubric = session.execute(
            select(EvaluationRubric).where(EvaluationRubric.id == rubric_id).with_for_update()
        ).scalar_one_or_none()
        if rubric is None:
            raise cycle_error(status.HTTP_404_NOT_FOUND, "rubric_not_found", "Evaluation criteria were not found.")
        version_number = (
            session.execute(
                select(func.max(EvaluationRubricVersion.version_number)).where(EvaluationRubricVersion.rubric_id == rubric.id)
            ).scalar_one()
            or 0
        ) + 1
        version = save_rubric_version(session, rubric, payload, actor, version_number)
        session.commit()
        session.refresh(version)
        return rubric_version_out(session, version)
    except HTTPException:
        session.rollback()
        raise
    except (IntegrityError, SQLAlchemyError) as error:
        session.rollback()
        raise cycle_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "rubric_save_failed", "Evaluation criteria version could not be saved.") from error
    except Exception as error:
        session.rollback()
        raise cycle_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "rubric_save_failed", "Evaluation criteria version could not be saved.") from error


@app.post("/api/v1/admin/academic-cycles", status_code=status.HTTP_201_CREATED, response_model=CycleOut)
def create_cycle(payload: CycleCreate, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> AcademicCycle:
    validate_mutating_origin(request)
    cycle_code = f"{payload.academic_year}-{payload.session.value}"
    display_name = f"{payload.session.value.title()} {payload.academic_year}"
    cycle = AcademicCycle(code=cycle_code, display_name=display_name, academic_year=payload.academic_year, session=payload.session.value, registration_open=False)
    session.add(cycle)
    try:
        session.flush()
        add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type="ACADEMIC_CYCLE", target_id=cycle.id, action="academic_cycle_created", changed_values={"academic_year": cycle.academic_year, "session": cycle.session, "code": cycle.code, "display_name": cycle.display_name, "registration_open": False})
        session.commit(); session.refresh(cycle)
    except IntegrityError as error:
        session.rollback()
        raise cycle_error(status.HTTP_409_CONFLICT, "duplicate_cycle_code", "An academic cycle with that code already exists.") from error
    return cycle


@app.patch("/api/v1/admin/academic-cycles/{cycle_id}", response_model=CycleOut)
def update_cycle(cycle_id: int, payload: CycleUpdate, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> AcademicCycle:
    validate_mutating_origin(request)
    cycle, policy = locked_cycle_and_policy(session, cycle_id)
    values = payload.model_dump(exclude_unset=True)
    if "session" in values:
        values["session"] = payload.session.value
    year = values.get("academic_year", cycle.academic_year)
    term = values.get("session", cycle.session)
    if (values.get("registration_open") or {"academic_year", "session"}.intersection(values)) and (year is None or not term):
        raise cycle_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "academic_cycle_metadata_missing", "Set the academic year and session before opening registration.")
    if values.get("registration_open") and policy is None:
        raise cycle_error(status.HTTP_409_CONFLICT, "group_policy_required", "Registration cannot open without a group-size policy.")
    if not values:
        return cycle
    before = {key: getattr(cycle, key) for key in values}
    for key, value in values.items(): setattr(cycle, key, value)
    try:
        add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type="ACADEMIC_CYCLE", target_id=cycle.id, action="academic_cycle_updated", changed_values={"before": before, "after": values})
        session.commit(); session.refresh(cycle)
    except IntegrityError as error:
        session.rollback()
        raise cycle_error(status.HTTP_409_CONFLICT, "duplicate_cycle_code", "An academic cycle with that code already exists.") from error
    return cycle


@app.delete("/api/v1/admin/academic-cycles/{cycle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cycle(cycle_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> Response:
    validate_mutating_origin(request)
    cycle = session.execute(select(AcademicCycle).where(AcademicCycle.id == cycle_id).with_for_update()).scalar_one_or_none()
    if cycle is None:
        raise cycle_error(status.HTTP_404_NOT_FOUND, "cycle_not_found", "Academic cycle was not found.")
    if cycle.registration_open:
        raise cycle_error(status.HTTP_409_CONFLICT, "cycle_open", "Close registration before deleting this academic cycle.")
    try:
        session.delete(cycle)
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise cycle_error(status.HTTP_409_CONFLICT, "cycle_in_use", "This academic cycle has related records and cannot be deleted.") from error
    add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type="ACADEMIC_CYCLE", target_id=cycle_id, action="academic_cycle_deleted", changed_values={"academic_year": cycle.academic_year, "session": cycle.session})
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.put("/api/v1/admin/academic-cycles/{cycle_id}/group-policy", response_model=PolicyOut)
def set_group_policy(cycle_id: int, payload: PolicyUpdate, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> AcademicGroupPolicy:
    validate_mutating_origin(request)
    cycle, policy = locked_cycle_and_policy(session, cycle_id)
    largest = largest_active_team_size(session, cycle.id)
    if payload.min_group_size > payload.max_group_size:
        raise cycle_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_group_size_range", "Minimum group size cannot exceed maximum group size.")
    if payload.max_group_size < largest:
        raise cycle_error(status.HTTP_409_CONFLICT, "existing_team_exceeds_limit", "Existing active team membership exceeds that maximum.")
    created = policy is None
    if policy is None:
        policy = AcademicGroupPolicy(academic_cycle_id=cycle.id, max_group_size=payload.max_group_size, min_group_size=payload.min_group_size, formation_deadline=payload.formation_deadline, matching_weights=payload.matching_weights); session.add(policy); session.flush()
    else:
        previous = policy.max_group_size; policy.max_group_size = payload.max_group_size; policy.min_group_size = payload.min_group_size; policy.formation_deadline = payload.formation_deadline; policy.matching_weights = payload.matching_weights
    add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type="ACADEMIC_GROUP_POLICY", target_id=policy.id, action="group_policy_created" if created else "group_policy_updated", changed_values={"academic_cycle_id": cycle.id, "max_group_size": payload.max_group_size, "previous_max_group_size": None if created else previous})
    session.commit(); session.refresh(policy)
    return policy


@app.delete("/api/v1/admin/academic-cycles/{cycle_id}/group-policy", status_code=status.HTTP_204_NO_CONTENT)
def delete_group_policy(cycle_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> Response:
    validate_mutating_origin(request)
    cycle, policy = locked_cycle_and_policy(session, cycle_id)
    if policy is None:
        raise cycle_error(status.HTTP_404_NOT_FOUND, "group_policy_not_found", "No group-size policy exists for this academic cycle.")
    if cycle.registration_open:
        raise cycle_error(status.HTTP_409_CONFLICT, "group_policy_in_use", "Close registration before deleting the group-size policy.")
    if largest_active_team_size(session, cycle.id) > 0:
        raise cycle_error(status.HTTP_409_CONFLICT, "group_policy_in_use", "This group-size policy has active team records and cannot be deleted.")
    add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type="ACADEMIC_GROUP_POLICY", target_id=policy.id, action="group_policy_deleted", changed_values={"academic_cycle_id": cycle.id})
    session.delete(policy)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/health")
def health() -> dict[str, str]:
    """Report application liveness only; this does not check database connectivity."""
    return {"status": "ok", "service": "fyphub-p1-api"}


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    """Report readiness only when the database and vector extension are available."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            vector_version = connection.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one_or_none()
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unavailable", "service": "fyphub-p1-api"},
        ) from error

    if vector_version is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unavailable", "service": "fyphub-p1-api"},
        )

    return {"status": "ready", "service": "fyphub-p1-api"}


@app.post("/api/v1/auth/login", response_model=CurrentUserResponse)
def login(
    credentials: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """Authenticate an active account and issue a new opaque cookie session."""
    validate_mutating_origin(request)
    if credentials.email is not None:
        user = session.execute(
            select(User).where(User.email == str(credentials.email).strip().lower())
        ).scalar_one_or_none()
    else:
        # Student access is group-account-only: registration numbers are never
        # accepted as login identifiers.
        user = None
    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_valid = verify_password(credentials.password, password_hash)
    group_linked = user is not None and (
        user.role != UserRole.STUDENT
        or session.scalar(select(Team.id).where(Team.shared_user_id == user.id, Team.status != "dissolved").limit(1)) is not None
    )
    if (
        user is None
        or not password_valid
        or not user.is_active
        or not group_linked
        or (credentials.requested_role is not None and user.role != credentials.requested_role)
    ):
        log_temporary_auth_diagnostic(
            request,
            "login_response",
            response_status=status.HTTP_401_UNAUTHORIZED,
            session_cookie_set=False,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    now = utc_now()
    presented_token = request.cookies.get(SESSION_COOKIE_NAME)
    if presented_token:
        existing = session.execute(
            select(AuthSession).where(AuthSession.token_hash == hash_session_token(presented_token))
        ).scalar_one_or_none()
        if existing is not None and existing.revoked_at is None:
            existing.revoked_at = now

    raw_token = generate_session_token()
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_session_token(raw_token),
            expires_at=now + timedelta(hours=SESSION_LIFETIME_HOURS),
        )
    )
    session.commit()
    set_session_cookie(request, response, raw_token)
    log_temporary_auth_diagnostic(
        request,
        "login_response",
        response_status=status.HTTP_200_OK,
        session_cookie_set=True,
        cookie_domain=None,
        cookie_path="/",
        cookie_secure=session_cookie_secure(request),
        cookie_samesite="lax",
        cookie_max_age=SESSION_LIFETIME_HOURS * 60 * 60,
    )
    return account_response(session, user)


def account_response(session: Session, user: User) -> dict[str, object]:
    """Return an account principal and, for students, its shared group context."""
    member_match = select(TeamMember.id).where(
        TeamMember.team_id == Team.id,
        TeamMember.academic_cycle_id == Team.academic_cycle_id,
        TeamMember.is_active.is_(True),
        (TeamMember.registration_number == user.registration_number) | (TeamMember.university_email == user.email),
    ).exists()
    team = session.scalar(
        select(Team)
        .where(Team.status != "dissolved", (Team.shared_user_id == user.id) | member_match)
        .order_by(Team.id)
        .limit(1)
    )
    group_id = team.id if team is not None else None
    shared_account = session.get(User, team.shared_user_id) if team is not None else None
    cycle = session.get(AcademicCycle, team.academic_cycle_id) if team is not None else None
    members = session.execute(
        select(TeamMember)
        .where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True))
        .order_by(TeamMember.is_creator.desc(), TeamMember.id)
    ).scalars().all() if team is not None else []
    group_name = None
    if members:
        leader = next((member for member in members if member.is_creator), members[0])
        group_name = f"{leader.full_name}'s Group"
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "registration_number": user.registration_number,
        "role": user.role,
        "is_active": user.is_active,
        "principal_type": "GROUP" if user.role == UserRole.STUDENT and team is not None else "ACCOUNT",
        "group_id": group_id if user.role == UserRole.STUDENT else None,
        "group_email": shared_account.email if user.role == UserRole.STUDENT and group_id is not None and shared_account is not None else None,
        "group_name": group_name if user.role == UserRole.STUDENT else None,
        "academic_cycle": cycle.display_name if user.role == UserRole.STUDENT and cycle is not None else None,
        "group_status": ("ACTIVE" if user.is_active else "INACTIVE") if user.role == UserRole.STUDENT and team is not None else None,
        "members": [
            {
                "id": member.id,
                "full_name": member.full_name,
                "registration_number": member.registration_number,
                "email": member.university_email,
                "designation": "LEADER" if member.is_creator else "MEMBER",
                "is_active": member.is_active,
            }
            for member in members
        ] if user.role == UserRole.STUDENT else [],
    }


@app.get("/api/v1/auth/me", response_model=CurrentUserResponse)
def current_user(request: Request, current_user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> dict[str, object]:
    """Return the authenticated active account's safe fields."""
    log_temporary_auth_diagnostic(
        request,
        "auth_me_response",
        user_id=current_user.id,
        user_active=current_user.is_active,
        persisted_role=current_user.role.value,
        role_comparison="not applicable",
        response_status=status.HTTP_200_OK,
    )
    return account_response(session, current_user)


@app.get("/api/v1/admin/me", response_model=CurrentUserResponse)
def admin_current_user(
    request: Request,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """Return the current account only when its persisted role is ADMIN."""
    log_temporary_auth_diagnostic(
        request,
        "admin_me_response",
        user_id=current_user.id,
        user_active=current_user.is_active,
        persisted_role=current_user.role.value,
        role_comparison="matched",
        response_status=status.HTTP_200_OK,
    )
    return account_response(session, current_user)


@app.get("/api/v1/admin/registration-mode")
def admin_registration_mode(
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> dict[str, str | None]:
    """Expose demo-mode status only to authenticated administrators."""
    mode = registration_mode()
    return {
        "registration_mode": mode.value,
        "demo_warning": DEMO_MODE_WARNING if mode is RegistrationMode.DEMO else None,
    }


def admin_user_error(status_code: int, code: str, message: str) -> HTTPException:
    """Return a safe management failure without leaking persistence details."""
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def add_admin_audit_event(
    session: Session, *, actor_id: int, affected_user_id: int | None, action: str, changed_values: dict[str, object], target_type: str = "USER", target_id: int | None = None
) -> None:
    """Append only non-sensitive account metadata; never credentials or sessions."""
    session.add(
        AdminAuditEvent(
            actor_id=actor_id,
            affected_user_id=affected_user_id, target_type=target_type, target_id=target_id if target_id is not None else affected_user_id,
            action=action,
            changed_values=changed_values,
        )
    )


def shared_team_account(session: Session, user_id: int) -> bool:
    return session.execute(select(Team.id).where(Team.shared_user_id == user_id)).scalar_one_or_none() is not None


def lock_and_protect_last_active_admin(session: Session, user: User, *, will_remain_active_admin: bool) -> None:
    """Serialize changes that could remove the final active ADMIN account."""
    if user.role != UserRole.ADMIN or will_remain_active_admin:
        return
    # PostgreSQL transaction advisory lock closes the count-then-change race across requests.
    session.execute(text("SELECT pg_advisory_xact_lock(98137241)"))
    active_admins = session.execute(
        select(func.count(User.id)).where(User.role == UserRole.ADMIN, User.is_active.is_(True))
    ).scalar_one()
    if user.is_active and active_admins <= 1:
        raise admin_user_error(
            status.HTTP_409_CONFLICT,
            "last_active_admin",
            "At least one active ADMIN account must remain.",
        )


def revoke_user_sessions(session: Session, user_id: int) -> None:
    session.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )


def supervisor_capacity_counts(session: Session, supervisor_id: int, academic_year: int | None) -> dict[str, int]:
    if academic_year is None:
        return {"FALL": 0, "SPRING": 0, "total": 0}
    rows = session.execute(
        select(SupervisorAssignment, AcademicCycle.session, AcademicCycle.academic_year)
        .outerjoin(AcademicCycle, AcademicCycle.id == SupervisorAssignment.academic_cycle_id)
        .where(
            SupervisorAssignment.supervisor_id == supervisor_id,
            SupervisorAssignment.ended_at.is_(None),
            (SupervisorAssignment.academic_year == academic_year)
            | ((SupervisorAssignment.academic_year.is_(None)) & (AcademicCycle.academic_year == academic_year)),
        )
    ).all()
    counts = {"FALL": 0, "SPRING": 0, "total": 0}
    for assignment, cycle_session, _ in rows:
        period_session = assignment.session or cycle_session
        if period_session in ("FALL", "SPRING"):
            counts[period_session] += 1
        counts["total"] += 1
    return counts


def supervisor_capacity_out(policy: SupervisorCapacityPolicy, session: Session) -> dict[str, object]:
    supervisor = policy.supervisor
    cycle = policy.academic_cycle
    academic_year = policy.academic_year if policy.academic_year is not None else cycle.academic_year if cycle else None
    counts = supervisor_capacity_counts(session, policy.supervisor_id, academic_year)
    assigned = counts["total"]
    eligible = supervisor.is_active and supervisor.role == UserRole.SUPERVISOR
    if not eligible:
        status_value = "INACTIVE"
    elif assigned > policy.max_group_capacity:
        status_value = "OVER_CAPACITY"
    elif assigned >= policy.max_group_capacity:
        status_value = "FULL"
    elif assigned * 100 >= policy.max_group_capacity * 80:
        status_value = "NEARLY_FULL"
    else:
        status_value = "AVAILABLE"
    remaining_capacity = max(policy.max_group_capacity - assigned, 0)
    return {
        "assigned": assigned, "remaining": remaining_capacity, "full": assigned >= policy.max_group_capacity,
        "assigned_groups": assigned, "remaining_groups": remaining_capacity, "status": status_value,
        "id": policy.id,
        "supervisor_id": supervisor.id,
        "supervisor_name": supervisor.full_name,
        "supervisor_email": supervisor.email,
        "supervisor_is_eligible": eligible,
        "academic_cycle_id": cycle.id if cycle else None,
        "academic_cycle_name": cycle.display_name if cycle else None,
        "academic_year": academic_year,
        "fall_assigned": counts["FALL"],
        "spring_assigned": counts["SPRING"],
        "total_assigned": assigned,
        "remaining_capacity": remaining_capacity,
        "max_group_capacity": policy.max_group_capacity,
        "maximum_groups": policy.max_group_capacity,
        "created_at": policy.created_at,
        "updated_at": policy.updated_at,
    }


def locked_eligible_supervisor_and_cycle(session: Session, supervisor_id: int, cycle_id: int) -> tuple[User, AcademicCycle]:
    """Lock eligibility records so role/status changes cannot race capacity writes."""
    supervisor = session.execute(select(User).where(User.id == supervisor_id).with_for_update()).scalar_one_or_none()
    if supervisor is None:
        raise admin_user_error(status.HTTP_404_NOT_FOUND, "supervisor_not_found", "Supervisor account was not found.")
    cycle = session.execute(select(AcademicCycle).where(AcademicCycle.id == cycle_id).with_for_update()).scalar_one_or_none()
    if cycle is None:
        raise admin_user_error(status.HTTP_404_NOT_FOUND, "academic_cycle_not_found", "Academic cycle was not found.")
    if not supervisor.is_active or supervisor.role != UserRole.SUPERVISOR:
        raise admin_user_error(status.HTTP_409_CONFLICT, "supervisor_ineligible", "Capacity can be configured only for an active SUPERVISOR account.")
    return supervisor, cycle


def locked_eligible_supervisor_and_period(session: Session, supervisor_id: int, academic_year: int) -> User:
    """Lock an active supervisor before changing annual capacity."""
    supervisor = session.execute(select(User).where(User.id == supervisor_id).with_for_update()).scalar_one_or_none()
    if supervisor is None:
        raise admin_user_error(status.HTTP_404_NOT_FOUND, "supervisor_not_found", "Supervisor account was not found.")
    if not supervisor.is_active or supervisor.role != UserRole.SUPERVISOR:
        raise admin_user_error(status.HTTP_409_CONFLICT, "supervisor_ineligible", "Capacity can be configured only for an active SUPERVISOR account.")
    return supervisor


def assigned_groups_for_period(session: Session, supervisor_id: int, academic_year: int) -> int:
    return supervisor_capacity_counts(session, supervisor_id, academic_year)["total"]


@app.get("/api/v1/admin/users", response_model=AdminUserPage)
def list_admin_users(
    search: str | None = Query(default=None, max_length=320),
    role: UserRole | None = None,
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    statement = select(User)
    count_statement = select(func.count(User.id))
    filters = []
    if search and search.strip():
        needle = f"%{search.strip()}%"
        filters.append(or_(User.full_name.ilike(needle), User.email.ilike(needle), User.registration_number.ilike(needle)))
    if role is not None:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))
    if filters:
        statement = statement.where(*filters)
        count_statement = count_statement.where(*filters)
    total = session.execute(count_statement).scalar_one()
    users = session.execute(
        statement.order_by(User.id).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return {"items": users, "page": page, "page_size": page_size, "total": total}


@app.post("/api/v1/admin/users", status_code=status.HTTP_201_CREATED, response_model=AdminUserResponse)
def create_admin_user(
    payload: AdminUserCreate,
    request: Request,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> User:
    validate_mutating_origin(request)
    user = User(
        full_name=payload.full_name,
        email=str(payload.email).strip().lower(),
        registration_number=payload.registration_number,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    session.add(user)
    try:
        session.flush()
        add_admin_audit_event(
            session,
            actor_id=actor.id,
            affected_user_id=user.id,
            action="account_created",
            changed_values={"email": user.email, "role": user.role.value, "is_active": True},
        )
        session.commit()
        session.refresh(user)
    except IntegrityError as error:
        session.rollback()
        raise admin_user_error(status.HTTP_409_CONFLICT, "duplicate_account", "An account with that email or registration number already exists.") from error
    return user


@app.patch("/api/v1/admin/users/{user_id}/status", response_model=AdminUserResponse)
def change_admin_user_status(
    user_id: int,
    payload: AdminUserStatusChange,
    request: Request,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> User:
    validate_mutating_origin(request)
    user = session.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()
    if user is None:
        raise admin_user_error(status.HTTP_404_NOT_FOUND, "account_not_found", "Account was not found.")
    if user.is_active == payload.is_active:
        return user
    lock_and_protect_last_active_admin(
        session, user, will_remain_active_admin=payload.is_active and user.role == UserRole.ADMIN
    )
    previous = user.is_active
    user.is_active = payload.is_active
    if not payload.is_active:
        revoke_user_sessions(session, user.id)
    add_admin_audit_event(
        session, actor_id=actor.id, affected_user_id=user.id, action="account_status_changed",
        changed_values={"is_active": payload.is_active, "previous_is_active": previous},
    )
    try:
        session.commit()
        session.refresh(user)
    except SQLAlchemyError:
        session.rollback()
        raise
    return user


@app.patch("/api/v1/admin/users/{user_id}/role", response_model=AdminUserResponse)
def change_admin_user_role(
    user_id: int,
    payload: AdminUserRoleChange,
    request: Request,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> User:
    validate_mutating_origin(request)
    raise admin_user_error(
        status.HTTP_409_CONFLICT,
        "assigned_role_locked",
        "An account's assigned role is fixed after creation.",
    )
    user = session.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()
    if user is None:
        raise admin_user_error(status.HTTP_404_NOT_FOUND, "account_not_found", "Account was not found.")
    if user.role == payload.role:
        return user
    if shared_team_account(session, user.id):
        raise admin_user_error(status.HTTP_409_CONFLICT, "shared_team_account", "Shared team account roles cannot be changed here.")
    if payload.role == UserRole.STUDENT and user.registration_number is None:
        raise admin_user_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "student_registration_required", "A STUDENT account requires a registration number.")
    lock_and_protect_last_active_admin(
        session, user, will_remain_active_admin=user.is_active and payload.role == UserRole.ADMIN
    )
    previous = user.role
    user.role = payload.role
    revoke_user_sessions(session, user.id)
    add_admin_audit_event(
        session, actor_id=actor.id, affected_user_id=user.id, action="account_role_changed",
        changed_values={"role": payload.role.value, "previous_role": previous.value},
    )
    try:
        session.commit()
        session.refresh(user)
    except SQLAlchemyError:
        session.rollback()
        raise
    return user


@app.delete("/api/v1/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_user(
    user_id: int,
    request: Request,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> Response:
    """Remove portal access without deleting the account or historical records."""
    validate_mutating_origin(request)
    if actor.id == user_id:
        raise admin_user_error(status.HTTP_409_CONFLICT, "cannot_delete_self", "You cannot delete the account used for this admin session.")
    user = session.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()
    if user is None:
        raise admin_user_error(status.HTTP_404_NOT_FOUND, "account_not_found", "Account was not found.")
    if user.role == UserRole.ADMIN and user.is_active:
        lock_and_protect_last_active_admin(session, user, will_remain_active_admin=False)
    was_active = user.is_active
    try:
        user.is_active = False
        revoke_user_sessions(session, user.id)
        from .models import PasswordResetToken
        session.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)).values(used_at=utc_now()))
        if was_active:
            add_admin_audit_event(session, actor_id=actor.id, affected_user_id=user.id, action="account_access_removed", changed_values={"previous_is_active": True, "is_active": False, "historical_records_preserved": True})
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/v1/admin/supervisor-capacities", response_model=list[SupervisorCapacityOut])
def list_supervisor_capacities(
    _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    policies = session.execute(
        select(SupervisorCapacityPolicy).order_by(SupervisorCapacityPolicy.id)
    ).scalars().all()
    return [supervisor_capacity_out(policy, session) for policy in policies]


@app.get("/api/v1/supervisor/capacity")
def supervisor_capacity_workspace(
    actor: User = Depends(require_roles(UserRole.SUPERVISOR)), session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    """Return the signed-in supervisor's read-only annual capacity and assignment detail."""
    policies = session.scalars(
        select(SupervisorCapacityPolicy)
        .where(SupervisorCapacityPolicy.supervisor_id == actor.id)
        .order_by(SupervisorCapacityPolicy.academic_year, SupervisorCapacityPolicy.id)
    ).all()
    result: list[dict[str, object]] = []
    for policy in policies:
        item = supervisor_capacity_out(policy, session)
        academic_year = item.get("academic_year")
        assignments = session.execute(
            select(SupervisorAssignment, AcademicCycle, Team)
            .join(AcademicCycle, AcademicCycle.id == SupervisorAssignment.academic_cycle_id)
            .join(Team, Team.id == SupervisorAssignment.team_id)
            .where(
                SupervisorAssignment.supervisor_id == actor.id,
                SupervisorAssignment.ended_at.is_(None),
                (SupervisorAssignment.academic_year == academic_year)
                | ((SupervisorAssignment.academic_year.is_(None)) & (AcademicCycle.academic_year == academic_year)),
            )
            .order_by(AcademicCycle.academic_year, AcademicCycle.session, Team.id)
        ).all() if academic_year is not None else []
        item["assignments"] = [
            {
                "assignment_id": assignment.id,
                "team_id": team.id,
                "academic_cycle_id": cycle.id,
                "academic_cycle": cycle.display_name,
                "academic_year": assignment.academic_year or cycle.academic_year,
                "session": assignment.session or cycle.session,
                "assigned_at": assignment.created_at,
            }
            for assignment, cycle, team in assignments
        ]
        result.append(item)
    return result


@app.get("/api/v1/admin/supervisor-capacities/{policy_id}", response_model=SupervisorCapacityOut)
def read_supervisor_capacity(
    policy_id: int, _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)
) -> dict[str, object]:
    policy = session.get(SupervisorCapacityPolicy, policy_id)
    if policy is None:
        raise admin_user_error(status.HTTP_404_NOT_FOUND, "capacity_policy_not_found", "Supervisor capacity policy was not found.")
    return supervisor_capacity_out(policy, session)


@app.post("/api/v1/admin/supervisor-capacities", status_code=status.HTTP_201_CREATED, response_model=SupervisorCapacityOut)
def create_supervisor_capacity(
    payload: SupervisorCapacityWrite, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)
) -> dict[str, object]:
    validate_mutating_origin(request)
    # Serialize capacity writes before taking row locks. This prevents a
    # create and an update from acquiring policy/account locks in a cycle.
    session.execute(text("SELECT pg_advisory_xact_lock(98137243)"))
    locked_eligible_supervisor_and_period(session, payload.supervisor_id, payload.academic_year)
    existing = session.execute(select(SupervisorCapacityPolicy).where(
        SupervisorCapacityPolicy.supervisor_id == payload.supervisor_id,
        SupervisorCapacityPolicy.academic_year == payload.academic_year,
    )).scalar_one_or_none()
    if existing is not None:
        raise admin_user_error(status.HTTP_409_CONFLICT, "duplicate_capacity_policy", "A capacity policy already exists for this supervisor and academic year.")
    policy = SupervisorCapacityPolicy(
        supervisor_id=payload.supervisor_id,
        academic_year=payload.academic_year,
        max_group_capacity=payload.maximum_groups,
    )
    session.add(policy)
    try:
        session.flush()
        add_admin_audit_event(session, actor_id=actor.id, affected_user_id=payload.supervisor_id, target_type="SUPERVISOR_CAPACITY_POLICY", target_id=policy.id, action="supervisor_capacity_created", changed_values={"academic_year": payload.academic_year, "maximum_groups": payload.maximum_groups})
        session.commit(); session.refresh(policy)
    except IntegrityError as error:
        session.rollback()
        raise admin_user_error(status.HTTP_409_CONFLICT, "duplicate_capacity_policy", "A capacity policy already exists for this supervisor and academic year.") from error
    except SQLAlchemyError as error:
        session.rollback()
        raise admin_user_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "capacity_save_failed", "Supervisor capacity could not be saved.") from error
    return supervisor_capacity_out(policy, session)


@app.put("/api/v1/admin/supervisor-capacities/{policy_id}", response_model=SupervisorCapacityOut)
def update_supervisor_capacity(
    policy_id: int, payload: SupervisorCapacityWrite, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)
) -> dict[str, object]:
    validate_mutating_origin(request)
    # Match create's advisory-lock-first order. The account row lock below
    # serializes an eligibility check with activation or deactivation.
    session.execute(text("SELECT pg_advisory_xact_lock(98137243)"))
    policy = session.execute(select(SupervisorCapacityPolicy).where(SupervisorCapacityPolicy.id == policy_id).with_for_update()).scalar_one_or_none()
    if policy is None:
        raise admin_user_error(status.HTTP_404_NOT_FOUND, "capacity_policy_not_found", "Supervisor capacity policy was not found.")
    locked_eligible_supervisor_and_period(session, payload.supervisor_id, payload.academic_year)
    duplicate = session.execute(select(SupervisorCapacityPolicy.id).where(
        SupervisorCapacityPolicy.supervisor_id == payload.supervisor_id,
        SupervisorCapacityPolicy.academic_year == payload.academic_year,
        SupervisorCapacityPolicy.id != policy.id,
    )).scalar_one_or_none()
    if duplicate is not None:
        raise admin_user_error(status.HTTP_409_CONFLICT, "duplicate_capacity_policy", "A capacity policy already exists for this supervisor and academic year.")
    old_year = policy.academic_year or (policy.academic_cycle.academic_year if policy.academic_cycle else payload.academic_year)
    assigned = assigned_groups_for_period(session, policy.supervisor_id, old_year)
    if payload.maximum_groups < assigned:
        raise admin_user_error(status.HTTP_409_CONFLICT, "capacity_in_use", "Annual capacity cannot be lower than the currently assigned groups.")
    previous = {"supervisor_id": policy.supervisor_id, "academic_year": policy.academic_year, "maximum_groups": policy.max_group_capacity}
    policy.supervisor_id = payload.supervisor_id; policy.academic_year = payload.academic_year; policy.max_group_capacity = payload.maximum_groups
    try:
        session.flush()
        add_admin_audit_event(session, actor_id=actor.id, affected_user_id=payload.supervisor_id, target_type="SUPERVISOR_CAPACITY_POLICY", target_id=policy.id, action="supervisor_capacity_updated", changed_values={"before": previous, "after": {"supervisor_id": payload.supervisor_id, "academic_year": payload.academic_year, "maximum_groups": payload.maximum_groups}})
        session.commit(); session.refresh(policy)
    except IntegrityError as error:
        session.rollback()
        raise admin_user_error(status.HTTP_409_CONFLICT, "duplicate_capacity_policy", "A capacity policy already exists for this supervisor and academic year.") from error
    except SQLAlchemyError as error:
        session.rollback()
        raise admin_user_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "capacity_save_failed", "Supervisor capacity could not be saved.") from error
    return supervisor_capacity_out(policy, session)


@app.delete("/api/v1/admin/supervisor-capacities/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supervisor_capacity(
    policy_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)
) -> Response:
    validate_mutating_origin(request)
    session.execute(text("SELECT pg_advisory_xact_lock(98137243)"))
    policy = session.execute(
        select(SupervisorCapacityPolicy).where(SupervisorCapacityPolicy.id == policy_id).with_for_update()
    ).scalar_one_or_none()
    if policy is None:
        raise admin_user_error(status.HTTP_404_NOT_FOUND, "capacity_policy_not_found", "Supervisor capacity policy was not found.")
    year = policy.academic_year if policy.academic_year is not None else (policy.academic_cycle.academic_year if policy.academic_cycle else None)
    assigned = assigned_groups_for_period(session, policy.supervisor_id, year) if year is not None else 0
    if assigned:
        raise admin_user_error(status.HTTP_409_CONFLICT, "capacity_in_use", "This capacity policy has active assignments and cannot be deleted.")
    active_requests = session.scalar(select(func.count(SupervisorRequest.id)).where(
        SupervisorRequest.supervisor_id == policy.supervisor_id,
        SupervisorRequest.status.in_((SupervisorRequestStatus.DRAFT.value, SupervisorRequestStatus.SUBMITTED.value, SupervisorRequestStatus.CHANGES_REQUESTED.value, SupervisorRequestStatus.ACCEPTED.value)),
    )) or 0
    if active_requests:
        raise admin_user_error(status.HTTP_409_CONFLICT, "capacity_in_use", "This capacity policy has active supervisor requests and cannot be deleted.")
    add_admin_audit_event(session, actor_id=actor.id, affected_user_id=policy.supervisor_id, target_type="SUPERVISOR_CAPACITY_POLICY", target_id=policy.id, action="supervisor_capacity_deleted", changed_values={})
    session.delete(policy)
    try:
        session.commit()
    except SQLAlchemyError as error:
        session.rollback()
        raise admin_user_error(status.HTTP_409_CONFLICT, "capacity_delete_failed", "The capacity policy could not be deleted because it is still in use.") from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
) -> Response:
    """Revoke the presented session when present and always clear its browser cookie."""
    validate_mutating_origin(request)
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        record = session.execute(
            select(AuthSession).where(AuthSession.token_hash == hash_session_token(token))
        ).scalar_one_or_none()
        if record is not None and record.revoked_at is None:
            record.revoked_at = utc_now()
            session.commit()
    clear_session_cookie(request, response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@app.post(
    "/api/v1/auth/register",
    status_code=status.HTTP_201_CREATED,
    response_model=RegistrationResponse,
)
def register_student(
    registration: RegistrationRequest, session: Session = Depends(get_db)
) -> User:
    """Reject the retired individual public signup flow.

    Public student registration is group-based.  Keep this route as an explicit
    compatibility response so older clients cannot silently create accounts
    outside the group-registration workflow.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Individual student signup is no longer available. Create a student group account instead.",
    )


@app.post(
    "/api/v1/team-registration",
    status_code=status.HTTP_201_CREATED,
    response_model=TeamRegistrationResponse,
)
def register_team(
    registration: TeamRegistrationRequest,
    session: Session = Depends(get_db),
    *,
    request: Request = None,
) -> dict[str, object]:
    """Atomically create one shared student account, team, and member contacts."""
    creator = normalize_team_member(registration.creator, "creator")
    members = [
        normalize_team_member(member, f"members.{index}")
        for index, member in enumerate(registration.members)
    ]
    all_members = [creator, *members]
    shared_login_email = str(registration.shared_login_email).strip().lower()

    if len(shared_login_email) > 320:
        raise registration_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_shared_login_email",
            "Shared login email must not exceed 320 characters.",
            "shared_login_email",
        )
    if not 8 <= len(registration.password) <= 128:
        raise registration_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_password_length",
            "Password must be between 8 and 128 characters.",
            "password",
        )
    if registration.confirm_password is not None and registration.password != registration.confirm_password:
        raise registration_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "password_mismatch",
            "Password and confirmation password must match.",
            "confirm_password",
        )
    try:
        validate_password(registration.password)
    except ValueError as error:
        raise registration_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_password_policy",
            str(error),
            "password",
        ) from error

    registration_paths: dict[str, str] = {}
    email_paths: dict[str, str] = {}
    for index, member in enumerate(all_members):
        prefix = "creator" if index == 0 else f"members.{index - 1}"
        registration_number = member["registration_number"]
        university_email = member["university_email"]
        if registration_number in registration_paths:
            raise registration_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "duplicate_request_registration_number",
                "Registration numbers must be unique within the team.",
                f"{prefix}.registration_number",
            )
        if university_email is not None and university_email in email_paths:
            raise registration_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "duplicate_request_university_email",
                "University emails must be unique within the team.",
                f"{prefix}.university_email",
            )
        registration_paths[registration_number] = prefix
        if university_email is not None:
            email_paths[university_email] = prefix

    try:
        cycle = session.execute(
            select(AcademicCycle)
            .where(AcademicCycle.id == registration.academic_cycle_id)
            .with_for_update()
        ).scalar_one_or_none()
        if cycle is None:
            raise registration_error(
                status.HTTP_404_NOT_FOUND,
                "academic_cycle_not_found",
                "Academic cycle was not found.",
                "academic_cycle_id",
            )
        if not cycle.registration_open:
            raise registration_error(
                status.HTTP_409_CONFLICT,
                "academic_cycle_closed",
                "Registration is not open for this academic cycle.",
                "academic_cycle_id",
            )

        policy = session.execute(
            select(AcademicGroupPolicy)
            .where(AcademicGroupPolicy.academic_cycle_id == cycle.id)
            .with_for_update()
        ).scalar_one_or_none()
        if policy is None:
            raise registration_error(
                status.HTTP_409_CONFLICT,
                "academic_group_policy_missing",
                "Academic group policy is not configured for this cycle.",
                "academic_cycle_id",
            )
        if len(all_members) > policy.max_group_size:
            raise registration_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "group_size_exceeded",
                "Team size exceeds the configured maximum.",
                "members",
            )
        if len(all_members) < policy.min_group_size:
            raise registration_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "group_size_below_minimum",
                "Team size is below the configured minimum.",
                "members",
            )

        existing_user = session.execute(
            select(User.email, User.registration_number).where(
                or_(
                    User.email == shared_login_email,
                    User.registration_number.in_(registration_paths),
                )
            )
        ).all()
        for email, registration_number in existing_user:
            if email == shared_login_email:
                raise registration_error(
                    status.HTTP_409_CONFLICT,
                    "shared_login_email_exists",
                    "An account with that shared login email already exists.",
                    "shared_login_email",
                )
            if registration_number == creator["registration_number"]:
                raise registration_error(
                    status.HTTP_409_CONFLICT,
                    "creator_registration_exists",
                    "An account with that creator registration number already exists.",
                    "creator.registration_number",
                )
            if registration_number in registration_paths:
                raise registration_error(
                    status.HTTP_409_CONFLICT,
                    "member_registration_exists",
                    "A registration number already belongs to another account.",
                    f"{registration_paths[registration_number]}.registration_number",
                )

        existing_member = session.execute(
            select(TeamMember.registration_number, TeamMember.university_email).where(
                TeamMember.is_active.is_(True),
                or_(
                    TeamMember.registration_number.in_(registration_paths),
                    TeamMember.university_email.in_(email_paths) if email_paths else False,
                ),
            )
        ).all()
        for registration_number, university_email in existing_member:
            if registration_number in registration_paths:
                raise registration_error(
                    status.HTTP_409_CONFLICT,
                    "member_registration_exists",
                    "An active member with that registration number already belongs to another group.",
                    f"{registration_paths[registration_number]}.registration_number",
                )
            if university_email in email_paths:
                raise registration_error(
                    status.HTTP_409_CONFLICT,
                    "member_university_email_exists",
                    "An active member with that university email already belongs to another group.",
                    f"{email_paths[university_email]}.university_email",
                )

        user = User(
            full_name=creator["full_name"],
            email=shared_login_email,
            registration_number=creator["registration_number"],
            password_hash=hash_password(registration.password),
            role=UserRole.STUDENT,
        )
        session.add(user)
        session.flush()

        team = Team(academic_cycle_id=cycle.id, shared_user_id=user.id)
        session.add(team)
        session.flush()

        created_members = [
            TeamMember(
                team_id=team.id,
                academic_cycle_id=cycle.id,
                is_creator=index == 0,
                **{**member, "university_email": member["university_email"] or f"{member['registration_number'].lower()}@group.invalid"},
            )
            for index, member in enumerate(all_members)
        ]
        session.add_all(created_members)
        session.flush()
        from .team_lifecycle import refresh_team_status
        refresh_team_status(session, team)
        if request is not None:
            add_admin_audit_event(
                session,
                actor_id=user.id,
                affected_user_id=user.id,
                target_type="REGISTRATION",
                target_id=user.id,
                action="team_registration_created",
                changed_values={
                    "registration_mode": registration_mode().value,
                    "academic_cycle_id": cycle.id,
                    "team_id": team.id,
                    "member_count": len(created_members),
                },
            )
        session.commit()
        for record in (user, team, *created_members):
            session.refresh(record)
    except HTTPException:
        session.rollback()
        raise
    except IntegrityError as error:
        session.rollback()
        raise registration_error(
            status.HTTP_409_CONFLICT,
            "duplicate_conflict",
            "A conflicting account or active team member already exists.",
        ) from error
    except SQLAlchemyError as error:
        session.rollback()
        raise registration_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "team_registration_failed",
            "Team registration could not be completed.",
        ) from error

    return {
        "account": user,
        "team": team,
        "cycle": cycle,
        "members": created_members,
    }


@app.post(
    "/api/v1/student/group-registration",
    response_model=TeamRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
@app.post(
    "/api/v1/auth/group-signup",
    status_code=status.HTTP_201_CREATED,
    response_model=TeamRegistrationResponse,
)
def register_student_group(
    registration: StudentGroupRegistrationRequest,
    session: Session = Depends(get_db),
    *,
    request: Request = None,
) -> dict[str, object]:
    """Create one shared STUDENT group account from member contacts only."""
    if not registration.members:
        raise registration_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "members_required", "Add at least one group member.", "members")
    first, *remaining = registration.members
    def member_name(email: str) -> str:
        return email.split("@", 1)[0].replace(".", " ").replace("_", " ").strip().title() or "Group member"
    leader_count = sum(1 for member in registration.members if (member.designation or "").strip().upper() == "LEADER")
    if leader_count > 1:
        raise registration_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "multiple_leaders", "A group can have only one leader.", "members")
    if leader_count == 1:
        first = next(member for member in registration.members if (member.designation or "").strip().upper() == "LEADER")
        remaining = [member for member in registration.members if member is not first]
    legacy = TeamRegistrationRequest(
        academic_cycle_id=registration.academic_cycle_id,
        creator=TeamMemberInput(full_name=first.full_name or member_name(str(first.email)), registration_number=first.registration_number, university_email=first.email),
        shared_login_email=registration.group_email,
        password=registration.password,
        confirm_password=registration.confirm_password,
        members=[TeamMemberInput(full_name=member.full_name or member_name(str(member.email)), registration_number=member.registration_number, university_email=member.email) for member in remaining],
    )
    return register_team(legacy, session, request=request)


def student_group_detail(session: Session, team: Team) -> dict[str, object]:
    """Serialize the shared student principal without exposing credentials."""
    account = session.get(User, team.shared_user_id)
    cycle = session.get(AcademicCycle, team.academic_cycle_id)
    members = session.execute(
        select(TeamMember)
        .where(TeamMember.team_id == team.id)
        .order_by(TeamMember.is_creator.desc(), TeamMember.id)
    ).scalars().all()
    assignment = session.scalar(select(SupervisorAssignment).where(SupervisorAssignment.team_id == team.id, SupervisorAssignment.ended_at.is_(None)).order_by(SupervisorAssignment.id.desc()).limit(1))
    supervisor = session.get(User, assignment.supervisor_id) if assignment else None
    latest_request = session.scalar(select(SupervisorRequest).where(SupervisorRequest.team_id == team.id).order_by(SupervisorRequest.updated_at.desc(), SupervisorRequest.id.desc()).limit(1))
    leader = next((member for member in members if member.is_creator), members[0] if members else None)
    return {
        "id": team.id,
        "group_id": team.id,
        "group_name": f"{leader.full_name}'s Group" if leader else f"Group {team.id}",
        "group_email": account.email if account else None,
        "academic_cycle_id": team.academic_cycle_id,
        "academic_cycle": cycle.display_name if cycle else None,
        "status": "ACTIVE" if account and account.is_active and team.status != "dissolved" else "INACTIVE",
        "is_active": bool(account and account.is_active and team.status != "dissolved"),
        "created_at": team.created_at,
        "project": {"title": latest_request.title, "status": latest_request.status, "updated_at": latest_request.updated_at} if latest_request else None,
        "supervisor": {"id": supervisor.id, "name": supervisor.full_name} if supervisor else None,
        "supervisor_assignment": {"id": assignment.id, "academic_cycle_id": assignment.academic_cycle_id, "assigned_at": assignment.created_at} if assignment else None,
        "members": [
            {
                "id": member.id,
                "full_name": member.full_name,
                "registration_number": member.registration_number,
                "email": member.university_email,
                "designation": "LEADER" if member.is_creator else "MEMBER",
                "is_creator": member.is_creator,
                "is_active": member.is_active,
            }
            for member in members
        ],
    }


def current_student_team(session: Session, actor: User) -> Team:
    member_match = select(TeamMember.id).where(
        TeamMember.team_id == Team.id,
        TeamMember.academic_cycle_id == Team.academic_cycle_id,
        TeamMember.is_active.is_(True),
        (TeamMember.registration_number == actor.registration_number) | (TeamMember.university_email == actor.email),
    ).exists()
    team = session.scalar(
        select(Team)
        .where(Team.status != "dissolved", (Team.shared_user_id == actor.id) | member_match)
        .order_by(Team.id)
        .limit(1)
    )
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student group was not found.")
    return team


@app.get("/api/v1/student/group/me")
def student_group_me(
    actor: User = Depends(require_roles(UserRole.STUDENT)),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    return student_group_detail(session, current_student_team(session, actor))


@app.get("/api/v1/student/group/members")
def student_group_members(
    actor: User = Depends(require_roles(UserRole.STUDENT)),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    group = current_student_team(session, actor)
    return {"group_id": group.id, "members": student_group_detail(session, group)["members"]}


@app.get("/api/v1/admin/student-groups")
def list_student_groups(
    search: str | None = Query(default=None, max_length=320),
    is_active: bool | None = None,
    _: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    statement = select(Team).join(User, User.id == Team.shared_user_id).where(User.role == UserRole.STUDENT, Team.status != "dissolved")
    if search and search.strip():
        needle = f"%{search.strip()}%"
        statement = statement.where(or_(User.email.ilike(needle), User.full_name.ilike(needle)))
    if is_active is not None:
        statement = statement.where(User.is_active.is_(is_active))
    groups = session.execute(statement.order_by(Team.id.desc())).scalars().all()
    return {"items": [student_group_detail(session, group) for group in groups], "total": len(groups)}


@app.get("/api/v1/admin/student-groups/{group_id}")
def get_student_group(
    group_id: int,
    _: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    group = session.get(Team, group_id)
    if group is None or group.status == "dissolved":
        raise admin_user_error(status.HTTP_404_NOT_FOUND, "group_not_found", "Student group was not found.")
    return student_group_detail(session, group)


def set_student_group_status(
    group_id: int,
    active: bool,
    request: Request,
    actor: User,
    session: Session,
) -> dict[str, object]:
    validate_mutating_origin(request)
    group = session.execute(select(Team).where(Team.id == group_id).with_for_update()).scalar_one_or_none()
    if group is None or group.status == "dissolved":
        raise admin_user_error(status.HTTP_404_NOT_FOUND, "group_not_found", "Student group was not found.")
    account = session.execute(select(User).where(User.id == group.shared_user_id).with_for_update()).scalar_one()
    account.is_active = active
    if not active:
        revoke_user_sessions(session, account.id)
    add_admin_audit_event(session, actor_id=actor.id, affected_user_id=account.id, target_type="STUDENT_GROUP", target_id=group.id, action="student_group_activated" if active else "student_group_deactivated", changed_values={"is_active": active})
    session.commit()
    session.refresh(group)
    return student_group_detail(session, group)


@app.patch("/api/v1/admin/student-groups/{group_id}/activate")
def activate_student_group(group_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> dict[str, object]:
    return set_student_group_status(group_id, True, request, actor, session)


@app.patch("/api/v1/admin/student-groups/{group_id}/deactivate")
def deactivate_student_group(group_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> dict[str, object]:
    return set_student_group_status(group_id, False, request, actor, session)


@app.delete("/api/v1/admin/student-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student_group(group_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> Response:
    validate_mutating_origin(request)
    group = session.execute(select(Team).where(Team.id == group_id).with_for_update()).scalar_one_or_none()
    if group is None or group.status == "dissolved":
        raise admin_user_error(status.HTTP_404_NOT_FOUND, "group_not_found", "Student group was not found.")
    account = session.get(User, group.shared_user_id)
    if account is None:
        raise admin_user_error(status.HTTP_404_NOT_FOUND, "group_account_not_found", "The shared group account was not found.")
    try:
        session.execute(delete(AuthSession).where(AuthSession.user_id == account.id))
        session.execute(delete(AdminAuditEvent).where(or_(AdminAuditEvent.actor_id == account.id, AdminAuditEvent.affected_user_id == account.id)))
        session.execute(delete(TeamMember).where(TeamMember.team_id == group.id))
        session.delete(group)
        session.delete(account)
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise admin_user_error(status.HTTP_409_CONFLICT, "group_in_use", "This group is referenced by portal records and cannot be permanently deleted.") from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Non-operational reminder/escalation configuration.
from .models.reminder_rule import ReminderRule, ReminderRuleVersion
from .schemas.reminder_rules import RuleCreate as ReminderCreate, RuleWrite as ReminderWrite, RulePreview as ReminderPreview


def reminder_calculation(session: Session, payload: ReminderPreview, cycle_id: int | None = None) -> dict[str, object]:
    version = session.get(AcademicDeadlineVersion, payload.deadline_version_id)
    if version is None:
        raise deadline_error(404, "deadline_version_not_found", "Deadline version was not found.")
    deadline = session.get(AcademicDeadline, version.academic_deadline_id)
    if cycle_id is not None and deadline.academic_cycle_id != cycle_id:
        raise deadline_error(422, "deadline_cycle_mismatch", "Deadline version must belong to the rule's academic cycle.")
    require_timezone_data()
    try:
        zone = ZoneInfo(version.time_zone)
        due = version.due_at_utc.astimezone(timezone.utc)
        delta = timedelta(minutes=payload.elapsed_minutes)
        calculated = due - delta if payload.direction == "BEFORE" else due + delta
        local = calculated.astimezone(zone)
        due_local = due.astimezone(zone)
    except ZoneInfoNotFoundError as error:
        raise deadline_error(503, "timezone_data_unavailable", "Timezone data is unavailable; contact the service administrator.") from error
    except (OverflowError, ValueError) as error:
        raise deadline_error(422, "calculation_out_of_range", "Calculated time is outside the supported date range.") from error
    return {"deadline_version_id": version.id, "deadline_id": deadline.id, "deadline_version_number": version.version_number, "academic_cycle_id": deadline.academic_cycle_id, "deadline_name": version.name, "due_at_utc": due, "due_local": due_local.isoformat(), "time_zone": version.time_zone, "direction": payload.direction, "elapsed_minutes": payload.elapsed_minutes, "calculated_at_utc": calculated, "calculated_local": local.isoformat(), "utc_offset": formatted_utc_offset(local.utcoffset() or timedelta())}


def reminder_version_out(session: Session, version: ReminderRuleVersion) -> dict[str, object]:
    calculation = reminder_calculation(session, ReminderPreview(deadline_version_id=version.deadline_version_id, direction=version.direction, elapsed_minutes=version.elapsed_minutes))
    return {**calculation, "id": version.id, "version_number": version.version_number, "name": version.name, "description": version.description, "category": version.category, "created_at": version.created_at}


def reminder_detail(session: Session, rule: ReminderRule) -> dict[str, object]:
    versions = session.execute(select(ReminderRuleVersion).where(ReminderRuleVersion.rule_id == rule.id).order_by(ReminderRuleVersion.version_number)).scalars().all()
    cycle = session.get(AcademicCycle, rule.academic_cycle_id)
    return {"id": rule.id, "academic_cycle_id": rule.academic_cycle_id, "academic_cycle_name": cycle.display_name, "created_at": rule.created_at, "versions": [reminder_version_out(session, version) for version in versions]}


def save_reminder_version(session: Session, rule: ReminderRule, payload: ReminderWrite, actor: User, number: int) -> ReminderRuleVersion:
    reminder_calculation(session, payload, rule.academic_cycle_id)
    version = ReminderRuleVersion(rule_id=rule.id, version_number=number, deadline_version_id=payload.deadline_version_id, name=payload.name, description=payload.description, category=payload.category, direction=payload.direction, elapsed_minutes=payload.elapsed_minutes, created_by_id=actor.id)
    session.add(version)
    session.flush()
    add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type="REMINDER_RULE", target_id=rule.id, action="reminder_rule_version_created", changed_values={"version": number, "academic_cycle_id": rule.academic_cycle_id, "deadline_version_id": payload.deadline_version_id, "category": payload.category, "direction": payload.direction, "elapsed_minutes": payload.elapsed_minutes, "operational": False})
    return version


@app.post("/api/v1/admin/reminder-rules/preview")
def preview_reminder_rule(payload: ReminderPreview, request: Request, _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    return reminder_calculation(session, payload)


@app.get("/api/v1/admin/reminder-rules")
def list_reminder_rules(academic_cycle_id: int | None = None, _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    if academic_cycle_id is not None and session.get(AcademicCycle, academic_cycle_id) is None:
        raise deadline_error(404, "cycle_not_found", "Academic cycle was not found.")
    stmt = select(ReminderRule).order_by(ReminderRule.id)
    if academic_cycle_id is not None:
        stmt = stmt.where(ReminderRule.academic_cycle_id == academic_cycle_id)
    return [reminder_detail(session, rule) for rule in session.execute(stmt).scalars().all()]


@app.get("/api/v1/admin/reminder-rules/{rule_id}")
def read_reminder_rule(rule_id: int, _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    rule = session.get(ReminderRule, rule_id)
    if rule is None:
        raise deadline_error(404, "rule_not_found", "Rule was not found.")
    return reminder_detail(session, rule)


@app.post("/api/v1/admin/reminder-rules", status_code=201)
def create_reminder_rule(payload: ReminderCreate, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    cycle = session.execute(select(AcademicCycle).where(AcademicCycle.id == payload.academic_cycle_id).with_for_update()).scalar_one_or_none()
    if cycle is None:
        raise deadline_error(404, "cycle_not_found", "Academic cycle was not found.")
    try:
        rule = ReminderRule(academic_cycle_id=cycle.id)
        session.add(rule)
        session.flush()
        save_reminder_version(session, rule, payload, actor, 1)
        result = reminder_detail(session, rule)
        session.commit()
        return result
    except HTTPException:
        session.rollback()
        raise
    except Exception as error:
        session.rollback()
        raise deadline_error(500, "rule_save_failed", "Rule configuration could not be saved.") from error


@app.post("/api/v1/admin/reminder-rules/{rule_id}/versions", status_code=201)
def create_reminder_rule_version(rule_id: int, payload: ReminderWrite, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    identity = session.get(ReminderRule, rule_id)
    if identity is None:
        raise deadline_error(404, "rule_not_found", "Rule was not found.")
    try:
        session.execute(select(AcademicCycle).where(AcademicCycle.id == identity.academic_cycle_id).with_for_update()).scalar_one()
        session.execute(text("SELECT pg_advisory_xact_lock(98139, :rule_id)"), {"rule_id": rule_id})
        rule = session.execute(select(ReminderRule).where(ReminderRule.id == rule_id).with_for_update()).scalar_one()
        number = (session.execute(select(func.max(ReminderRuleVersion.version_number)).where(ReminderRuleVersion.rule_id == rule_id)).scalar_one() or 0) + 1
        version = save_reminder_version(session, rule, payload, actor, number)
        result = reminder_version_out(session, version)
        session.commit()
        return result
    except HTTPException:
        session.rollback()
        raise
    except Exception as error:
        session.rollback()
        raise deadline_error(500, "rule_save_failed", "Rule configuration could not be saved.") from error


@app.delete("/api/v1/admin/reminder-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder_rule(
    rule_id: int,
    request: Request,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> Response:
    validate_mutating_origin(request)
    rule = session.get(ReminderRule, rule_id)
    if rule is None:
        raise deadline_error(404, "rule_not_found", "Rule was not found.")
    try:
        session.execute(delete(ReminderRuleVersion).where(ReminderRuleVersion.rule_id == rule_id))
        session.delete(rule)
        add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type="REMINDER_RULE", target_id=rule_id, action="reminder_rule_deleted", changed_values={})
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise deadline_error(409, "rule_in_use", "This reminder rule is referenced by other data and cannot be deleted.") from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


from .audit_history import router as audit_history_router
app.include_router(audit_history_router)

from .supervisor_assignments import router as supervisor_assignments_router
app.include_router(supervisor_assignments_router)

from .group_channels import router as group_channels_router
app.include_router(group_channels_router)
from .module2_collaboration import router as module2_collaboration_router
app.include_router(module2_collaboration_router)
from .collaboration_channels import router as collaboration_channels_router
app.include_router(collaboration_channels_router)
from .group_ai import router as group_ai_router
app.include_router(group_ai_router)

from .notifications import router as notifications_router
app.include_router(notifications_router)

from .supervisor_requests import proposal_router, router as supervisor_requests_router
app.include_router(supervisor_requests_router)
app.include_router(proposal_router)

from .proposal_reference import router as proposal_reference_router
app.include_router(proposal_reference_router)

from .supervisor_request_conversations import router as supervisor_request_conversations_router
app.include_router(supervisor_request_conversations_router)
from .agent_supervision import router as agent_supervision_router
app.include_router(agent_supervision_router)

from .archived_projects import admin_archive_router, router as archived_projects_router
app.include_router(archived_projects_router)
app.include_router(admin_archive_router)

from .password_reset import router as password_reset_router
app.include_router(password_reset_router)
app.include_router(dashboard_requirements_router)
app.include_router(project_workflow_router)
app.include_router(evaluations_router)
from .supervisor_workspace import router as supervisor_workspace_router
app.include_router(supervisor_workspace_router)
