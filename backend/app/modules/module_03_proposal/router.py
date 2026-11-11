"""Module 3 APIs: template ingestion, proposal submissions, and reports."""

from __future__ import annotations

import re
import json
import hashlib
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import delete, desc, or_, select, update
from sqlalchemy.orm import Session

from ...auth import get_current_user, require_roles, utc_now, validate_mutating_origin
from ...config import settings
from ...database import get_db
from ...models import AcademicRuleVersion, ProposalComplianceReport, ProposalComplianceSubmission, SupervisorAssignment, Team, TeamMember, TemplateReference, TemplateReferenceVersion, TemplateType, User, UserRole
from ...pdf_extraction import PdfExtractionError, extract_proposal_document
from .compliance_engine import build_change_summary, build_compliance_report
from .template_extractor import extract_template_rules
from ...team_lifecycle import lock_team
from ...ai_provider import run_ai_json
from .ai_report import REPORT_VERSION, assemble_report, generate_full_report

router = APIRouter(prefix="/api/v1/proposal-compliance", tags=["module-3-proposal-compliance"])
REVIEW_ROLES = (UserRole.ADMIN, UserRole.COORDINATOR, UserRole.SUPERVISOR, UserRole.PANEL_MEMBER)
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
PROPOSAL_REVIEW_STATUSES = {"CHANGES_REQUESTED", "APPROVED", "REJECTED"}


class ProposalStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=1, max_length=32)
    comment: str | None = Field(default=None, max_length=2000)


def _error(code: str, message: str, http_status: int = 400) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "message": message})


def _student_team(session: Session, actor: User) -> Team | None:
    """Resolve the existing shared project group for its login or an active member."""
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


def _same_group(row: ProposalComplianceSubmission, team: Team | None) -> bool:
    return team is not None and row.team_id == team.id


def _owner_scope(row: ProposalComplianceSubmission, actor: User, team: Team | None) -> bool:
    return row.owner_user_id == actor.id or _same_group(row, team)


def _safe_filename(filename: str | None) -> str:
    value = Path(filename or "proposal").name
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)[:180] or "proposal"


def _storage_path(kind: str, identifier: str, filename: str) -> Path:
    root = settings.document_storage_root / "module-3" / kind / identifier
    root.mkdir(parents=True, exist_ok=True)
    return root / _safe_filename(filename)


def _template_rules(session: Session, version_id: int) -> dict[str, Any]:
    rule = session.scalar(select(AcademicRuleVersion).where(AcademicRuleVersion.template_reference_version_id == version_id).order_by(desc(AcademicRuleVersion.version_number)).limit(1))
    return dict(rule.rules) if rule else {}


def _template_out(session: Session, version: TemplateReferenceVersion) -> dict[str, Any]:
    return {"id": version.id, "reference_id": version.template_reference_id, "template_type": version.template_type.value if hasattr(version.template_type, "value") else str(version.template_type), "version": version.version_number, "title": version.title, "provenance": version.provenance, "source_note": version.source_note, "is_active": version.is_active, "activated_at": version.activated_at, "rules": _template_rules(session, version.id)}


def _active_template(session: Session, proposal_type: str) -> tuple[TemplateReferenceVersion, dict[str, Any]] | None:
    reference = session.scalar(select(TemplateReference).where(TemplateReference.template_type == TemplateType(proposal_type)).limit(1))
    if reference is None:
        return None
    version = session.scalar(select(TemplateReferenceVersion).where(TemplateReferenceVersion.template_reference_id == reference.id, TemplateReferenceVersion.is_active.is_(True)).order_by(desc(TemplateReferenceVersion.version_number), desc(TemplateReferenceVersion.id)).limit(1))
    return (version, _template_rules(session, version.id)) if version else None


def _allowed_upload(filename: str | None, content_type: str | None) -> bool:
    suffix = (filename or "").lower().rsplit(".", 1)[-1]
    return suffix in {"pdf", "docx", "txt"} or (content_type or "").lower() in {"application/pdf", "text/plain", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def _allowed_template_upload(filename: str | None, content_type: str | None) -> bool:
    suffix = (filename or "").lower().rsplit(".", 1)[-1]
    return suffix in {"pdf", "docx"} or (content_type or "").lower() in {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }


def _detected_headings(text: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    page = 1
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        page_match = re.match(r"\[PAGE\s+(\d+)\]", line, re.IGNORECASE)
        if page_match:
            page = int(page_match.group(1))
            continue
        if not line or len(line) > 140 or line.endswith((".", ",", ";")):
            continue
        numbered = re.match(r"^(?:chapter\s+\d+|\d+(?:\.\d+)*[.)]?)\s+.+$", line, re.IGNORECASE)
        uppercase = re.match(r"^[A-Z][A-Z\s&:/()\-]{4,}$", line)
        if not (numbered or uppercase):
            continue
        key = re.sub(r"\s+", " ", line.casefold())
        if key in seen:
            continue
        seen.add(key)
        result.append({"name": line, "page": page})
    return result[:100]


def _submission_out(session: Session, row: ProposalComplianceSubmission) -> dict[str, Any]:
    report = session.scalar(select(ProposalComplianceReport).where(ProposalComplianceReport.submission_id == row.id).limit(1))
    summary = report.report.get("reportSummary", {}) if report else {}
    return {"id": row.id, "proposal_key": row.proposal_key, "title": row.title, "proposal_type": row.proposal_type, "version": row.version, "status": row.status, "processing_status": row.processing_status, "filename": row.filename, "page_count": row.page_count, "created_at": row.created_at, "score": summary.get("score"), "report_status": summary.get("status"), "report_available": report is not None}


def _version_history(session: Session, row: ProposalComplianceSubmission) -> list[dict[str, Any]]:
    owner_scope = or_(ProposalComplianceSubmission.team_id == row.team_id, ProposalComplianceSubmission.owner_user_id == row.owner_user_id) if row.team_id is not None else ProposalComplianceSubmission.owner_user_id == row.owner_user_id
    previous = session.scalars(
        select(ProposalComplianceSubmission)
        .where(
            ProposalComplianceSubmission.proposal_key == row.proposal_key,
            owner_scope,
            ProposalComplianceSubmission.version < row.version,
        )
        .order_by(ProposalComplianceSubmission.version)
    ).all()
    history: list[dict[str, Any]] = []
    for item in previous:
        score = session.scalar(select(ProposalComplianceReport.score).where(ProposalComplianceReport.submission_id == item.id).limit(1))
        history.append({
            "version": item.version,
            "filename": item.filename,
            "score": score,
            "changeSummary": build_change_summary(item.extracted_fields, row.extracted_fields, item.version, row.version),
        })
    return history


def _can_view(session: Session, actor: User, row: ProposalComplianceSubmission) -> bool:
    team = _student_team(session, actor) if actor.role == UserRole.STUDENT else None
    if _owner_scope(row, actor, team) or actor.role in (UserRole.ADMIN, UserRole.COORDINATOR, UserRole.PANEL_MEMBER):
        return True
    if actor.role != UserRole.SUPERVISOR:
        return False
    if row.team_id is None:
        return False
    assignment = session.scalar(
        select(SupervisorAssignment.id)
        .where(
            SupervisorAssignment.supervisor_id == actor.id,
            SupervisorAssignment.team_id == row.team_id,
            SupervisorAssignment.ended_at.is_(None),
        )
        .limit(1)
    )
    return assignment is not None


@router.post("/templates/upload", status_code=status.HTTP_201_CREATED)
async def upload_template(
    request: Request,
    template_type: str = Form(...),
    title: str = Form(..., min_length=1, max_length=160),
    source_note: str = Form("Uploaded official university template", max_length=500),
    template_file: UploadFile = File(...),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
):
    validate_mutating_origin(request)
    if template_type not in {"SHORT", "LONG"}:
        raise _error("invalid_template_type", "Template type must be SHORT or LONG.", 422)
    if not _allowed_template_upload(template_file.filename, template_file.content_type):
        raise _error("unsupported_template", "Only PDF and DOCX templates are supported.", 422)
    data = await template_file.read()
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise _error("invalid_template_size", "The template must be non-empty and 5 MiB or smaller.", 422)
    try:
        rules = extract_template_rules(data, template_file.content_type, template_file.filename)
    except PdfExtractionError as error:
        raise _error(error.code, error.message, 422) from error
    reference = session.scalar(select(TemplateReference).where(TemplateReference.template_type == TemplateType(template_type)).limit(1))
    if reference is None:
        reference = TemplateReference(template_type=TemplateType(template_type))
        session.add(reference)
        session.flush()
    number = (session.scalar(select(TemplateReferenceVersion.version_number).where(TemplateReferenceVersion.template_reference_id == reference.id).order_by(desc(TemplateReferenceVersion.version_number)).limit(1)) or 0) + 1
    key = str(uuid.uuid4())
    path = _storage_path("templates", key, template_file.filename or "template")
    path.write_bytes(data)
    rules["source"]["storage_key"] = str(path.relative_to(settings.document_storage_root))
    version = TemplateReferenceVersion(template_reference_id=reference.id, version_number=number, title=title.strip(), provenance="UPLOADED_DOCUMENT", source_note=source_note.strip(), created_by_id=actor.id, is_active=False)
    session.add(version)
    session.flush()
    session.add(AcademicRuleVersion(template_reference_version_id=version.id, version_number=1, provenance="UPLOADED_DOCUMENT", rules=rules, created_by_id=actor.id))
    session.commit()
    session.refresh(version)
    return _template_out(session, version)


@router.get("/templates")
def list_templates(actor: User = Depends(require_roles(*REVIEW_ROLES)), session: Session = Depends(get_db)):
    versions = session.scalars(select(TemplateReferenceVersion).order_by(TemplateReferenceVersion.template_reference_id, desc(TemplateReferenceVersion.version_number))).all()
    return [_template_out(session, version) for version in versions]


@router.post("/templates/{version_id}/activate")
def activate_template(version_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    version = session.get(TemplateReferenceVersion, version_id)
    if version is None:
        raise _error("template_not_found", "Template version was not found.", 404)
    rules = _template_rules(session, version.id)
    if not rules.get("required_sections") and not any(key in rules for key in ("page_size", "font_family", "font_size_pt", "margin_mm", "line_spacing")):
        raise _error("template_incomplete", "The template has no confirmed extractable rules and cannot be activated.", 409)
    session.execute(update(TemplateReferenceVersion).where(TemplateReferenceVersion.template_reference_id == version.template_reference_id).values(is_active=False, activated_at=None, activated_by_id=None))
    version.is_active = True
    version.activated_at = utc_now()
    version.activated_by_id = actor.id
    session.commit()
    session.refresh(version)
    return _template_out(session, version)


@router.post("/templates/{version_id}/deactivate")
def deactivate_template(version_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    """Stop using a baseline without deleting its immutable version history."""
    validate_mutating_origin(request)
    version = session.get(TemplateReferenceVersion, version_id)
    if version is None:
        raise _error("template_not_found", "Template version was not found.", 404)
    version.is_active = False
    version.activated_at = None
    version.activated_by_id = None
    session.commit()
    session.refresh(version)
    return _template_out(session, version)


@router.delete("/templates/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(version_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> Response:
    """Delete an unused uploaded template version and its extracted rule snapshot."""
    validate_mutating_origin(request)
    version = session.get(TemplateReferenceVersion, version_id)
    if version is None:
        raise _error("template_not_found", "Template version was not found.", 404)
    if version.is_active:
        raise _error("template_active", "Deactivate the template before deleting it.", 409)
    try:
        session.execute(delete(AcademicRuleVersion).where(AcademicRuleVersion.template_reference_version_id == version_id))
        session.delete(version)
        session.commit()
    except Exception as error:
        session.rollback()
        raise _error("template_in_use", "This template is referenced by historical submissions and cannot be deleted.", 409) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/templates/{version_id}/rules")
def save_template_rules(
    version_id: int,
    request: Request,
    rules: dict[str, Any] = Body(...),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
):
    """Save an admin-confirmed rule review as a new immutable rule snapshot."""
    validate_mutating_origin(request)
    version = session.get(TemplateReferenceVersion, version_id)
    if version is None:
        raise _error("template_not_found", "Template version was not found.", 404)
    allowed = {"page_size", "margin_mm", "right_margin_mm", "top_margin_mm", "bottom_margin_mm", "font_family", "font_size_pt", "line_spacing", "alignment", "heading_style", "page_numbering", "table_count", "figure_count", "caption_count", "reference_count", "appendix_count", "required_sections", "required_references", "required_appendices", "required_captions", "source"}
    cleaned: dict[str, Any] = {key: value for key, value in rules.items() if key in allowed}
    for key in ("margin_mm", "right_margin_mm", "top_margin_mm", "bottom_margin_mm", "font_size_pt", "line_spacing", "table_count", "figure_count", "caption_count", "reference_count", "appendix_count", "required_references", "required_appendices", "required_captions"):
        if key in cleaned and cleaned[key] not in (None, ""):
            try:
                number = float(cleaned[key])
                cleaned[key] = int(number) if number.is_integer() and key in {"table_count", "figure_count"} else number
            except (TypeError, ValueError) as error:
                raise _error("invalid_rule_value", f"{key} must be numeric.", 422) from error
    if "page_numbering" in cleaned and isinstance(cleaned["page_numbering"], str):
        cleaned["page_numbering"] = cleaned["page_numbering"].strip().casefold() in {"true", "yes", "1", "present", "required"}
    sections = cleaned.get("required_sections")
    if sections is not None:
        if not isinstance(sections, list):
            raise _error("invalid_required_sections", "Required sections must be sent as a list.", 422)
        cleaned["required_sections"] = [str(item).strip() for item in sections if str(item).strip()]
    latest = session.scalar(select(AcademicRuleVersion.version_number).where(AcademicRuleVersion.template_reference_version_id == version.id).order_by(desc(AcademicRuleVersion.version_number)).limit(1)) or 0
    session.add(AcademicRuleVersion(template_reference_version_id=version.id, version_number=latest + 1, provenance="ADMIN_CONFIRMED", rules=cleaned, created_by_id=actor.id))
    session.commit()
    session.refresh(version)
    return _template_out(session, version)


@router.post("/submissions", status_code=status.HTTP_201_CREATED)
async def submit_proposal(
    request: Request,
    proposal_type: str = Form(...),
    title: str = Form(..., min_length=1, max_length=200),
    proposal_key: str | None = Form(None),
    action: str = Form("submit"),
    proposal_file: UploadFile = File(...),
    actor: User = Depends(require_roles(UserRole.STUDENT)),
    session: Session = Depends(get_db),
):
    validate_mutating_origin(request)
    if proposal_type not in {"SHORT", "LONG"}:
        raise _error("invalid_proposal_type", "Proposal type must be SHORT or LONG.", 422)
    if not _allowed_upload(proposal_file.filename, proposal_file.content_type):
        raise _error("unsupported_proposal", "Only PDF, DOCX, and TXT proposals are supported.", 422)
    active = _active_template(session, proposal_type)
    if active is None:
        raise _error("active_template_missing", "No active university template exists for this proposal type.", 409)
    data = await proposal_file.read(MAX_UPLOAD_BYTES + 1)
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise _error("invalid_proposal_size", "The proposal must be non-empty and 5 MiB or smaller.", 422)
    try:
        extracted = extract_proposal_document(data, proposal_file.content_type, proposal_file.filename)
    except PdfExtractionError as error:
        raise _error(error.code, error.message, 422) from error
    title_value = title.strip()
    if not title_value:
        raise _error("invalid_proposal_title", "Proposal title is required.", 422)
    key = (proposal_key or str(uuid.uuid4())).strip()
    if len(key) > 64:
        raise _error("invalid_proposal_key", "Proposal key is too long.", 422)
    team = _student_team(session, actor)
    ownership_filter = or_(ProposalComplianceSubmission.team_id == team.id, ProposalComplianceSubmission.owner_user_id == actor.id) if team is not None else ProposalComplianceSubmission.owner_user_id == actor.id
    previous = session.scalar(select(ProposalComplianceSubmission).where(ProposalComplianceSubmission.proposal_key == key, ownership_filter).order_by(desc(ProposalComplianceSubmission.version)).limit(1))
    if proposal_key and previous is None:
        raise _error("proposal_not_found", "The proposal version history could not be found.", 404)
    version_number = (previous.version + 1) if previous else 1
    path = _storage_path("submissions", key, f"v{version_number}-{proposal_file.filename or 'proposal'}")
    path.write_bytes(data)
    fields = {**extracted.extracted_fields, "detected_headings": _detected_headings(extracted.extracted_text)}
    template_version, rules = active
    if action not in {"draft", "submit"}:
        raise _error("invalid_submission_action", "Action must be draft or submit.", 422)
    is_draft = action == "draft"
    row = ProposalComplianceSubmission(proposal_key=key, owner_user_id=actor.id, team_id=team.id if team else None, proposal_type=proposal_type, title=title_value, version=version_number, status="DRAFT" if is_draft else ("RESUBMITTED" if previous else "SUBMITTED"), processing_status="PENDING" if is_draft else "COMPLETED", filename=proposal_file.filename or "proposal", content_type=extracted.content_type, file_size=extracted.file_size, sha256=extracted.sha256, page_count=extracted.page_count, storage_key=str(path.relative_to(settings.document_storage_root)), extracted_text=extracted.extracted_text, extracted_fields=fields, template_reference_version_id=template_version.id)
    session.add(row)
    session.flush()
    if is_draft:
        session.commit()
        return {"submission": _submission_out(session, row), "report": None}
    history = _version_history(session, row)
    report = build_compliance_report(submission=row, rules=rules, previous_versions=history)
    session.add(ProposalComplianceReport(submission_id=row.id, status=report["reportSummary"]["status"], score=report["reportSummary"]["score"], total_checks=report["finalResults"]["totalChecks"], report=report))
    session.commit()
    if team is not None and not is_draft:
        lock_team(session, team.id, "proposal_submitted")
        session.commit()
    return {"submission": _submission_out(session, row), "report": report}


def _run_submission(session: Session, row: ProposalComplianceSubmission, template_version: TemplateReferenceVersion, rules: dict[str, Any]) -> dict[str, Any]:
    history = _version_history(session, row)
    row.template_reference_version_id = template_version.id
    row.status = "SUBMITTED" if row.status == "DRAFT" else row.status
    row.processing_status = "COMPLETED"
    row.error_message = None
    report_data = build_compliance_report(submission=row, rules=rules, previous_versions=history)
    saved = session.scalar(select(ProposalComplianceReport).where(ProposalComplianceReport.submission_id == row.id).limit(1))
    if saved is None:
        saved = ProposalComplianceReport(submission_id=row.id, status=report_data["reportSummary"]["status"], score=report_data["reportSummary"]["score"], total_checks=report_data["finalResults"]["totalChecks"], report=report_data)
        session.add(saved)
    else:
        saved.status = report_data["reportSummary"]["status"]
        saved.score = report_data["reportSummary"]["score"]
        saved.total_checks = report_data["finalResults"]["totalChecks"]
        saved.report = report_data
    session.commit()
    session.refresh(row)
    return {"submission": _submission_out(session, row), "report": report_data}


@router.post("/submissions/{submission_id}/submit")
def submit_draft(submission_id: int, request: Request, actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(ProposalComplianceSubmission, submission_id)
    if row is None or not _owner_scope(row, actor, _student_team(session, actor)):
        raise _error("submission_not_found", "The proposal draft was not found.", 404)
    if row.status != "DRAFT":
        raise _error("invalid_submission_state", "Only a draft proposal can be submitted.", 409)
    active = _active_template(session, row.proposal_type)
    if active is None:
        raise _error("active_template_missing", "No active university template exists for this proposal type.", 409)
    return _run_submission(session, row, *active)


@router.post("/submissions/{submission_id}/withdraw")
def withdraw_submission(submission_id: int, request: Request, actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    """Withdraw a student-owned draft/submission without deleting its history."""
    validate_mutating_origin(request)
    row = session.get(ProposalComplianceSubmission, submission_id)
    if row is None or not _owner_scope(row, actor, _student_team(session, actor)):
        raise _error("submission_not_found", "The proposal submission was not found.", 404)
    if row.status not in {"DRAFT", "SUBMITTED", "RESUBMITTED", "CHANGES_REQUESTED"}:
        raise _error("invalid_submission_state", "This proposal cannot be withdrawn in its current state.", 409)
    row.status = "WITHDRAWN"
    row.processing_status = "COMPLETED"
    session.commit()
    session.refresh(row)
    return _submission_out(session, row)


@router.patch("/submissions/{submission_id}/status")
def update_submission_status(submission_id: int, payload: ProposalStatusUpdate, request: Request, actor: User = Depends(require_roles(*REVIEW_ROLES)), session: Session = Depends(get_db)):
    """Allow an authorized reviewer to record a lifecycle decision."""
    validate_mutating_origin(request)
    desired = payload.status.strip().upper()
    if desired not in PROPOSAL_REVIEW_STATUSES:
        raise _error("invalid_submission_status", "Review status must be CHANGES_REQUESTED, APPROVED, or REJECTED.", 422)
    row = session.get(ProposalComplianceSubmission, submission_id)
    if row is None or not _can_view(session, actor, row):
        raise _error("submission_not_found", "The proposal submission was not found.", 404)
    if row.status == "WITHDRAWN":
        raise _error("invalid_submission_state", "A withdrawn proposal cannot be reviewed.", 409)
    row.status = desired
    row.processing_status = "COMPLETED"
    session.commit()
    session.refresh(row)
    return _submission_out(session, row)


@router.get("/submissions/mine")
def my_submissions(actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    team = _student_team(session, actor)
    ownership_filter = or_(ProposalComplianceSubmission.team_id == team.id, ProposalComplianceSubmission.owner_user_id == actor.id) if team is not None else ProposalComplianceSubmission.owner_user_id == actor.id
    rows = session.scalars(select(ProposalComplianceSubmission).where(ownership_filter).order_by(desc(ProposalComplianceSubmission.created_at), desc(ProposalComplianceSubmission.version))).all()
    return [_submission_out(session, row) for row in rows]


@router.get("/submissions/{submission_id}")
def get_submission(submission_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    row = session.get(ProposalComplianceSubmission, submission_id)
    if row is None or not _can_view(session, actor, row):
        raise _error("submission_not_found", "The proposal submission was not found.", 404)
    report = session.scalar(select(ProposalComplianceReport).where(ProposalComplianceReport.submission_id == row.id).limit(1))
    return {"submission": _submission_out(session, row), "report": report.report if report else None, "versionHistory": _version_history(session, row)}


@router.get("/reports")
def report_queue(actor: User = Depends(require_roles(*REVIEW_ROLES)), session: Session = Depends(get_db)):
    rows = session.scalars(select(ProposalComplianceSubmission).order_by(desc(ProposalComplianceSubmission.created_at), desc(ProposalComplianceSubmission.version))).all()
    return [_submission_out(session, row) for row in rows if _can_view(session, actor, row)]


@router.get("/reports/{submission_id}")
def get_report(submission_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    row = session.get(ProposalComplianceSubmission, submission_id)
    if row is None or not _can_view(session, actor, row):
        raise _error("report_not_found", "The compliance report was not found.", 404)
    report = session.scalar(select(ProposalComplianceReport).where(ProposalComplianceReport.submission_id == row.id).limit(1))
    if report is None:
        raise _error("report_pending", "The compliance report is not available yet.", 409)
    return report.report


def _report_fingerprint(report: dict) -> str:
    return hashlib.sha256(json.dumps({key: value for key, value in report.items() if key != "aiSummary"}, sort_keys=True, default=str).encode()).hexdigest()


@router.post("/reports/{submission_id}/ai-summary")
async def generate_compliance_summary(submission_id: int, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(ProposalComplianceSubmission, submission_id)
    if row is None or not _can_view(session, actor, row):
        raise _error("report_not_found", "The compliance report was not found.", 404)
    report = session.scalar(select(ProposalComplianceReport).where(ProposalComplianceReport.submission_id == row.id))
    if report is None:
        raise _error("report_pending", "Run the compliance check before generating its summary.", 409)
    fingerprint = _report_fingerprint(report.report)
    cached = report.report.get("aiSummary")
    if cached and cached.get("status") == "COMPLETED" and cached.get("report_fingerprint") == fingerprint and cached.get("input_scope") == "FULL_DOCUMENT_AND_REPORT_V1" and cached.get("report_format") == REPORT_VERSION:
        return cached
    context = {
        "proposal_text": row.extracted_text,
        "proposal_fields": row.extracted_fields,
        "compliance_report": {key: value for key, value in report.report.items() if key != "aiSummary"},
    }
    actor_id = actor.id
    source_sha = row.sha256
    session.rollback()
    result = await generate_full_report(context, run_ai_json, rate_key=f"compliance-summary:{actor_id}")
    saved = {"status": result.get("status", "UNAVAILABLE"), "model": result.get("model"), "provider": result.get("provider"), "generated_at": result.get("timestamp"), "advisory": True, "report_fingerprint": fingerprint, "source_sha256": source_sha, "input_scope": "FULL_DOCUMENT_AND_REPORT_V1", "report_format": REPORT_VERSION}
    if result.get("status") == "COMPLETED":
        saved["summary"] = assemble_report(result["payload"], context)
    else:
        saved["message"] = result.get("message") or "AI summary is unavailable. The rule-based compliance report remains available. Retry generation when the model is ready."
    report = session.scalar(select(ProposalComplianceReport).where(ProposalComplianceReport.submission_id == submission_id).with_for_update())
    if report is None or _report_fingerprint(report.report) != fingerprint:
        session.rollback()
        raise _error("report_changed", "The compliance report changed during generation. Retry its summary.", 409)
    report.report = {**report.report, "aiSummary": saved}
    session.commit()
    return saved


@router.post("/reports/{submission_id}/run")
def rerun_report(submission_id: int, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    """Explicitly re-run a report against the current active baseline."""
    validate_mutating_origin(request)
    row = session.get(ProposalComplianceSubmission, submission_id)
    if row is None or not _can_view(session, actor, row):
        raise _error("report_not_found", "The compliance report was not found.", 404)
    active = _active_template(session, row.proposal_type)
    if active is None:
        raise _error("active_template_missing", "No active university template exists for this proposal type.", 409)
    return _run_submission(session, row, *active)["report"]


@router.get("/reports/{submission_id}/original")
def get_original(submission_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    row = session.get(ProposalComplianceSubmission, submission_id)
    if row is None or not _can_view(session, actor, row):
        raise _error("document_not_found", "The original proposal was not found.", 404)
    path = settings.document_storage_root / row.storage_key
    if not path.is_file():
        raise _error("document_missing", "The original proposal file is no longer available.", 404)
    return FileResponse(path, media_type=row.content_type, filename=row.filename)


@router.get("/reports/{submission_id}/annotated")
def get_annotated_document(submission_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    """Return a safe annotated copy; the student's original file is never modified."""
    row = session.get(ProposalComplianceSubmission, submission_id)
    if row is None or not _can_view(session, actor, row):
        raise _error("document_not_found", "The annotated proposal was not found.", 404)
    saved = session.scalar(select(ProposalComplianceReport).where(ProposalComplianceReport.submission_id == row.id).limit(1))
    if saved is None:
        raise _error("report_pending", "The compliance report is not available yet.", 409)
    path = settings.document_storage_root / row.storage_key
    if not path.is_file():
        raise _error("document_missing", "The original proposal file is no longer available.", 404)
    try:
        data = _render_annotated_document(path.read_bytes(), row.content_type, row.filename, saved.report)
    except PdfExtractionError as error:
        raise _error(error.code, error.message, 422) from error
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="annotated-{_safe_filename(row.filename.rsplit(".", 1)[0])}.pdf"'})


@router.get("/reports/{submission_id}/pdf")
def download_report_pdf(submission_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    row = session.get(ProposalComplianceSubmission, submission_id)
    if row is None or not _can_view(session, actor, row):
        raise _error("report_not_found", "The compliance report was not found.", 404)
    saved = session.scalar(select(ProposalComplianceReport).where(ProposalComplianceReport.submission_id == row.id).limit(1))
    if saved is None:
        raise _error("report_pending", "The compliance report is not available yet.", 409)
    data = _render_pdf(saved.report)
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="compliance-report-{submission_id}.pdf"'})


def _render_pdf(report: dict[str, Any]) -> bytes:
    from io import BytesIO
    from xml.sax.saxutils import escape

    stream = BytesIO()
    document = SimpleDocTemplate(stream, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    summary = report.get("reportSummary", {})
    story = [Paragraph("FYPHub Compliance Report", styles["Title"]), Paragraph(f"{report.get('proposal', {}).get('title', 'Proposal')} · Score {summary.get('score', 0)}% · {summary.get('status', 'Review Required')}", styles["Normal"]), Spacer(1, 8)]
    story.append(Table([["Passed", "Failed", "Partial", "Total"], [summary.get("metrics", {}).get("passed", 0), summary.get("metrics", {}).get("failed", 0), summary.get("metrics", {}).get("partial", 0), summary.get("metrics", {}).get("total", 0)]], colWidths=[38 * mm] * 4, style=TableStyle([["BACKGROUND", (0, 0), (-1, 0), "#1E2436"], ["TEXTCOLOR", (0, 0), (-1, 0), "white"], ["GRID", (0, 0), (-1, -1), 0.25, "#D8E0EA"], ["ALIGN", (0, 0), (-1, -1), "CENTER"], ["BACKGROUND", (0, 1), (-1, 1), "#F5F8FC"]])))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Checks needing attention (including partial and unverifiable)", styles["Heading2"]))
    for category in report.get("categories", []):
        for check in category.get("checks", []):
            if check.get("status") == "PASS":
                continue
            story.append(Paragraph(escape(f"{category.get('name')} / {check.get('name')} — {check.get('status')}"), styles["Heading3"]))
            for label, key in (("Expected", "expected"), ("Detected", "actual"), ("Location", "location"), ("Evidence / reason", "evidence")):
                value = check.get(key)
                story.append(Paragraph(escape(f"{label}: {value if value is not None else 'Not available'}"), styles["BodyText"]))
            story.append(Spacer(1, 6))
    story.append(Paragraph("Detailed Violations", styles["Heading2"]))
    for violation in report.get("violations", []):
        story.extend([Paragraph(f"{violation.get('id')} · {violation.get('severity')} · {violation.get('title')}", styles["Heading3"]), Paragraph(f"Location: {violation.get('location', 'Document')} · Requirement: {violation.get('requirement')} · Detected: {violation.get('detected')}", styles["BodyText"]), Paragraph(str(violation.get("evidence", "")), styles["BodyText"]), Spacer(1, 6)])
    document.build(story)
    return stream.getvalue()


def _render_annotated_document(data: bytes, content_type: str, filename: str, report: dict[str, Any]) -> bytes:
    """Annotate each affected page with red issue callouts and append full evidence."""
    from io import BytesIO
    try:
        import fitz
    except ImportError as error:
        raise PdfExtractionError("pdf_annotation_unavailable", "PDF annotation is unavailable on this server.") from error
    if not filename.casefold().endswith(".pdf") or not content_type.casefold().endswith("pdf"):
        raise PdfExtractionError("pdf_annotation_unavailable", "Annotated preview is currently available for PDF proposals only.")
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as error:
        raise PdfExtractionError("invalid_pdf", "The proposal PDF could not be opened for annotation.") from error
    violations = report.get("violations", [])
    by_page: dict[int, list[dict[str, Any]]] = {}
    for violation in violations:
        page_number = violation.get("pageNumber") or (violation.get("location", {}).get("page") if isinstance(violation.get("location"), dict) else None) or 1
        by_page.setdefault(max(1, int(page_number)), []).append(violation)
    for page_number, page_violations in by_page.items():
        if page_number > document.page_count:
            continue
        page = document[page_number - 1]
        for index, violation in enumerate(page_violations[:6]):
            top = 24 + index * 43
            rect = fitz.Rect(24, top, page.rect.width - 24, top + 35)
            page.draw_rect(rect, color=(0.88, 0.08, 0.14), fill=(1, 0.93, 0.94), width=1.6, overlay=True)
            label = f"{violation.get('id', 'Issue')} | {violation.get('title', 'Compliance issue')} | Expected: {display_value(violation.get('requirement'))} | Detected: {display_value(violation.get('detected'))}"
            page.insert_textbox(rect + (5, 4, -5, -4), label[:300], fontsize=8, color=(0.55, 0.05, 0.08), overlay=True)
    appendix = document.new_page()
    appendix.insert_text((36, 45), "FYPHub - Annotated Compliance Findings", fontsize=16, color=(0.1, 0.18, 0.3))
    y = 75
    for violation in violations:
        text = f"{violation.get('id', 'Issue')} | {violation.get('severity', 'Review')} | {violation.get('title', 'Compliance issue')}\nLocation: {violation.get('location', 'Document')}\nExpected: {display_value(violation.get('requirement'))}\nDetected: {display_value(violation.get('detected'))}\nEvidence: {violation.get('evidence', '')}"
        box = fitz.Rect(36, y, appendix.rect.width - 36, y + 70)
        appendix.draw_rect(box, color=(0.88, 0.08, 0.14), fill=(1, 0.95, 0.95), width=1.2, overlay=True)
        appendix.insert_textbox(box + (8, 7, -8, -7), text[:700], fontsize=8, color=(0.18, 0.2, 0.25), overlay=True)
        y += 82
        if y > appendix.rect.height - 90:
            appendix = document.new_page(); y = 45
    output = BytesIO()
    document.save(output, garbage=4, deflate=True)
    document.close()
    return output.getvalue()


def display_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return "Not available" if value is None or value == "" else str(value)
