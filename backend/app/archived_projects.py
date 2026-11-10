"""Authorized logical FYP archive management and deterministic knowledge search."""

import hashlib
from io import BytesIO
import os
import re
from datetime import datetime
from pathlib import PurePath

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles, validate_mutating_origin
from .database import get_db
from .models import AcademicCycle, AdminAuditEvent, ArchivedProject, ArchivedProjectDocument, ArchivedProjectDocumentType, User, UserRole

router = APIRouter(prefix="/api/v1/archived-projects")
admin_archive_router = APIRouter(prefix="/api/v1/admin/archive", tags=["archive-import"])
READ_ROLES = (UserRole.STUDENT, UserRole.SUPERVISOR, UserRole.COORDINATOR, UserRole.ADMIN)
ARCHIVE_MAX_BYTES = int(os.getenv("FYPHUB_ARCHIVE_MAX_BYTES", str(10 * 1024 * 1024)))
DOCUMENT_TYPES = {item.value for item in ArchivedProjectDocumentType}
ARCHIVE_METADATA_FIELDS = ("title", "abstract_summary", "keywords", "academic_year", "department_program", "project_scope", "completion_stage", "implemented_scope", "remaining_gaps", "future_work", "supervisor_display_reference", "source_label", "source_metadata")

ARCHIVE_COLUMNS = [
    ("Project Title", "title", True), ("Project Code", "project_code", True),
    ("Group Leader Name", "group_leader_name", True), ("Group Leader Registration Number", "group_leader_registration_number", True),
    ("Group Members", "group_members", False), ("Supervisor Name", "supervisor_name", True),
    ("Department / Program", "department_program", True), ("Academic Year", "academic_year", True),
    ("Session", "session_name", True), ("Abstract / Summary", "abstract_summary", True),
    ("Problem Statement", "problem_statement", True), ("Objectives", "objectives", True),
    ("Methodology", "methodology", True), ("Technologies Used", "technologies_used", True),
    ("Main Features", "main_features", True), ("Project Status", "project_status", True),
    ("Completion Percentage", "completion_percentage", True), ("Outcomes / Results", "outcomes_results", True),
    ("Repository URL", "repository_url", False), ("Report URL", "report_url", False),
    ("Presentation URL", "presentation_url", False), ("External Reference", "external_reference", False),
    ("Notes", "notes", False),
]
_HEADER_ALIASES = {re.sub(r"[^a-z0-9]", "", label.casefold()): key for label, key, _ in ARCHIVE_COLUMNS}


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    text_value = str(value).strip()
    # Formula cells are never evaluated or executed.  They are rejected so an
    # imported workbook cannot smuggle executable spreadsheet content through.
    if text_value.startswith("="):
        raise ValueError("Formula cells are not allowed")
    return text_value


def parse_archive_workbook(content: bytes, cycle: AcademicCycle) -> dict:
    if len(content) > ARCHIVE_MAX_BYTES:
        raise _error("archive_file_too_large", "The XLSX file exceeds the configured size limit.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=False)
    except Exception as error:
        raise _error("invalid_archive_workbook", "Upload a readable .xlsx workbook.", status.HTTP_422_UNPROCESSABLE_CONTENT) from error
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise _error("empty_archive_workbook", "The workbook contains no rows.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    headers: dict[str, int] = {}
    for index, value in enumerate(rows[0]):
        normalized = re.sub(r"[^a-z0-9]", "", str(value or "").casefold())
        if normalized in _HEADER_ALIASES:
            headers[_HEADER_ALIASES[normalized]] = index
    missing = [key for _, key, required in ARCHIVE_COLUMNS if required and key not in headers]
    if missing:
        labels = [label for label, key, required in ARCHIVE_COLUMNS if required and key in missing]
        raise _error("missing_archive_columns", f"Missing required columns: {', '.join(labels)}.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    valid: list[dict] = []
    invalid: list[dict] = []
    seen_codes: set[str] = set()
    seen_titles: set[str] = set()
    cycle_year = str(cycle.academic_year or "").strip()
    cycle_session = str(cycle.session or "").strip().upper()
    for row_number, values in enumerate(rows[1:], 2):
        if not any(value not in (None, "") for value in values):
            continue
        row: dict[str, str] = {}
        errors: list[str] = []
        try:
            for _, key, _ in ARCHIVE_COLUMNS:
                row[key] = _cell_text(values[headers[key]]) if key in headers and headers[key] < len(values) else ""
        except ValueError as error:
            invalid.append({"row": row_number, "errors": [str(error)]}); continue
        for label, key, required in ARCHIVE_COLUMNS:
            if required and not row.get(key, ""):
                errors.append(f"{label} is required")
        if row.get("completion_percentage"):
            try:
                percentage = int(float(row["completion_percentage"]))
                if not 0 <= percentage <= 100: raise ValueError
                row["completion_percentage"] = str(percentage)
            except ValueError:
                errors.append("Completion Percentage must be between 0 and 100")
        if row.get("academic_year") and row["academic_year"] != cycle_year:
            errors.append("Academic Year does not match the selected academic cycle")
        if row.get("session_name"):
            row["session_name"] = row["session_name"].upper()
        if row.get("session_name") and row["session_name"] != cycle_session:
            errors.append("Session does not match the selected academic cycle")
        code_key = row.get("project_code", "").casefold().strip()
        title_key = normalize_title(row.get("title", ""))
        if code_key in seen_codes and code_key: errors.append("Duplicate project code in upload")
        if title_key in seen_titles and title_key: errors.append("Duplicate project title in upload")
        seen_codes.add(code_key); seen_titles.add(title_key)
        if errors: invalid.append({"row": row_number, "data": row, "errors": errors})
        else: valid.append({"row": row_number, "data": row})
    return {"valid_rows": valid, "invalid_rows": invalid, "total_rows": len(valid) + len(invalid), "cycle": {"id": cycle.id, "academic_year": cycle.academic_year, "session": cycle.session}}


def _archive_import_project(row: dict[str, str], cycle: AcademicCycle) -> ArchivedProject:
    members = [item.strip() for item in re.split(r"[,;\n]", row.get("group_members", "")) if item.strip()]
    return ArchivedProject(
        title=row["title"], normalized_title=normalize_title(row["title"]), abstract_summary=row["abstract_summary"], keywords=[],
        academic_cycle_id=cycle.id, academic_year=str(cycle.academic_year), department_program=row["department_program"],
        project_scope="Historical FYP Project", completion_stage=row["project_status"], implemented_scope=row["main_features"],
        remaining_gaps=row.get("notes") or "Not provided", future_work=row.get("outcomes_results") or "Not provided",
        supervisor_display_reference=row["supervisor_name"], source_label="XLSX_IMPORT", source_metadata={"imported": True},
        project_code=row["project_code"], group_leader_name=row["group_leader_name"], group_leader_registration_number=row["group_leader_registration_number"],
        group_members=members, supervisor_name=row["supervisor_name"], session_name=cycle.session,
        problem_statement=row["problem_statement"], objectives=row["objectives"], methodology=row["methodology"], technologies_used=row["technologies_used"],
        main_features=row["main_features"], project_status=row["project_status"], completion_percentage=int(row["completion_percentage"]), outcomes_results=row["outcomes_results"],
        repository_url=row.get("repository_url") or None, report_url=row.get("report_url") or None, presentation_url=row.get("presentation_url") or None,
        external_reference=row.get("external_reference") or None, notes=row.get("notes") or None, is_visible_to_students=True,
    )


def normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.casefold())).strip()


def clean_filename(value: str) -> str:
    name = PurePath(value.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name[:255] or "archive-document.pdf"


class ArchiveCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=255)
    abstract_summary: str = Field(min_length=1, max_length=10000)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    academic_cycle_id: int | None = Field(default=None, gt=0)
    academic_year: str = Field(min_length=1, max_length=64)
    department_program: str = Field(min_length=1, max_length=255)
    project_scope: str = Field(min_length=1, max_length=255)
    completion_stage: str = Field(min_length=1, max_length=100)
    implemented_scope: str = Field(min_length=1, max_length=10000)
    remaining_gaps: str = Field(min_length=1, max_length=10000)
    future_work: str = Field(min_length=1, max_length=10000)
    supervisor_display_reference: str | None = Field(default=None, max_length=255)
    source_label: str = Field(min_length=1, max_length=64)
    source_metadata: dict = Field(default_factory=dict)

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, values: list[str]) -> list[str]:
        cleaned = [item.strip() for item in values if item.strip()]
        if any(len(item) > 100 for item in cleaned):
            raise ValueError("Each keyword must be 100 characters or fewer.")
        return list(dict.fromkeys(cleaned))


class ArchiveUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=255)
    abstract_summary: str | None = Field(default=None, min_length=1, max_length=10000)
    keywords: list[str] | None = Field(default=None, max_length=30)
    academic_year: str | None = Field(default=None, min_length=1, max_length=64)
    department_program: str | None = Field(default=None, min_length=1, max_length=255)
    project_scope: str | None = Field(default=None, min_length=1, max_length=255)
    completion_stage: str | None = Field(default=None, min_length=1, max_length=100)
    implemented_scope: str | None = Field(default=None, min_length=1, max_length=10000)
    remaining_gaps: str | None = Field(default=None, min_length=1, max_length=10000)
    future_work: str | None = Field(default=None, min_length=1, max_length=10000)
    supervisor_display_reference: str | None = Field(default=None, max_length=255)
    source_label: str | None = Field(default=None, min_length=1, max_length=64)
    source_metadata: dict | None = None

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return list(dict.fromkeys(item.strip() for item in values if item.strip()))


def _error(code: str, message: str, code_status: int = status.HTTP_409_CONFLICT) -> HTTPException:
    return HTTPException(code_status, detail={"code": code, "message": message})


def _audit(session: Session, actor: User, project: ArchivedProject, action: str, changed: dict | None = None) -> None:
    from .main import add_admin_audit_event

    add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type="ARCHIVED_PROJECT", target_id=project.id, action=action, changed_values=changed or {})


def _document_out(document: ArchivedProjectDocument) -> dict:
    return {"id": document.id, "document_type": document.document_type, "display_name": document.display_name, "file_hash": document.file_hash, "mime_type": document.mime_type, "file_size": document.file_size, "version": document.version, "created_at": document.created_at, "is_active": document.is_active, "document_url": f"/api/v1/archived-projects/{document.archived_project_id}/documents/{document.id}"}


def _project_out(session: Session, project: ArchivedProject, *, include_history: bool = False, actor: User | None = None) -> dict:
    statement = select(ArchivedProjectDocument).where(ArchivedProjectDocument.archived_project_id == project.id)
    if not include_history:
        statement = statement.where(ArchivedProjectDocument.is_active.is_(True))
    documents = session.scalars(statement.order_by(ArchivedProjectDocument.document_type, ArchivedProjectDocument.version.desc())).all()
    public = actor is not None and actor.role == UserRole.STUDENT
    return {"id": project.id, "title": project.title, "normalized_title": project.normalized_title, "abstract_summary": project.abstract_summary, "keywords": project.keywords or [], "academic_cycle_id": project.academic_cycle_id, "academic_year": project.academic_year, "session": project.session_name, "department_program": project.department_program, "project_scope": project.project_scope, "completion_stage": project.completion_stage, "implemented_scope": project.implemented_scope, "remaining_gaps": project.remaining_gaps, "future_work": project.future_work, "supervisor_display_reference": project.supervisor_display_reference, "source_label": project.source_label, "project_code": project.project_code, "group_leader_name": project.group_leader_name, "group_leader_registration_number": None if public else project.group_leader_registration_number, "group_members": [] if public else (project.group_members or []), "supervisor_name": project.supervisor_name, "problem_statement": project.problem_statement, "objectives": project.objectives, "methodology": project.methodology, "technologies_used": project.technologies_used, "main_features": project.main_features, "project_status": project.project_status, "completion_percentage": project.completion_percentage, "outcomes_results": project.outcomes_results, "repository_url": project.repository_url, "report_url": project.report_url, "presentation_url": project.presentation_url, "external_reference": project.external_reference, "notes": project.notes, "is_visible_to_students": project.is_visible_to_students, "created_at": project.created_at, "updated_at": project.updated_at, "archived_at": project.archived_at, "is_active": project.is_active, "documents": [_document_out(item) for item in documents]}


def _active_project(session: Session, project_id: int, actor: User | None = None) -> ArchivedProject:
    project = session.scalar(select(ArchivedProject).where(ArchivedProject.id == project_id, ArchivedProject.is_active.is_(True)))
    if project is None or (actor is not None and actor.role == UserRole.STUDENT and not project.is_visible_to_students):
        raise _error("archive_not_found", "Archived project was not found.", status.HTTP_404_NOT_FOUND)
    return project


def _metadata_snapshot(project: ArchivedProject) -> dict:
    return {field: list(getattr(project, field)) if field == "keywords" else getattr(project, field) for field in ARCHIVE_METADATA_FIELDS}


def _validate_document(file: UploadFile, content: bytes) -> str:
    if file.content_type != "application/pdf" or not (file.filename or "").lower().endswith(".pdf"):
        raise _error("invalid_document_type", "Archive documents must be PDF files.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if not content or len(content) > ARCHIVE_MAX_BYTES:
        raise _error("document_size_invalid", "The archive PDF is empty or exceeds the configured size limit.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if not content.startswith(b"%PDF"):
        raise _error("invalid_pdf", "The uploaded archive file is not a readable PDF.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return clean_filename(file.filename or "archive-document.pdf")


def _next_version(session: Session, project_id: int, document_type: str) -> int:
    current = session.scalar(select(func.max(ArchivedProjectDocument.version)).where(ArchivedProjectDocument.archived_project_id == project_id, ArchivedProjectDocument.document_type == document_type))
    return int(current or 0) + 1


@router.get("/search")
def search_archives(q: str | None = Query(default=None, max_length=255), academic_year: str | None = Query(default=None, max_length=64), session_name: str | None = Query(default=None, max_length=16), department: str | None = Query(default=None, max_length=255), supervisor: str | None = Query(default=None, max_length=255), technology: str | None = Query(default=None, max_length=255), project_scope: str | None = Query(default=None, max_length=255), completion_stage: str | None = Query(default=None, max_length=100), _: User = Depends(require_roles(*READ_ROLES)), session: Session = Depends(get_db)):
    statement = select(ArchivedProject).where(ArchivedProject.is_active.is_(True), ArchivedProject.is_visible_to_students.is_(True))
    if academic_year:
        statement = statement.where(ArchivedProject.academic_year == academic_year.strip())
    if session_name:
        statement = statement.where(ArchivedProject.session_name == session_name.strip().upper())
    if department:
        statement = statement.where(ArchivedProject.department_program.ilike(f"%{department.strip()}%"))
    if supervisor:
        statement = statement.where(ArchivedProject.supervisor_name.ilike(f"%{supervisor.strip()}%"))
    if technology:
        statement = statement.where(ArchivedProject.technologies_used.ilike(f"%{technology.strip()}%"))
    if project_scope:
        statement = statement.where(ArchivedProject.project_scope.ilike(f"%{project_scope.strip()}%"))
    if completion_stage:
        statement = statement.where(ArchivedProject.completion_stage.ilike(f"%{completion_stage.strip()}%"))
    projects = session.scalars(statement).all()
    normalized = normalize_title(q or "")
    query_tokens = set(normalized.split())
    ranked: list[tuple[int, ArchivedProject, str]] = []
    for project in projects:
        title = project.normalized_title
        keywords = {normalize_title(item) for item in (project.keywords or [])}
        summary = normalize_title(project.abstract_summary)
        scope = normalize_title(project.project_scope)
        technology = normalize_title(project.technologies_used or "")
        gaps = normalize_title(project.remaining_gaps)
        if not normalized:
            score, reason = 0, "all active projects"
        elif title == normalized:
            score, reason = 100, "exact title match"
        elif title.startswith(normalized) or normalized in title:
            score, reason = 80, "normalized title match"
        elif query_tokens.intersection(keywords):
            score, reason = 60, "keyword match"
        elif query_tokens.intersection(set(summary.split())):
            score, reason = 40, "summary match"
        elif query_tokens.intersection(set(scope.split())):
            score, reason = 30, "scope match"
        elif query_tokens.intersection(set(technology.split())):
            score, reason = 30, "technology match"
        elif query_tokens.intersection(set(gaps.split())):
            score, reason = 20, "remaining gaps match"
        else:
            continue
        ranked.append((score, project, reason))
    ranked.sort(key=lambda item: (-item[0], item[1].normalized_title, item[1].id))
    results = []
    for rank, (score, project, reason) in enumerate(ranked, 1):
        active_count = session.scalar(select(func.count()).select_from(ArchivedProjectDocument).where(ArchivedProjectDocument.archived_project_id == project.id, ArchivedProjectDocument.is_active.is_(True))) or 0
        results.append({"rank": rank, "id": project.id, "title": project.title, "short_summary": project.abstract_summary[:500], "academic_year": project.academic_year, "session": project.session_name, "department_program": project.department_program, "project_scope": project.project_scope, "completion_stage": project.completion_stage, "project_status": project.project_status, "completion_percentage": project.completion_percentage, "technologies_used": project.technologies_used, "implemented_scope": project.implemented_scope[:500], "remaining_gaps": project.remaining_gaps[:500], "available_documents_count": active_count, "match_score": score, "match_reason": reason})
    return {"semantic_search": "unavailable", "advisory": True, "results": results}


@router.get("/admin/list")
def admin_archive_list(_: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    return [_project_out(session, project, include_history=True) for project in session.scalars(select(ArchivedProject).order_by(ArchivedProject.updated_at.desc(), ArchivedProject.id.desc())).all()]


@router.get("/admin/detail/{project_id}")
def admin_archive_detail(project_id: int, _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    project = session.get(ArchivedProject, project_id)
    if project is None:
        raise _error("archive_not_found", "Archived project was not found.", status.HTTP_404_NOT_FOUND)
    return _project_out(session, project, include_history=True)


@router.get("/{project_id}")
def read_archive(project_id: int, actor: User = Depends(require_roles(*READ_ROLES)), session: Session = Depends(get_db)):
    return _project_out(session, _active_project(session, project_id, actor), actor=actor)


@router.get("/{project_id}/documents/{document_id}")
def read_archive_document(project_id: int, document_id: int, actor: User = Depends(require_roles(*READ_ROLES)), session: Session = Depends(get_db)):
    project = _active_project(session, project_id, actor)
    document = session.scalar(select(ArchivedProjectDocument).where(ArchivedProjectDocument.id == document_id, ArchivedProjectDocument.archived_project_id == project.id, ArchivedProjectDocument.is_active.is_(True)))
    if document is None:
        raise _error("document_not_found", "Archive document was not found.", status.HTTP_404_NOT_FOUND)
    filename = clean_filename(document.display_name)
    from fastapi.responses import StreamingResponse
    from io import BytesIO

    return StreamingResponse(BytesIO(document.content), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})


@router.post("/admin", status_code=status.HTTP_201_CREATED)
def create_archive(payload: ArchiveCreate, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    project = ArchivedProject(normalized_title=normalize_title(payload.title), **payload.model_dump())
    if not project.normalized_title:
        raise _error("invalid_title", "Title must contain letters or numbers.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if session.scalar(select(ArchivedProject).where(ArchivedProject.normalized_title == project.normalized_title, ArchivedProject.academic_year == project.academic_year, ArchivedProject.is_active.is_(True))):
        raise _error("duplicate_active_title", "An active archive with this title already exists in the academic year.")
    try:
        session.add(project); session.flush(); _audit(session, actor, project, "archived_project_created", {"source_label": project.source_label}); session.commit(); session.refresh(project); return _project_out(session, project)
    except IntegrityError as error:
        session.rollback(); raise _error("duplicate_active_title", "An active archive with this title already exists in the academic year.") from error
    except Exception as error:
        session.rollback(); raise _error("archive_create_failed", "The archived project could not be created.", status.HTTP_500_INTERNAL_SERVER_ERROR) from error


@router.patch("/admin/{project_id}")
def update_archive(project_id: int, payload: ArchiveUpdate, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    project = session.scalar(select(ArchivedProject).where(ArchivedProject.id == project_id))
    if project is None:
        raise _error("archive_not_found", "Archived project was not found.", status.HTTP_404_NOT_FOUND)
    changes = payload.model_dump(exclude_unset=True)
    if "title" in changes:
        changes["normalized_title"] = normalize_title(changes["title"])
    if "title" in changes or "academic_year" in changes:
        title = changes.get("normalized_title", project.normalized_title); year = changes.get("academic_year", project.academic_year)
        duplicate = session.scalar(select(ArchivedProject).where(ArchivedProject.id != project.id, ArchivedProject.normalized_title == title, ArchivedProject.academic_year == year, ArchivedProject.is_active.is_(True)))
        if duplicate:
            raise _error("duplicate_active_title", "An active archive with this title already exists in the academic year.")
    try:
        before = _metadata_snapshot(project)
        for key, value in changes.items(): setattr(project, key, value)
        after = _metadata_snapshot(project)
        _audit(session, actor, project, "archived_project_updated", {"before": before, "after": after}); session.commit(); session.refresh(project); return _project_out(session, project, include_history=True)
    except IntegrityError as error:
        session.rollback(); raise _error("duplicate_active_title", "An active archive with this title already exists in the academic year.") from error


@router.post("/admin/{project_id}/rollback/{event_id}")
def rollback_archive_metadata(project_id: int, event_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    project = session.get(ArchivedProject, project_id)
    event = session.get(AdminAuditEvent, event_id)
    if project is None or event is None or event.target_type != "ARCHIVED_PROJECT" or event.target_id != project_id or event.action != "archived_project_updated":
        raise _error("rollback_not_available", "The requested archive metadata snapshot was not found.", status.HTTP_404_NOT_FOUND)
    before = (event.changed_values or {}).get("before") if isinstance(event.changed_values, dict) else None
    if not isinstance(before, dict) or any(field not in before for field in ARCHIVE_METADATA_FIELDS):
        raise _error("rollback_not_available", "The audit event does not contain a complete metadata snapshot.", status.HTTP_409_CONFLICT)
    normalized_title = normalize_title(str(before["title"]))
    duplicate = session.scalar(select(ArchivedProject).where(ArchivedProject.id != project.id, ArchivedProject.normalized_title == normalized_title, ArchivedProject.academic_year == before["academic_year"], ArchivedProject.is_active.is_(True)))
    if duplicate:
        raise _error("duplicate_active_title", "The historical title conflicts with another active archive.")
    snapshot = _metadata_snapshot(project)
    for field in ARCHIVE_METADATA_FIELDS: setattr(project, field, before[field])
    project.normalized_title = normalized_title
    _audit(session, actor, project, "archived_project_metadata_rolled_back", {"source_event_id": event_id, "before": snapshot, "after": _metadata_snapshot(project)})
    session.commit(); session.refresh(project)
    return _project_out(session, project, include_history=True)


@router.post("/admin/{project_id}/active")
def set_archive_active(project_id: int, request: Request, active: bool = Form(...), actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    project = session.get(ArchivedProject, project_id)
    if project is None:
        raise _error("archive_not_found", "Archived project was not found.", status.HTTP_404_NOT_FOUND)
    project.is_active = active
    project.archived_at = None if active else datetime.now(project.updated_at.tzinfo) if project.updated_at and project.updated_at.tzinfo else datetime.utcnow()
    _audit(session, actor, project, "archived_project_activated" if active else "archived_project_deactivated", {"is_active": active})
    session.commit(); return _project_out(session, project, include_history=True)


@router.post("/admin/{project_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_archive_document(project_id: int, request: Request, document_type: str = Form(...), display_name: str | None = Form(default=None), document: UploadFile = File(...), actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    project = session.get(ArchivedProject, project_id)
    if project is None:
        raise _error("archive_not_found", "Archived project was not found.", status.HTTP_404_NOT_FOUND)
    document_type = document_type.strip().upper()
    if document_type not in DOCUMENT_TYPES:
        raise _error("invalid_document_type", "Unsupported archive document type.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    content = await document.read()
    filename = _validate_document(document, content)
    try:
        previous = session.scalars(select(ArchivedProjectDocument).where(ArchivedProjectDocument.archived_project_id == project.id, ArchivedProjectDocument.document_type == document_type, ArchivedProjectDocument.is_active.is_(True)).with_for_update()).all()
        for item in previous: item.is_active = False
        version = _next_version(session, project.id, document_type)
        row = ArchivedProjectDocument(archived_project_id=project.id, document_type=document_type, display_name=clean_filename(display_name or filename), storage_key=f"archive/{project.id}/{document_type.lower()}/v{version}-{filename}", file_hash=hashlib.sha256(content).hexdigest(), mime_type="application/pdf", file_size=len(content), content=content, version=version, uploaded_by_id=actor.id, is_active=True)
        session.add(row); session.flush(); _audit(session, actor, project, "archived_project_document_uploaded", {"document_type": document_type, "version": version, "file_hash": row.file_hash}); session.commit(); session.refresh(row); return _document_out(row)
    except Exception as error:
        session.rollback(); raise _error("archive_document_upload_failed", "The archive document could not be saved.", status.HTTP_500_INTERNAL_SERVER_ERROR) from error


@router.get("/admin/{project_id}/documents/history")
def archive_document_history(project_id: int, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    project = session.get(ArchivedProject, project_id)
    if project is None:
        raise _error("archive_not_found", "Archived project was not found.", status.HTTP_404_NOT_FOUND)
    return [_document_out(item) for item in session.scalars(select(ArchivedProjectDocument).where(ArchivedProjectDocument.archived_project_id == project.id).order_by(ArchivedProjectDocument.document_type, ArchivedProjectDocument.version.desc())).all()]


@admin_archive_router.get("/import-template")
def archive_import_template(_: User = Depends(require_roles(UserRole.ADMIN))):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Old FYP Projects"
    sheet.append([label for label, _, _ in ARCHIVE_COLUMNS])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="old-fyp-projects-template.xlsx"'})


async def _read_archive_upload(file: UploadFile) -> bytes:
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise _error("invalid_archive_file_type", "Upload an .xlsx workbook.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return await file.read()


@admin_archive_router.post("/import/preview")
async def archive_import_preview(academic_cycle_id: int = Form(...), file: UploadFile = File(...), _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    cycle = session.get(AcademicCycle, academic_cycle_id)
    if cycle is None or cycle.academic_year is None or not cycle.session:
        raise _error("invalid_academic_cycle", "Select an existing academic cycle with a year and session.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return parse_archive_workbook(await _read_archive_upload(file), cycle)


@admin_archive_router.post("/import/confirm")
async def archive_import_confirm(request: Request, academic_cycle_id: int = Form(...), file: UploadFile = File(...), actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    cycle = session.get(AcademicCycle, academic_cycle_id)
    if cycle is None or cycle.academic_year is None or not cycle.session:
        raise _error("invalid_academic_cycle", "Select an existing academic cycle with a year and session.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    preview = parse_archive_workbook(await _read_archive_upload(file), cycle)
    if preview["invalid_rows"]:
        raise _error("archive_import_has_invalid_rows", "Fix invalid rows before confirming the import.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    created: list[ArchivedProject] = []
    try:
        for item in preview["valid_rows"]:
            row = item["data"]
            duplicate = session.scalar(select(ArchivedProject).where(ArchivedProject.academic_cycle_id == cycle.id, ArchivedProject.is_active.is_(True), ((ArchivedProject.project_code == row["project_code"]) | (ArchivedProject.normalized_title == normalize_title(row["title"])))) )
            if duplicate:
                raise _error("duplicate_archive_project", f"Project code or title already exists in the selected cycle (row {item['row']}).")
            project = _archive_import_project(row, cycle)
            session.add(project); session.flush(); _audit(session, actor, project, "archived_project_imported", {"academic_cycle_id": cycle.id, "source": "xlsx"}); created.append(project)
        session.commit()
    except HTTPException:
        session.rollback(); raise
    except Exception as error:
        session.rollback(); raise _error("archive_import_failed", "The archive import could not be completed.", status.HTTP_500_INTERNAL_SERVER_ERROR) from error
    return {"imported_count": len(created), "projects": [_project_out(session, project) for project in created]}


@router.post("/admin/{project_id}/visibility")
def set_archive_visibility(project_id: int, request: Request, visible: bool = Form(...), actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    project = session.get(ArchivedProject, project_id)
    if project is None:
        raise _error("archive_not_found", "Archived project was not found.", status.HTTP_404_NOT_FOUND)
    project.is_visible_to_students = visible
    _audit(session, actor, project, "archived_project_visibility_changed", {"is_visible_to_students": visible})
    session.commit(); session.refresh(project)
    return _project_out(session, project, include_history=True)
