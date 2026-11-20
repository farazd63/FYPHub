from datetime import datetime, timezone
import logging
from pathlib import Path, PurePath
from secrets import token_hex
from zipfile import BadZipFile, ZipFile
from io import BytesIO
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from .auth import get_current_user, require_roles, validate_mutating_origin
from .database import get_db
from .models import AcademicCycle, DocumentArchiveReviewQueue, DocumentRequirementSection, DocumentSubmission, DocumentSubmissionReviewEvent, DocumentSubmissionVersion, DocumentUploadRequirement, SupervisorAssignment, SupervisorRequest, Team, TeamMember, User, UserRole
from .schemas.document_requirements import RequirementWrite, RequirementPatch, RequirementOut, ReviewEventOut, SubmissionOut, VersionOut
from .config import settings
from .document_preview import DocumentPreviewError, render_document_preview

router = APIRouter(prefix="/api/v1/document-requirements", tags=["document-requirements"])
student_router = APIRouter(tags=["document-requirements"])
ADMIN = (UserRole.ADMIN, UserRole.COORDINATOR)
logger = logging.getLogger(__name__)
SECTION_STATUS = {"DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED", "ACTIVE"}
MIMES = {"pdf":"application/pdf","doc":"application/msword","docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document","tex":"application/x-tex","txt":"text/plain","md":"text/markdown","jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","gif":"image/gif","webp":"image/webp","svg":"image/svg+xml","mp4":"video/mp4","mov":"video/quicktime","avi":"video/x-msvideo","mkv":"video/x-matroska","webm":"video/webm","mp3":"audio/mpeg","wav":"audio/wav","m4a":"audio/mp4","ogg":"audio/ogg","xls":"application/vnd.ms-excel","xlsx":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","csv":"text/csv","ppt":"application/vnd.ms-powerpoint","pptx":"application/vnd.openxmlformats-officedocument.presentationml.presentation","zip":"application/zip","rar":"application/vnd.rar","7z":"application/x-7z-compressed"}

def _audit(db, actor, action, target, values=None, affected=None):
    from .main import add_admin_audit_event
    add_admin_audit_event(db, actor_id=actor.id, affected_user_id=affected, target_type=target, target_id=getattr(target, "id", None) if not isinstance(target, int) else target, action=action, changed_values=values or {})

def _student_cycle_ids(user, db):
    """Resolve the student's current cycle without trusting a client-supplied cycle."""
    team_cycle_ids = set(db.scalars(select(Team.academic_cycle_id).where(Team.shared_user_id == user.id, Team.status != "dissolved")).all())
    member_cycle_ids = set(db.scalars(select(TeamMember.academic_cycle_id).where(
        TeamMember.is_active.is_(True),
        or_(TeamMember.registration_number == user.registration_number, TeamMember.university_email == user.email),
    )).all())
    cycle_ids = team_cycle_ids | member_cycle_ids
    if cycle_ids:
        return cycle_ids
    latest = db.scalar(select(AcademicCycle.id).order_by(AcademicCycle.id.desc()))
    return {latest} if latest is not None else set()


def _student_team_ids(user, db):
    team_ids = set(db.scalars(select(Team.id).where(Team.shared_user_id == user.id)).all())
    team_ids.update(db.scalars(select(TeamMember.team_id).where(
        TeamMember.is_active.is_(True),
        or_(TeamMember.registration_number == user.registration_number, TeamMember.university_email == user.email),
    )).all())
    return team_ids


def _student_group(user, db):
    member_match = select(TeamMember.id).where(
        TeamMember.team_id == Team.id,
        TeamMember.academic_cycle_id == Team.academic_cycle_id,
        TeamMember.is_active.is_(True),
        or_(TeamMember.registration_number == user.registration_number, TeamMember.university_email == user.email),
    ).exists()
    return db.scalar(select(Team).where(Team.status != "dissolved", (Team.shared_user_id == user.id) | member_match).order_by(Team.id).limit(1))


def _current_active_cycle_id(db):
    return db.scalar(select(AcademicCycle.id).where(AcademicCycle.registration_open.is_(True)).order_by(AcademicCycle.id).limit(1))


def _visible(req, user, db=None):
    if user.role in ADMIN:
        return True
    if req.status not in {"PUBLISHED", "CLOSED", "ACTIVE"}:
        return False
    visible_roles = {str(role).upper() for role in (req.visible_to_roles or [])}
    if user.role != UserRole.STUDENT or "STUDENT" not in visible_roles:
        return False
    if req.assigned_user_id is not None and req.assigned_user_id != user.id:
        return False
    if db is None or req.academic_cycle_id not in _student_cycle_ids(user, db):
        return False
    return req.assigned_group_id is None or req.assigned_group_id in _student_team_ids(user, db)


def _supervisor_can_review(row, req, user, db):
    """Allow a supervisor to review only submissions from their active group."""
    if user.role != UserRole.SUPERVISOR or row.group_id is None or req is None:
        return False
    assigned = db.scalar(select(SupervisorAssignment.id).where(
        SupervisorAssignment.team_id == row.group_id,
        SupervisorAssignment.supervisor_id == user.id,
        SupervisorAssignment.ended_at.is_(None),
    )) is not None
    if assigned:
        return True
    return db.scalar(select(SupervisorRequest.id).where(
        SupervisorRequest.team_id == row.group_id,
        SupervisorRequest.supervisor_id == user.id,
        SupervisorRequest.academic_cycle_id == req.academic_cycle_id,
        SupervisorRequest.status.in_(["SUBMITTED", "CHANGES_REQUESTED"]),
    )) is not None

def _out(req, db=None):
    result = RequirementOut.model_validate(req)
    if db is not None:
        result = result.model_copy(update={"submission_count": int(db.scalar(select(func.count(DocumentSubmission.id)).where(DocumentSubmission.requirement_id == req.id)) or 0)})
    return result
def _now(): return datetime.now(timezone.utc)
def _stored_path(reference: str) -> Path:
    root = settings.document_storage_root.resolve()
    candidate = (root / reference).resolve()
    if root != candidate and root not in candidate.parents:
        raise HTTPException(400, "Invalid storage reference.")
    return candidate


def _section_code(value: str) -> str:
    normalized = "_".join(value.strip().casefold().split())
    return "".join(character for character in normalized if character.isalnum() or character == "_")[:80] or "general"


def _requirement_section(db: Session, cycle_id: int, module: str | None) -> DocumentRequirementSection:
    name = (module or "General").strip() or "General"
    code = _section_code(name)
    section = db.scalar(select(DocumentRequirementSection).where(DocumentRequirementSection.academic_cycle_id == cycle_id, DocumentRequirementSection.code == code))
    if section is not None:
        return section
    last_order = db.scalar(select(func.max(DocumentRequirementSection.display_order)).where(DocumentRequirementSection.academic_cycle_id == cycle_id))
    section = DocumentRequirementSection(academic_cycle_id=cycle_id, code=code, name=name, display_order=(last_order + 1 if last_order is not None else 0))
    db.add(section)
    db.flush()
    return section


def _project_for_group(db: Session, group_id: int, cycle_id: int) -> SupervisorRequest | None:
    return db.scalar(select(SupervisorRequest).where(SupervisorRequest.team_id == group_id, SupervisorRequest.academic_cycle_id == cycle_id, SupervisorRequest.status.not_in(["WITHDRAWN", "REJECTED"])).order_by(SupervisorRequest.updated_at.desc(), SupervisorRequest.id.desc()).limit(1))

@router.post("", response_model=RequirementOut, status_code=201)
def create_requirement(payload: RequirementWrite, _: object = Depends(validate_mutating_origin), actor: User = Depends(require_roles(*ADMIN)), db: Session = Depends(get_db)):
    try:
        values = payload.model_dump(exclude={"due_date", "assigned_to", "academic_cycle_id", "due_at", "description", "module", "visible_to_roles", "allowed_file_types", "assigned_user_id", "assigned_group_id"})
        due = payload.due_date or payload.due_at
        if due is None: raise HTTPException(422, "Deadline is required.")
        cycle_id = payload.academic_cycle_id or _current_active_cycle_id(db)
        if cycle_id is None: raise HTTPException(422, "No academic cycle is available.")
        assignment = (payload.assigned_to or "ALL_STUDENTS").strip()
        assigned_user_id = None
        if assignment.upper() != "ALL_STUDENTS":
            try: assigned_user_id = int(assignment)
            except ValueError: raise HTTPException(422, "Assigned To must be All Students or a valid student selector.") from None
            assigned = db.get(User, assigned_user_id)
            if assigned is None or assigned.role != UserRole.STUDENT: raise HTTPException(422, "Assigned To must identify a student.")
        assigned_group_id = payload.assigned_group_id
        if assigned_group_id is not None:
            assigned_group = db.get(Team, assigned_group_id)
            if assigned_group is None or assigned_group.status == "dissolved": raise HTTPException(422, "Assigned group was not found.")
            if assigned_group.academic_cycle_id != cycle_id: raise HTTPException(422, "Assigned group belongs to a different academic cycle.")
            if assigned_user_id is not None: raise HTTPException(422, "Choose either a student or a group assignment, not both.")
        section = _requirement_section(db, cycle_id, payload.module)
        req = DocumentUploadRequirement(**values, description=payload.description, academic_cycle_id=cycle_id, section_id=section.id, module=section.name, visible_to_roles=["STUDENT"], assigned_user_id=assigned_user_id, assigned_group_id=assigned_group_id, due_at=due, created_by_id=actor.id, status="DRAFT", allowed_file_types=payload.allowed_file_types)
        db.add(req); db.flush(); _audit(db, actor, "document_requirement_created", req.id, {"status": req.status}); db.commit(); db.refresh(req); return _out(req, db)
    except HTTPException:
        db.rollback()
        raise
    except (SQLAlchemyError, TypeError, ValueError):
        db.rollback()
        logger.exception("document_requirement_create_failed", extra={"error_type": "persistence_or_mapping_error"})
        raise HTTPException(500, "The document requirement could not be created.") from None

@router.delete("/{requirement_id}", status_code=204)
def delete_requirement(requirement_id: int, _: object = Depends(validate_mutating_origin), actor: User = Depends(require_roles(*ADMIN)), db: Session = Depends(get_db)):
    """Remove an unused draft requirement while preserving published/history records."""
    req = db.get(DocumentUploadRequirement, requirement_id)
    if req is None:
        raise HTTPException(404, "Requirement not found.")
    if req.status != "DRAFT":
        raise HTTPException(409, "Only draft requirements can be deleted; archive active requirements instead.")
    submissions = db.scalar(select(func.count(DocumentSubmission.id)).where(DocumentSubmission.requirement_id == req.id)) or 0
    if submissions:
        raise HTTPException(409, "This requirement has student submissions and cannot be deleted.")
    _audit(db, actor, "document_requirement_deleted", req.id, {"status": req.status})
    db.delete(req)
    try:
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(409, "This requirement is in use and cannot be deleted.") from error


@router.get("", response_model=list[RequirementOut])
def list_requirements(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(DocumentUploadRequirement).order_by(DocumentUploadRequirement.due_at)).all()
    return [_out(r, db) for r in rows if _visible(r, actor, db)]

@router.get("/{requirement_id}", response_model=RequirementOut)
@student_router.get("/api/v1/student/group/requirements/{requirement_id}", response_model=RequirementOut)
def get_requirement(requirement_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = db.get(DocumentUploadRequirement, requirement_id)
    if req is None or not _visible(req, actor, db):
        raise HTTPException(404, "Requirement not found.")
    return _out(req, db)

@router.patch("/{requirement_id}", response_model=RequirementOut)
def update_requirement(requirement_id: int, payload: RequirementPatch, _: object = Depends(validate_mutating_origin), actor: User = Depends(require_roles(*ADMIN)), db: Session = Depends(get_db)):
    req = db.get(DocumentUploadRequirement, requirement_id)
    if not req: raise HTTPException(404, "Requirement not found.")
    if req.status == "ARCHIVED": raise HTTPException(409, "Archived requirements cannot be edited.")
    changes = payload.model_dump(exclude_unset=True)
    if "module" in changes:
        section = _requirement_section(db, req.academic_cycle_id, changes["module"])
        req.section_id = section.id
        changes["module"] = section.name
    for key, value in changes.items(): setattr(req, key, value)
    _audit(db, actor, "document_requirement_updated", req.id, {"status": req.status}); db.commit(); db.refresh(req); return _out(req, db)

def _state(requirement_id, action, actor, db, late=False):
    req = db.get(DocumentUploadRequirement, requirement_id)
    if not req: raise HTTPException(404, "Requirement not found.")
    if action == "PUBLISHED" and req.status == "ARCHIVED":
        raise HTTPException(409, "Archived requirements cannot be published.")
    req.status = action
    if action == "PUBLISHED" and late: req.late_upload_allowed = True
    _audit(db, actor, {"PUBLISHED":"document_requirement_published", "CLOSED":"document_requirement_closed", "ARCHIVED":"document_requirement_archived", "DRAFT":"document_requirement_unpublished"}.get(action, "document_requirement_updated"), req.id, {"status": action}); db.commit(); db.refresh(req); return _out(req, db)

@router.post("/{requirement_id}/publish", response_model=RequirementOut)
def publish(requirement_id: int, _: object = Depends(validate_mutating_origin), actor: User = Depends(require_roles(*ADMIN)), db: Session = Depends(get_db)): return _state(requirement_id, "PUBLISHED", actor, db)
@router.post("/{requirement_id}/unpublish", response_model=RequirementOut)
def unpublish(requirement_id: int, _: object = Depends(validate_mutating_origin), actor: User = Depends(require_roles(*ADMIN)), db: Session = Depends(get_db)): return _state(requirement_id, "DRAFT", actor, db)
@router.post("/{requirement_id}/close", response_model=RequirementOut)
def close(requirement_id: int, _: object = Depends(validate_mutating_origin), actor: User = Depends(require_roles(*ADMIN)), db: Session = Depends(get_db)): return _state(requirement_id, "CLOSED", actor, db)
@router.post("/{requirement_id}/archive", response_model=RequirementOut)
def archive(requirement_id: int, _: object = Depends(validate_mutating_origin), actor: User = Depends(require_roles(*ADMIN)), db: Session = Depends(get_db)): return _state(requirement_id, "ARCHIVED", actor, db)
@router.post("/{requirement_id}/reopen", response_model=RequirementOut)
def reopen(requirement_id: int, _: object = Depends(validate_mutating_origin), actor: User = Depends(require_roles(*ADMIN)), db: Session = Depends(get_db)): return _state(requirement_id, "PUBLISHED", actor, db, True)

def _submission(req, actor, db):
    if not _visible(req, actor, db): raise HTTPException(403, "You are not authorized for this requirement.")
    group = _student_group(actor, db) if actor.role == UserRole.STUDENT else None
    statement = select(DocumentSubmission).where(DocumentSubmission.requirement_id == req.id)
    if group is not None:
        statement = statement.where(or_(DocumentSubmission.group_id == group.id, DocumentSubmission.student_id == actor.id))
    else:
        statement = statement.where(DocumentSubmission.student_id == actor.id)
    row = db.scalar(statement.order_by(DocumentSubmission.id.desc()))
    return row

def _validate(req, upload, data):
    suffix = PurePath(upload.filename or "").suffix.lower().lstrip(".")
    if suffix not in (req.allowed_file_types or []): raise HTTPException(422, "File type is not allowed.")
    if upload.content_type != MIMES[suffix]: raise HTTPException(422, "File MIME type does not match the extension.")
    if not data or len(data) > req.max_file_size_mb * 1024 * 1024: raise HTTPException(413, "File is empty or exceeds the configured size limit.")
    signatures = {key: False for key in MIMES}
    signatures.update({"pdf": data.startswith(b"%PDF-"), "doc": data.startswith(bytes.fromhex("D0CF11E0A1B11AE1")), "txt": True, "md": True, "tex": True, "csv": True, "svg": data.lstrip().startswith(b"<svg"), "jpg": data.startswith(b"\xff\xd8\xff"), "jpeg": data.startswith(b"\xff\xd8\xff"), "png": data.startswith(b"\x89PNG\r\n\x1a\n"), "gif": data.startswith((b"GIF87a", b"GIF89a")), "webp": data.startswith(b"RIFF") and data[8:12] == b"WEBP", "zip": data.startswith(b"PK"), "rar": data.startswith(b"Rar!\x1a\x07"), "7z": data.startswith(b"7z\xbc\xaf\x27\x1c")})
    if suffix == "docx":
        try: signatures["docx"] = data.startswith(b"PK") and "[Content_Types].xml" in ZipFile(BytesIO(data)).namelist()
        except BadZipFile: signatures["docx"] = False
    for office in ("xlsx", "pptx"):
        try: signatures[office] = data.startswith(b"PK") and "[Content_Types].xml" in ZipFile(BytesIO(data)).namelist()
        except BadZipFile: signatures[office] = False
    for media in ("mp4", "mov", "m4a"):
        signatures[media] = len(data) > 12 and (data[4:8] == b"ftyp" or data[4:12] == b"ftyp")
    signatures["wav"] = data.startswith(b"RIFF") and data[8:12] == b"WAVE"
    signatures["ogg"] = data.startswith(b"OggS")
    signatures["avi"] = data.startswith(b"RIFF") and data[8:12] == b"AVI "
    signatures["mkv"] = data.startswith(b"\x1a\x45\xdf\xa3")
    if not signatures[suffix]: raise HTTPException(422, "File signature is invalid.")
    return suffix

def _submission_out(row, db):
    versions = db.scalars(select(DocumentSubmissionVersion).where(DocumentSubmissionVersion.submission_id == row.id).order_by(DocumentSubmissionVersion.version_number)).all()
    events = db.scalars(select(DocumentSubmissionReviewEvent).where(DocumentSubmissionReviewEvent.submission_id == row.id).order_by(DocumentSubmissionReviewEvent.created_at, DocumentSubmissionReviewEvent.id)).all()
    reviewer_ids = {event.reviewer_id for event in events}
    reviewers = {user.id: user for user in db.scalars(select(User).where(User.id.in_(reviewer_ids))).all()} if reviewer_ids else {}
    return SubmissionOut(
        id=row.id, requirement_id=row.requirement_id, academic_cycle_id=row.academic_cycle_id, group_id=row.group_id, project_id=row.project_id,
        requirement_section_id=row.requirement_section_id, student_id=row.student_id, uploader_id=row.uploaded_by_id, status=row.status,
        is_late=row.is_late, review_comment=row.review_comment, reviewed_by_id=row.reviewed_by_id, reviewed_at=row.reviewed_at,
        uploaded_at=row.uploaded_at, updated_at=row.updated_at,
        versions=[VersionOut.model_validate(v).model_copy(update={"uploaded_by_id": v.uploaded_by_id, "download_url": f"/api/v1/document-requirements/submissions/{row.id}/versions/{v.id}/download", "preview_url": f"/api/v1/document-requirements/submissions/{row.id}/versions/{v.id}/preview"}) for v in versions],
        review_history=[ReviewEventOut(id=event.id, status=event.status, version_id=event.version_id, reviewer_id=event.reviewer_id, reviewer_name=reviewers.get(event.reviewer_id).full_name if reviewers.get(event.reviewer_id) else None, comment=event.comment, created_at=event.created_at) for event in events],
    )

@router.get("/student", response_model=list[RequirementOut])
@student_router.get("/api/v1/student/document-requirements", response_model=list[RequirementOut])
@student_router.get("/api/v1/student/group/requirements", response_model=list[RequirementOut])
def student_requirements(actor: User = Depends(require_roles(UserRole.STUDENT)), db: Session = Depends(get_db)):
    group = _student_group(actor, db)
    cycle_id = group.academic_cycle_id if group is not None else _current_active_cycle_id(db)
    requirements = db.scalars(select(DocumentUploadRequirement).where(DocumentUploadRequirement.status.in_(["PUBLISHED", "CLOSED", "ACTIVE"]), DocumentUploadRequirement.academic_cycle_id == cycle_id).order_by(DocumentUploadRequirement.due_at, DocumentUploadRequirement.id)).all() if cycle_id is not None else []
    return [_out(r, db) for r in requirements if _visible(r, actor, db)]

@router.post("/{requirement_id}/upload", response_model=SubmissionOut)
@student_router.post("/api/v1/student/group/requirements/{requirement_id}/upload", response_model=SubmissionOut)
@student_router.post("/api/v1/student/group/requirements/{requirement_id}/resubmit", response_model=SubmissionOut)
async def upload(requirement_id: int, file: UploadFile = File(...), _: object = Depends(validate_mutating_origin), actor: User = Depends(require_roles(UserRole.STUDENT)), db: Session = Depends(get_db)):
    req = db.get(DocumentUploadRequirement, requirement_id)
    if not req or req.status not in {"PUBLISHED", "CLOSED", "ACTIVE"}: raise HTTPException(404, "Requirement is not available.")
    if req.status == "CLOSED": raise HTTPException(409, "This requirement is closed and cannot accept uploads.")
    if not _visible(req, actor, db): raise HTTPException(403, "You are not authorized for this requirement.")
    late = _now() > req.due_at
    if late and not req.late_upload_allowed: raise HTTPException(409, "The deadline has passed; late uploads are closed.")
    data = await file.read(); suffix = _validate(req, file, data)
    group = _student_group(actor, db)
    if group is None or group.academic_cycle_id != req.academic_cycle_id: raise HTTPException(409, "Your group is not assigned to this academic cycle.")
    project = _project_for_group(db, group.id, req.academic_cycle_id)
    if project is None: raise HTTPException(409, "Your group does not have a project record for this academic cycle yet.")
    row = db.scalar(select(DocumentSubmission).where(DocumentSubmission.requirement_id == req.id, DocumentSubmission.group_id == group.id))
    if row is None: row = DocumentSubmission(requirement_id=req.id, student_id=actor.id, group_id=group.id, academic_cycle_id=req.academic_cycle_id, project_id=project.id, requirement_section_id=req.section_id, uploaded_by_id=actor.id, status="UPLOADED", is_late=late); db.add(row); db.flush()
    else: row.status = "UPLOADED"; row.is_late = row.is_late or late; row.project_id = row.project_id or project.id; row.requirement_section_id = row.requirement_section_id or req.section_id
    row.uploaded_by_id = actor.id
    previous = db.scalar(select(DocumentSubmissionVersion.version_number).where(DocumentSubmissionVersion.submission_id == row.id).order_by(DocumentSubmissionVersion.version_number.desc())) or 0
    stored = f"document-requirements/{req.id}/{actor.id}/{token_hex(16)}.{suffix}"
    path = _stored_path(stored); path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_suffix(path.suffix + ".uploading")
    try:
        temporary.write_bytes(data); temporary.replace(path)
        version = DocumentSubmissionVersion(submission_id=row.id, version_number=previous + 1, original_filename=PurePath(file.filename or "upload").name, stored_filename=stored.rsplit("/", 1)[-1], mime_type=file.content_type or MIMES[suffix], file_size=len(data), storage_reference=stored, content=None, uploaded_by_id=actor.id)
        db.add(version); db.flush(); _audit(db, actor, "document_late_upload" if late else ("document_file_replaced" if previous else "document_file_uploaded"), row.id, {"version": version.version_number, "file_size": len(data), "mime_type": version.mime_type}, actor.id if late else None); db.commit(); db.refresh(row); return _submission_out(row, db)
    except Exception:
        db.rollback()
        if path.exists(): path.unlink()
        if temporary.exists(): temporary.unlink()
        raise

@router.get("/{requirement_id}/submission", response_model=SubmissionOut)
@student_router.get("/api/v1/student/group/requirements/{requirement_id}/submission", response_model=SubmissionOut)
def submission(requirement_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = db.get(DocumentUploadRequirement, requirement_id); row = _submission(req, actor, db) if req else None
    if row is None: raise HTTPException(404, "Submission not found.")
    return _submission_out(row, db)


@router.get("/{requirement_id}/submissions")
def all_submissions(requirement_id: int, actor: User = Depends(require_roles(*ADMIN)), db: Session = Depends(get_db)):
    """Return every student's submission and every uploaded version for an admin requirement view."""
    req = db.get(DocumentUploadRequirement, requirement_id)
    if req is None:
        raise HTTPException(404, "Requirement not found.")
    rows = db.scalars(select(DocumentSubmission).where(DocumentSubmission.requirement_id == req.id).order_by(DocumentSubmission.uploaded_at.desc(), DocumentSubmission.id.desc())).all()
    result = []
    for row in rows:
        student = db.get(User, row.student_id)
        group = db.get(Team, row.group_id) if row.group_id is not None else None
        submission = _submission_out(row, db)
        result.append({
            **submission.model_dump(mode="json"),
            "student": {"id": student.id, "name": student.full_name, "email": student.email, "registration_number": student.registration_number} if student else {"id": row.student_id, "name": "Unknown student", "email": None, "registration_number": None},
            "group_id": group.id if group else row.group_id,
        })
    return result

@router.get("/{requirement_id}/submission/versions", response_model=list[VersionOut])
def versions(requirement_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = db.get(DocumentUploadRequirement, requirement_id); row = _submission(req, actor, db) if req else None
    if row is None: raise HTTPException(404, "Submission not found.")
    return [VersionOut.model_validate(v).model_copy(update={"download_url": f"/api/v1/document-requirements/submissions/{row.id}/versions/{v.id}/download", "preview_url": f"/api/v1/document-requirements/submissions/{row.id}/versions/{v.id}/preview"}) for v in db.scalars(select(DocumentSubmissionVersion).where(DocumentSubmissionVersion.submission_id == row.id).order_by(DocumentSubmissionVersion.version_number)).all()]

@router.get("/submissions/{submission_id}/versions/{version_id}/download")
def download(submission_id: int, version_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row, version = _authorized_version(submission_id, version_id, actor, db)
    path = _stored_path(version.storage_reference)
    if not path.is_file(): raise HTTPException(410, "The stored document is no longer available.")
    return FileResponse(path, media_type=version.mime_type, filename=version.original_filename)


def _authorized_version(submission_id: int, version_id: int, actor: User, db: Session):
    row = db.get(DocumentSubmission, submission_id); version = db.get(DocumentSubmissionVersion, version_id)
    if not row or not version or version.submission_id != row.id: raise HTTPException(404, "Document version not found.")
    req = db.get(DocumentUploadRequirement, row.requirement_id)
    assigned = _supervisor_can_review(row, req, actor, db)
    if actor.role not in ADMIN and not (actor.role == UserRole.STUDENT and (row.student_id == actor.id or row.group_id in _student_team_ids(actor, db))) and not assigned: raise HTTPException(403, "You are not authorized to view this document.")
    return row, version


@router.get("/submissions/{submission_id}/versions/{version_id}/preview")
def preview(submission_id: int, version_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return an authorized document version for inline in-app viewing.

    The original upload is never changed. PDF and DOCX files are rendered by
    the shared preview utility; browser-readable media is returned inline.
    """
    _, version = _authorized_version(submission_id, version_id, actor, db)
    path = _stored_path(version.storage_reference)
    if not path.is_file(): raise HTTPException(410, "The stored document is no longer available.")
    try:
        rendered = render_document_preview(path, version.mime_type, version.original_filename, settings.document_storage_root)
    except DocumentPreviewError as error:
        browser_inline = {"image/", "audio/", "video/"}
        if not any(version.mime_type.casefold().startswith(prefix) for prefix in browser_inline):
            raise HTTPException(415, error.message) from error
        rendered = None
    headers = {"Content-Disposition": f'inline; filename="{PurePath(version.original_filename).name.replace(chr(34), "")}"'}
    if rendered is not None:
        headers["X-Preview-Page-Count"] = str(rendered.page_count)
        headers["X-Preview-Conversion"] = rendered.conversion
        return Response(content=rendered.content, media_type=rendered.media_type, headers=headers)
    return FileResponse(path, media_type=version.mime_type, headers=headers)

def _review(requirement_id, submission_id, decision, comment, actor, db):
    req = db.get(DocumentUploadRequirement, requirement_id); row = db.get(DocumentSubmission, submission_id)
    if not req or not row or row.requirement_id != req.id: raise HTTPException(404, "Submission not found.")
    if actor.role not in ADMIN and not _supervisor_can_review(row, req, actor, db): raise HTTPException(403, "You are not authorized to review this document.")
    row.status = decision; row.review_comment = comment; row.reviewed_by_id = actor.id; row.reviewed_at = _now()
    latest_version = db.scalar(select(DocumentSubmissionVersion).where(DocumentSubmissionVersion.submission_id == row.id).order_by(DocumentSubmissionVersion.version_number.desc()).limit(1))
    db.add(DocumentSubmissionReviewEvent(submission_id=row.id, version_id=latest_version.id if latest_version else None, status=decision, reviewer_id=actor.id, comment=comment, created_at=row.reviewed_at))
    _audit(db, actor, "document_submission_" + decision.lower(), row.id, {"status": decision}, row.student_id); db.commit(); db.refresh(row); return _submission_out(row, db)

@router.post("/{requirement_id}/submissions/{submission_id}/approve", response_model=SubmissionOut)
def approve(requirement_id:int, submission_id:int, _: object=Depends(validate_mutating_origin), actor:User=Depends(get_current_user), db:Session=Depends(get_db)): return _review(requirement_id, submission_id, "ACCEPTED", None, actor, db)
@router.post("/{requirement_id}/submissions/{submission_id}/under-review", response_model=SubmissionOut)
def under_review(requirement_id:int, submission_id:int, _: object=Depends(validate_mutating_origin), actor:User=Depends(get_current_user), db:Session=Depends(get_db)): return _review(requirement_id, submission_id, "UNDER_REVIEW", None, actor, db)
@router.post("/{requirement_id}/submissions/{submission_id}/reject", response_model=SubmissionOut)
def reject(requirement_id:int, submission_id:int, comment:str|None=None, _: object=Depends(validate_mutating_origin), actor:User=Depends(get_current_user), db:Session=Depends(get_db)): return _review(requirement_id, submission_id, "REJECTED", comment, actor, db)
@router.post("/{requirement_id}/submissions/{submission_id}/request-replacement", response_model=SubmissionOut)
@router.post("/{requirement_id}/submissions/{submission_id}/request-changes", response_model=SubmissionOut)
def replacement(requirement_id:int, submission_id:int, comment:str|None=None, _: object=Depends(validate_mutating_origin), actor:User=Depends(get_current_user), db:Session=Depends(get_db)): return _review(requirement_id, submission_id, "RESUBMISSION_REQUIRED", comment, actor, db)
