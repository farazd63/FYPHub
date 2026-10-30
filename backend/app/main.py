from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .database import engine, get_db
from .models import AdminAuditEvent, AuthSession, Team, TeamMember, User, UserRole
from .models import AcademicCycle, AcademicGroupPolicy, ApprovedStudent, SupervisorCapacityPolicy, SupervisorAssignment, SupervisorRequest, SupervisorRequestStatus
from .models import TemplateReference, TemplateReferenceVersion, AcademicRuleVersion, TemplateType
from .models import EvaluationRubric, EvaluationRubricCriterion, EvaluationRubricVersion
from .models import AcademicDeadline, AcademicDeadlineVersion
from .schemas.templates import TemplateCreate, TemplateVersionCreate, RuleCreate, TemplateListOut, TemplateOut, RuleOut, TemplateDetail
from .schemas.evaluation_rubrics import RubricDetailOut, RubricListOut, RubricVersionOut, RubricVersionWrite
from .schemas.academic_deadlines import DeadlineCreate, DeadlineDetailOut, DeadlineListOut, DeadlinePreviewOut, DeadlinePreviewRequest, DeadlineVersionOut, DeadlineWrite
from .schemas.academic import CycleCreate, CycleOut, CycleUpdate, PolicyOut, PolicyUpdate
from .schemas.auth import CurrentUserResponse, LoginRequest, RegistrationRequest, RegistrationResponse
from .schemas.admin_users import AdminUserCreate, AdminUserPage, AdminUserResponse, AdminUserRoleChange, AdminUserStatusChange
from .schemas.supervisor_capacity import SupervisorCapacityOut, SupervisorCapacityWrite
from .schemas.team_registration import TeamMemberInput, TeamRegistrationRequest, TeamRegistrationResponse
from .security import generate_session_token, hash_password, hash_session_token, validate_password, verify_password
from .registration_policy import DEMO_MODE_WARNING, RegistrationMode, registration_mode, roster_validation_required
from .project_workflow import router as project_workflow_router
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_BROWSER_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT"],
    allow_headers=["Content-Type", "X-File-Name", "X-Preview-Token"],
)

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


def normalize_team_member(member: TeamMemberInput, path: str) -> dict[str, str]:
    """Apply the established identifier conventions and field-length rules."""
    full_name = member.full_name.strip()
    registration_number = member.registration_number.strip().upper()
    university_email = str(member.university_email).strip().lower()

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
    if len(university_email) > 320:
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
  session.execute(text("SELECT pg_advisory_xact_lock(98137242)")); root=TemplateReference(template_type=payload.template_type); session.add(root); session.flush(); ref=TemplateReferenceVersion(template_reference_id=root.id,version_number=1,title=payload.title.strip(),provenance=payload.provenance,source_note=payload.source_note.strip(),created_by_id=actor.id); session.add(ref); session.flush(); rule=AcademicRuleVersion(template_reference_version_id=ref.id,version_number=1,provenance=payload.provenance,rules=payload.rules.model_dump(exclude_none=True),created_by_id=actor.id); session.add(rule); add_admin_audit_event(session,actor_id=actor.id,affected_user_id=None,target_type="TEMPLATE_REFERENCE",target_id=ref.id,action="template_reference_version_created",changed_values={"template_type":payload.template_type.value,"version":1,"provenance":payload.provenance}); session.commit(); session.refresh(ref); session.refresh(rule); return {"reference_id":root.id,"template_type":root.template_type,"versions":[{"template":ref,"rules":[rule]}]}
 except Exception as error:
  session.rollback(); raise HTTPException(status_code=500,detail="Template reference could not be saved.") from error
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
    cycle = AcademicCycle(code=payload.code, display_name=payload.display_name, registration_open=False)
    session.add(cycle)
    try:
        session.flush()
        add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type="ACADEMIC_CYCLE", target_id=cycle.id, action="academic_cycle_created", changed_values={"code": cycle.code, "display_name": cycle.display_name, "registration_open": False})
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


@app.put("/api/v1/admin/academic-cycles/{cycle_id}/group-policy", response_model=PolicyOut)
def set_group_policy(cycle_id: int, payload: PolicyUpdate, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> AcademicGroupPolicy:
    validate_mutating_origin(request)
    cycle, policy = locked_cycle_and_policy(session, cycle_id)
    largest = largest_active_team_size(session, cycle.id)
    if payload.max_group_size < largest:
        raise cycle_error(status.HTTP_409_CONFLICT, "existing_team_exceeds_limit", "Existing active team membership exceeds that maximum.")
    created = policy is None
    if policy is None:
        policy = AcademicGroupPolicy(academic_cycle_id=cycle.id, max_group_size=payload.max_group_size); session.add(policy); session.flush()
    else:
        previous = policy.max_group_size; policy.max_group_size = payload.max_group_size
    add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type="ACADEMIC_GROUP_POLICY", target_id=policy.id, action="group_policy_created" if created else "group_policy_updated", changed_values={"academic_cycle_id": cycle.id, "max_group_size": payload.max_group_size, "previous_max_group_size": None if created else previous})
    session.commit(); session.refresh(policy)
    return policy


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
) -> User:
    """Authenticate an active account and issue a new opaque cookie session."""
    validate_mutating_origin(request)
    if credentials.email is not None:
        user = session.execute(
            select(User).where(User.email == str(credentials.email).strip().lower())
        ).scalar_one_or_none()
    else:
        user = session.execute(
            select(User).where(User.registration_number == credentials.registration_number)
        ).scalar_one_or_none()
    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_valid = verify_password(credentials.password, password_hash)
    if (
        user is None
        or not password_valid
        or not user.is_active
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
    return user


@app.get("/api/v1/auth/me", response_model=CurrentUserResponse)
def current_user(request: Request, current_user: User = Depends(get_current_user)) -> User:
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
    return current_user


@app.get("/api/v1/admin/me", response_model=CurrentUserResponse)
def admin_current_user(
    request: Request,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> User:
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
    return current_user


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


def supervisor_capacity_out(policy: SupervisorCapacityPolicy, session: Session) -> dict[str, object]:
    supervisor = policy.supervisor
    cycle = policy.academic_cycle
    assigned = session.scalar(select(func.count(SupervisorAssignment.id)).where(SupervisorAssignment.supervisor_id == policy.supervisor_id, SupervisorAssignment.academic_cycle_id == policy.academic_cycle_id, SupervisorAssignment.ended_at.is_(None))) or 0
    assigned += session.scalar(select(func.count(SupervisorRequest.id)).where(SupervisorRequest.supervisor_id == policy.supervisor_id, SupervisorRequest.academic_cycle_id == policy.academic_cycle_id, SupervisorRequest.status == SupervisorRequestStatus.ACCEPTED.value, SupervisorRequest.assignment_id.is_(None))) or 0
    return {
        "assigned": assigned, "remaining": max(policy.max_group_capacity - assigned, 0), "full": assigned >= policy.max_group_capacity,
        "id": policy.id,
        "supervisor_id": supervisor.id,
        "supervisor_name": supervisor.full_name,
        "supervisor_email": supervisor.email,
        "supervisor_is_eligible": supervisor.is_active and supervisor.role == UserRole.SUPERVISOR,
        "academic_cycle_id": cycle.id,
        "academic_cycle_name": cycle.display_name,
        "max_group_capacity": policy.max_group_capacity,
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
    if not payload.is_active and shared_team_account(session, user.id):
        raise admin_user_error(status.HTTP_409_CONFLICT, "shared_team_account", "Shared team accounts cannot be deactivated here.")
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


@app.get("/api/v1/admin/supervisor-capacities", response_model=list[SupervisorCapacityOut])
def list_supervisor_capacities(
    _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    policies = session.execute(
        select(SupervisorCapacityPolicy).order_by(SupervisorCapacityPolicy.id)
    ).scalars().all()
    return [supervisor_capacity_out(policy, session) for policy in policies]


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
    locked_eligible_supervisor_and_cycle(session, payload.supervisor_id, payload.academic_cycle_id)
    existing = session.execute(select(SupervisorCapacityPolicy).where(
        SupervisorCapacityPolicy.supervisor_id == payload.supervisor_id,
        SupervisorCapacityPolicy.academic_cycle_id == payload.academic_cycle_id,
    )).scalar_one_or_none()
    if existing is not None:
        raise admin_user_error(status.HTTP_409_CONFLICT, "duplicate_capacity_policy", "A capacity policy already exists for this supervisor and cycle.")
    policy = SupervisorCapacityPolicy(**payload.model_dump())
    session.add(policy)
    try:
        session.flush()
        add_admin_audit_event(session, actor_id=actor.id, affected_user_id=payload.supervisor_id, target_type="SUPERVISOR_CAPACITY_POLICY", target_id=policy.id, action="supervisor_capacity_created", changed_values={"academic_cycle_id": payload.academic_cycle_id, "max_group_capacity": payload.max_group_capacity})
        session.commit(); session.refresh(policy)
    except IntegrityError as error:
        session.rollback()
        raise admin_user_error(status.HTTP_409_CONFLICT, "duplicate_capacity_policy", "A capacity policy already exists for this supervisor and cycle.") from error
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
    locked_eligible_supervisor_and_cycle(session, payload.supervisor_id, payload.academic_cycle_id)
    duplicate = session.execute(select(SupervisorCapacityPolicy.id).where(
        SupervisorCapacityPolicy.supervisor_id == payload.supervisor_id,
        SupervisorCapacityPolicy.academic_cycle_id == payload.academic_cycle_id,
        SupervisorCapacityPolicy.id != policy.id,
    )).scalar_one_or_none()
    if duplicate is not None:
        raise admin_user_error(status.HTTP_409_CONFLICT, "duplicate_capacity_policy", "A capacity policy already exists for this supervisor and cycle.")
    assigned = session.scalar(select(func.count(SupervisorAssignment.id)).where(SupervisorAssignment.supervisor_id == policy.supervisor_id, SupervisorAssignment.academic_cycle_id == policy.academic_cycle_id, SupervisorAssignment.ended_at.is_(None))) or 0
    if assigned and (policy.supervisor_id != payload.supervisor_id or policy.academic_cycle_id != payload.academic_cycle_id or payload.max_group_capacity < assigned):
        raise admin_user_error(status.HTTP_409_CONFLICT, "capacity_in_use", "The policy cannot be moved or reduced below its current assignments.")
    previous = {"supervisor_id": policy.supervisor_id, "academic_cycle_id": policy.academic_cycle_id, "max_group_capacity": policy.max_group_capacity}
    policy.supervisor_id = payload.supervisor_id; policy.academic_cycle_id = payload.academic_cycle_id; policy.max_group_capacity = payload.max_group_capacity
    try:
        session.flush()
        add_admin_audit_event(session, actor_id=actor.id, affected_user_id=payload.supervisor_id, target_type="SUPERVISOR_CAPACITY_POLICY", target_id=policy.id, action="supervisor_capacity_updated", changed_values={"before": previous, "after": payload.model_dump()})
        session.commit(); session.refresh(policy)
    except IntegrityError as error:
        session.rollback()
        raise admin_user_error(status.HTTP_409_CONFLICT, "duplicate_capacity_policy", "A capacity policy already exists for this supervisor and cycle.") from error
    except SQLAlchemyError as error:
        session.rollback()
        raise admin_user_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "capacity_save_failed", "Supervisor capacity could not be saved.") from error
    return supervisor_capacity_out(policy, session)


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
    """Create a student account without accepting public role assignment."""
    full_name = registration.full_name.strip()
    registration_number = registration.registration_number.strip().upper()
    email = str(registration.email).strip().lower()

    if not full_name or len(full_name) > 255:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="full_name must be between 1 and 255 non-whitespace characters.",
        )
    if not registration_number or len(registration_number) > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="registration_number must be between 1 and 100 non-whitespace characters.",
        )
    if len(email) > 320:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="email must not exceed 320 characters.",
        )
    try:
        validate_password(registration.password)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    user = User(
        full_name=full_name,
        email=email,
        registration_number=registration_number,
        password_hash=hash_password(registration.password),
        role=UserRole.STUDENT,
    )
    session.add(user)
    try:
        session.flush()
        add_admin_audit_event(
            session,
            actor_id=user.id,
            affected_user_id=user.id,
            target_type="REGISTRATION",
            target_id=user.id,
            action="student_registration_created",
            changed_values={"registration_mode": registration_mode().value},
        )
        session.commit()
        session.refresh(user)
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email or registration number already exists.",
        ) from error

    return user


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
        if university_email in email_paths:
            raise registration_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "duplicate_request_university_email",
                "University emails must be unique within the team.",
                f"{prefix}.university_email",
            )
        registration_paths[registration_number] = prefix
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

        existing_user = session.execute(
            select(User.email, User.registration_number).where(
                or_(
                    User.email == shared_login_email,
                    User.registration_number == creator["registration_number"],
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

        existing_member = session.execute(
            select(TeamMember.registration_number, TeamMember.university_email).where(
                TeamMember.academic_cycle_id == cycle.id,
                TeamMember.is_active.is_(True),
                or_(
                    TeamMember.registration_number.in_(registration_paths),
                    TeamMember.university_email.in_(email_paths),
                ),
            )
        ).all()
        for registration_number, university_email in existing_member:
            if registration_number in registration_paths:
                raise registration_error(
                    status.HTTP_409_CONFLICT,
                    "member_registration_exists",
                    "An active member with that registration number already exists in this cycle.",
                    f"{registration_paths[registration_number]}.registration_number",
                )
            if university_email in email_paths:
                raise registration_error(
                    status.HTTP_409_CONFLICT,
                    "member_university_email_exists",
                    "An active member with that university email already exists in this cycle.",
                    f"{email_paths[university_email]}.university_email",
                )

        if roster_validation_required():
            # Import confirmation takes this same cycle lock before inserting roster rows.
            # Keep it until registration commits so the eligibility decision is stable.
            roster = session.execute(
                select(ApprovedStudent.registration_number, ApprovedStudent.university_email, ApprovedStudent.semester)
                .where(
                    ApprovedStudent.academic_cycle_id == cycle.id,
                    func.lower(ApprovedStudent.registration_number).in_(
                        [member["registration_number"].lower() for member in all_members]
                    ),
                )
            ).all()
            eligible = {
                (number.lower(), email.lower())
                for number, email, semester in roster if semester in (7, 8)
            }
            for index, member in enumerate(all_members):
                if (member["registration_number"].lower(), member["university_email"].lower()) not in eligible:
                    prefix = "creator" if index == 0 else f"members.{index - 1}"
                    raise registration_error(
                        status.HTTP_422_UNPROCESSABLE_CONTENT,
                        "student_not_eligible",
                        "Registration number and university email could not be verified for this academic cycle.",
                        f"{prefix}.registration_number",
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
                **member,
            )
            for index, member in enumerate(all_members)
        ]
        session.add_all(created_members)
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


from .audit_history import router as audit_history_router
app.include_router(audit_history_router)

from .student_roster import router as student_roster_router
app.include_router(student_roster_router)

from .workflow_policy import router as workflow_policy_router
app.include_router(workflow_policy_router)

from .supervisor_assignments import router as supervisor_assignments_router
app.include_router(supervisor_assignments_router)

from .group_channels import router as group_channels_router
app.include_router(group_channels_router)

from .group_ai import router as group_ai_router
app.include_router(group_ai_router)

from .team_matching import router as team_matching_router
app.include_router(team_matching_router)

from .match_chat import router as match_chat_router
app.include_router(match_chat_router)

from .individual_verification import router as individual_verification_router
app.include_router(individual_verification_router)

from .anonymous_verification import router as anonymous_verification_router
app.include_router(anonymous_verification_router)

from .join_requests import router as join_requests_router
app.include_router(join_requests_router)

from .invitations import router as invitations_router
app.include_router(invitations_router)

from .supervisor_requests import router as supervisor_requests_router
app.include_router(supervisor_requests_router)

from .proposal_reference import router as proposal_reference_router
app.include_router(proposal_reference_router)

from .supervisor_request_conversations import router as supervisor_request_conversations_router
app.include_router(supervisor_request_conversations_router)

from .archived_projects import router as archived_projects_router
app.include_router(archived_projects_router)

from .modules.module_03_proposal.router import router as module03_router
app.include_router(module03_router)
from .fyp_registry import router as fyp_registry_router
app.include_router(fyp_registry_router)
from .password_reset import router as password_reset_router
app.include_router(password_reset_router)
app.include_router(project_workflow_router)
