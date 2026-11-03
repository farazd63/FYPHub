from datetime import datetime, timezone
import logging
from pathlib import Path, PurePath
from secrets import token_hex
from zipfile import BadZipFile, ZipFile
from io import BytesIO
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from .auth import get_current_user, require_roles, validate_mutating_origin
from .database import get_db
from .models import AcademicCycle, DocumentUploadRequirement, DocumentSubmission, DocumentSubmissionVersion, TeamMember, User, UserRole
from .schemas.document_requirements import RequirementWrite, RequirementPatch, RequirementOut, SubmissionOut, VersionOut
from .config import settings

router = APIRouter(prefix="/api/v1/document-requirements", tags=["document-requirements"])
student_router = APIRouter(tags=["document-requirements"])
ADMIN = (UserRole.ADMIN, UserRole.COORDINATOR)
logger = logging.getLogger(__name__)
SECTION_STATUS = {"DRAFT", "ACTIVE", "ARCHIVED"}
MIMES = {"pdf":"application/pdf","doc":"application/msword","docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document","tex":"application/x-tex","txt":"text/plain","md":"text/markdown","jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","gif":"image/gif","webp":"image/webp","svg":"image/svg+xml","mp4":"video/mp4","mov":"video/quicktime","avi":"video/x-msvideo","mkv":"video/x-matroska","webm":"video/webm","mp3":"audio/mpeg","wav":"audio/wav","m4a":"audio/mp4","ogg":"audio/ogg","xls":"application/vnd.ms-excel","xlsx":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","csv":"text/csv","ppt":"application/vnd.ms-powerpoint","pptx":"application/vnd.openxmlformats-officedocument.presentationml.presentation","zip":"application/zip","rar":"application/vnd.rar","7z":"application/x-7z-compressed"}

def _audit(db, actor, action, target, values=None, affected=None):
    from .main import add_admin_audit_event
    add_admin_audit_event(db, actor_id=actor.id, affected_user_id=affected, target_type=target, target_id=getattr(target, "id", None) if not isinstance(target, int) else target, action=action, changed_values=values or {})

def _visible(req, user):
    return user.role in ADMIN or (user.role == UserRole.STUDENT and "STUDENT" in (req.visible_to_roles or []) and (req.assigned_user_id is None or req.assigned_user_id == user.id))

def _out(req): return RequirementOut.model_validate(req)
def _now(): return datetime.now(timezone.utc)
def _stored_path(reference: str) -> Path:
    root = settings.document_storage_root.resolve()
    candidate = (root / reference).resolve()
    if root != candidate and root not in candidate.parents:
        raise HTTPException(400, "Invalid storage reference.")
    return candidate

@router.post("", response_model=RequirementOut, status_code=201)
def create_requirement(payload: RequirementWrite, _: object = Depends(validate_mutating_origin), actor: User = Depends(require_roles(*ADMIN)), db: Session = Depends(get_db)):
    try:
        values = payload.model_dump(exclude={"due_date", "assigned_to", "academic_cycle_id", "due_at", "description", "module", "visible_to_roles", "allowed_file_types", "assigned_user_id", "assigned_group_id"})
        due = payload.due_date or payload.due_at
        if due is None: raise HTTPException(422, "Deadline is required.")
        cycle_id = payload.academic_cycle_id or db.scalar(select(AcademicCycle.id).order_by(AcademicCycle.id.desc()))
        if cycle_id is None: raise HTTPException(422, "No academic cycle is available.")
        assignment = (payload.assigned_to or "ALL_STUDENTS").strip()
        assigned_user_id = None
        if assignment.upper() != "ALL_STUDENTS":
            try: assigned_user_id = int(assignment)
            except ValueError: raise HTTPException(422, "Assigned To must be All Students or a valid student selector.") from None
            assigned = db.get(User, assigned_user_id)
            if assigned is None or assigned.role != UserRole.STUDENT: raise HTTPException(422, "Assigned To must identify a student.")
        req = DocumentUploadRequirement(**values, description=payload.description, academic_cycle_id=cycle_id, module=payload.module or "General", visible_to_roles=["STUDENT"], assigned_user_id=assigned_user_id, due_at=due, created_by_id=actor.id, status="DRAFT", allowed_file_types=payload.allowed_file_types)
        db.add(req); db.flush(); _audit(db, actor, "document_requirement_created", req.id, {"status": req.status}); db.commit(); db.refresh(req); return _out(req)
    except HTTPException:
        db.rollback()
        raise
    except (SQLAlchemyError, TypeError, ValueError):
        db.rollback()
        logger.exception("document_requirement_create_failed", extra={"error_type": "persistence_or_mapping_error"})
        raise HTTPException(500, "The document requirement could not be created.") from None

@router.get("", response_model=list[RequirementOut])
def list_requirements(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(DocumentUploadRequirement).order_by(DocumentUploadRequirement.due_at)).all()
    return [_out(r) for r in rows if _visible(r, actor)]

@router.get("/{requirement_id}", response_model=RequirementOut)
def get_requirement(requirement_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = db.get(DocumentUploadRequirement, requirement_id)
    if req is None or not _visible(req, actor):
        raise HTTPException(404, "Requirement not found.")
    return _out(req)

@router.patch("/{requirement_id}", response_model=RequirementOut)
def update_requirement(requirement_id: int, payload: RequirementPatch, _: object = Depends(validate_mutating_origin), actor: User = Depends(require_roles(*ADMIN)), db: Session = Depends(get_db)):
    req = db.get(DocumentUploadRequirement, requirement_id)
    if not req: raise HTTPException(404, "Requirement not found.")
    if req.status == "ARCHIVED": raise HTTPException(409, "Archived requirements cannot be edited.")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(req, key, value)
    _audit(db, actor, "document_requirement_updated", req.id, {"status": req.status}); db.commit(); db.refresh(req); return _out(req)

def _state(requirement_id, action, actor, db, late=False):
    req = db.get(DocumentUploadRequirement, requirement_id)
    if not req: raise HTTPException(404, "Requirement not found.")
    req.status = action
    if action == "ACTIVE" and late: req.late_upload_allowed = True
    _audit(db, actor, {"ACTIVE":"document_requirement_published", "ARCHIVED":"document_requirement_archived"}.get(action, "document_requirement_reopened"), req.id, {"status": action}); db.commit(); db.refresh(req); return _out(req)

@router.post("/{requirement_id}/publish", response_model=RequirementOut)
def publish(requirement_id: int, _: object = Depends(validate_mutating_origin), actor: User = Depends(require_roles(*ADMIN)), db: Session = Depends(get_db)): return _state(requirement_id, "ACTIVE", actor, db)
@router.post("/{requirement_id}/archive", response_model=RequirementOut)
def archive(requirement_id: int, _: object = Depends(validate_mutating_origin), actor: User = Depends(require_roles(*ADMIN)), db: Session = Depends(get_db)): return _state(requirement_id, "ARCHIVED", actor, db)
@router.post("/{requirement_id}/reopen", response_model=RequirementOut)
def reopen(requirement_id: int, _: object = Depends(validate_mutating_origin), actor: User = Depends(require_roles(*ADMIN)), db: Session = Depends(get_db)): return _state(requirement_id, "ACTIVE", actor, db, True)

def _submission(req, actor, db):
    if not _visible(req, actor): raise HTTPException(403, "You are not authorized for this requirement.")
    row = db.scalar(select(DocumentSubmission).where(DocumentSubmission.requirement_id == req.id, DocumentSubmission.student_id == actor.id))
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
    return SubmissionOut(id=row.id, requirement_id=row.requirement_id, status=row.status, is_late=row.is_late, review_comment=row.review_comment, uploaded_at=row.uploaded_at, updated_at=row.updated_at, versions=[VersionOut.model_validate(v) for v in versions])

@router.get("/student", response_model=list[RequirementOut])
@student_router.get("/api/v1/student/document-requirements", response_model=list[RequirementOut])
def student_requirements(actor: User = Depends(require_roles(UserRole.STUDENT)), db: Session = Depends(get_db)):
    return [_out(r) for r in db.scalars(select(DocumentUploadRequirement).where(DocumentUploadRequirement.status == "ACTIVE").order_by(DocumentUploadRequirement.due_at)).all() if _visible(r, actor)]

@router.post("/{requirement_id}/upload", response_model=SubmissionOut)
async def upload(requirement_id: int, file: UploadFile = File(...), _: object = Depends(validate_mutating_origin), actor: User = Depends(require_roles(UserRole.STUDENT)), db: Session = Depends(get_db)):
    req = db.get(DocumentUploadRequirement, requirement_id)
    if not req or req.status != "ACTIVE": raise HTTPException(404, "Requirement is not available.")
    if not _visible(req, actor): raise HTTPException(403, "You are not authorized for this requirement.")
    late = _now() > req.due_at
    if late and not req.late_upload_allowed: raise HTTPException(409, "The deadline has passed; late uploads are closed.")
    data = await file.read(); suffix = _validate(req, file, data)
    row = db.scalar(select(DocumentSubmission).where(DocumentSubmission.requirement_id == req.id, DocumentSubmission.student_id == actor.id))
    if row is None: row = DocumentSubmission(requirement_id=req.id, student_id=actor.id, status="UPLOADED", is_late=late); db.add(row); db.flush()
    else: row.status = "UPLOADED"; row.is_late = row.is_late or late
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
def submission(requirement_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = db.get(DocumentUploadRequirement, requirement_id); row = _submission(req, actor, db) if req else None
    if row is None: raise HTTPException(404, "Submission not found.")
    return _submission_out(row, db)

@router.get("/{requirement_id}/submission/versions", response_model=list[VersionOut])
def versions(requirement_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = db.get(DocumentUploadRequirement, requirement_id); row = _submission(req, actor, db) if req else None
    if row is None: raise HTTPException(404, "Submission not found.")
    return [VersionOut.model_validate(v) for v in db.scalars(select(DocumentSubmissionVersion).where(DocumentSubmissionVersion.submission_id == row.id).order_by(DocumentSubmissionVersion.version_number)).all()]

@router.get("/submissions/{submission_id}/versions/{version_id}/download")
def download(submission_id: int, version_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(DocumentSubmission, submission_id); version = db.get(DocumentSubmissionVersion, version_id)
    if not row or not version or version.submission_id != row.id: raise HTTPException(404, "Document version not found.")
    req = db.get(DocumentUploadRequirement, row.requirement_id)
    if actor.role not in ADMIN and not (actor.role == UserRole.STUDENT and row.student_id == actor.id) and not (actor.role == UserRole.SUPERVISOR and req and _visible(req, actor)): raise HTTPException(403, "You are not authorized to download this document.")
    path = _stored_path(version.storage_reference)
    if not path.is_file(): raise HTTPException(410, "The stored document is no longer available.")
    return FileResponse(path, media_type=version.mime_type, filename=version.original_filename)

def _review(requirement_id, submission_id, decision, comment, actor, db):
    req = db.get(DocumentUploadRequirement, requirement_id); row = db.get(DocumentSubmission, submission_id)
    if not req or not row or row.requirement_id != req.id: raise HTTPException(404, "Submission not found.")
    if actor.role not in ADMIN and not (actor.role == UserRole.SUPERVISOR and _visible(req, actor)): raise HTTPException(403, "You are not authorized to review this document.")
    row.status = decision; row.review_comment = comment; row.reviewed_by_id = actor.id; row.reviewed_at = _now(); _audit(db, actor, "document_submission_" + decision.lower(), row.id, {"status": decision}, row.student_id); db.commit(); db.refresh(row); return _submission_out(row, db)

@router.post("/{requirement_id}/submissions/{submission_id}/approve", response_model=SubmissionOut)
def approve(requirement_id:int, submission_id:int, _: object=Depends(validate_mutating_origin), actor:User=Depends(get_current_user), db:Session=Depends(get_db)): return _review(requirement_id, submission_id, "APPROVED", None, actor, db)
@router.post("/{requirement_id}/submissions/{submission_id}/reject", response_model=SubmissionOut)
def reject(requirement_id:int, submission_id:int, comment:str|None=None, _: object=Depends(validate_mutating_origin), actor:User=Depends(get_current_user), db:Session=Depends(get_db)): return _review(requirement_id, submission_id, "REJECTED", comment, actor, db)
@router.post("/{requirement_id}/submissions/{submission_id}/request-replacement", response_model=SubmissionOut)
def replacement(requirement_id:int, submission_id:int, comment:str|None=None, _: object=Depends(validate_mutating_origin), actor:User=Depends(get_current_user), db:Session=Depends(get_db)): return _review(requirement_id, submission_id, "REPLACEMENT_REQUESTED", comment, actor, db)
