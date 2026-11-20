"""Module 3 APIs: template ingestion, proposal submissions, and reports."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
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
from ...models import AcademicRuleVersion, ProposalComplianceReport, ProposalComplianceSubmission, ProposalVersionComparison, SupervisorAssignment, Team, TeamMember, TemplateReference, TemplateReferenceVersion, TemplateType, User, UserRole
from ...pdf_extraction import PdfExtractionError, extract_proposal_document
from ...document_preview import DocumentPreviewError, render_document_preview
from .compliance_engine import build_change_summary, build_compliance_report, build_document_difference_issues
from .comparison import build_version_comparison, generate_comparison_summary
from .template_extractor import extract_template_rules, normalize_template_rules
from ...team_lifecycle import lock_team
from ...ai_provider import provider_config, run_ai_json
from .report_summary import generate_report_summary, prepare_user_friendly_report

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


def _safe_stored_path(storage_key: str | None) -> Path | None:
    if not storage_key:
        return None
    root = settings.document_storage_root.resolve()
    candidate = (root / storage_key).resolve()
    return candidate if candidate.is_relative_to(root) else None


def _inline_headers(filename: str, page_count: int) -> dict[str, str]:
    safe_name = _safe_filename(filename)
    return {"Content-Disposition": f'inline; filename="{safe_name}"', "X-Preview-Page-Count": str(max(1, page_count)), "Cache-Control": "private, max-age=300"}


def _preview_response(path: Path, content_type: str | None, filename: str | None) -> Response:
    try:
        preview = render_document_preview(path, content_type, filename, settings.document_storage_root)
    except DocumentPreviewError as error:
        raise _error(error.code, error.message, 422 if error.code != "document_missing" else 404) from error
    return Response(content=preview.content, media_type=preview.media_type, headers=_inline_headers(preview.filename, preview.page_count))


def _template_source_path(session: Session, version_id: int) -> tuple[Path, str] | None:
    rule = session.scalar(select(AcademicRuleVersion).where(AcademicRuleVersion.template_reference_version_id == version_id).order_by(desc(AcademicRuleVersion.version_number)).limit(1))
    source = (rule.rules or {}).get("source") if rule else None
    storage_key = source.get("storage_key") if isinstance(source, dict) else None
    path = _safe_stored_path(storage_key if isinstance(storage_key, str) else None)
    if path is None:
        return None
    return path, path.name


def _template_rules(session: Session, version_id: int) -> dict[str, Any]:
    rule = session.scalar(select(AcademicRuleVersion).where(AcademicRuleVersion.template_reference_version_id == version_id).order_by(desc(AcademicRuleVersion.version_number)).limit(1))
    return normalize_template_rules(dict(rule.rules)) if rule else {}


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
    summary = prepare_user_friendly_report(report.report).get("reportSummary", {}) if report else {}
    return {"id": row.id, "proposal_key": row.proposal_key, "title": row.title, "proposal_type": row.proposal_type, "version": row.version, "status": row.status, "processing_status": row.processing_status, "filename": row.filename, "page_count": row.page_count, "created_at": row.created_at, "score": summary.get("score"), "report_status": summary.get("status"), "report_available": report is not None}


def _report_out(session: Session, row: ProposalComplianceSubmission, report: dict[str, Any]) -> dict[str, Any]:
    payload = prepare_user_friendly_report(report)
    owner = session.get(User, row.owner_user_id)
    payload["student"] = {"name": owner.full_name if owner else "Student", "email": owner.email if owner else None, "registrationNumber": owner.registration_number if owner else None}
    return payload


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


def _previous_audited_submission(session: Session, row: ProposalComplianceSubmission) -> tuple[ProposalComplianceSubmission, ProposalComplianceReport] | None:
    owner_scope = or_(ProposalComplianceSubmission.team_id == row.team_id, ProposalComplianceSubmission.owner_user_id == row.owner_user_id) if row.team_id is not None else ProposalComplianceSubmission.owner_user_id == row.owner_user_id
    match = session.execute(
        select(ProposalComplianceSubmission, ProposalComplianceReport)
        .join(ProposalComplianceReport, ProposalComplianceReport.submission_id == ProposalComplianceSubmission.id)
        .where(ProposalComplianceSubmission.proposal_key == row.proposal_key, owner_scope, ProposalComplianceSubmission.version < row.version)
        .order_by(desc(ProposalComplianceSubmission.version))
        .limit(1)
    ).first()
    return (match[0], match[1]) if match else None


def _comparison_out(comparison: ProposalVersionComparison) -> dict[str, Any]:
    payload = dict(comparison.comparison or {})
    payload.update({
        "id": comparison.id,
        "previousSubmissionId": comparison.previous_submission_id,
        "currentSubmissionId": comparison.current_submission_id,
        "previousReportId": comparison.previous_report_id,
        "currentReportId": comparison.current_report_id,
        "createdAt": comparison.created_at,
        "aiSummary": comparison.ai_summary,
        "aiStatus": comparison.ai_status,
        "aiMeta": {"source": comparison.ai_source, "model": comparison.ai_model, "provider": comparison.ai_provider, "generatedAt": comparison.ai_generated_at, "inputScope": "STRUCTURED_VERSION_COMPARISON_V1"} if comparison.ai_status else None,
    })
    return payload


def _ensure_version_comparison(session: Session, row: ProposalComplianceSubmission) -> tuple[ProposalVersionComparison | None, bool]:
    current_report = session.scalar(select(ProposalComplianceReport).where(ProposalComplianceReport.submission_id == row.id).limit(1))
    if current_report is None:
        return None, False
    existing = session.scalar(select(ProposalVersionComparison).where(ProposalVersionComparison.current_submission_id == row.id).limit(1))
    if existing is not None:
        return existing, False
    previous = _previous_audited_submission(session, row)
    if previous is None:
        return None, False
    previous_row, previous_report = previous
    result = build_version_comparison(previous_report=previous_report.report, current_report=current_report.report, previous_version=previous_row.version, current_version=row.version, previous_template_version_id=previous_row.template_reference_version_id, current_template_version_id=row.template_reference_version_id)
    comparison = ProposalVersionComparison(
        previous_submission_id=previous_row.id, current_submission_id=row.id, previous_report_id=previous_report.id, current_report_id=current_report.id,
        previous_version=result["previousVersion"], current_version=result["currentVersion"], previous_score=result["previousScore"], current_score=result["newScore"], score_difference=result["scoreDifference"], overall_result=result["overallResult"],
        previous_issue_count=result["previousIssueCount"], current_issue_count=result["currentIssueCount"], fixed_count=len(result["fixedIssues"]), remaining_count=len(result["remainingIssues"]), new_count=len(result["newIssues"]), unchanged_count=len(result["unchangedIssues"]), net_issue_change=result["netIssueChange"], different_template_versions=result["differentTemplateVersions"], comparison=result,
    )
    session.add(comparison)
    session.flush()
    return comparison, True


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
    if not rules.get("required_sections") and not any(key in rules for key in ("page_size", "top_margin_mm", "bottom_margin_mm", "left_margin_mm", "right_margin_mm", "font_family", "font_size_pt", "line_spacing", "alignment", "heading_style", "page_numbering", "required_references", "required_captions", "required_tables", "required_figures", "required_appendices")):
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
    """Delete an inactive template while preserving historical compliance results."""
    validate_mutating_origin(request)
    version = session.get(TemplateReferenceVersion, version_id)
    if version is None:
        raise _error("template_not_found", "Template version was not found.", 404)
    if version.is_active:
        raise _error("template_active", "Deactivate the template before deleting it.", 409)
    source = _template_source_path(session, version_id)
    try:
        # Historical submissions keep their measured report snapshot, so they
        # no longer need a live FK to a template that an administrator removes.
        # Detach the reference before deleting the immutable template row.
        session.execute(
            update(ProposalComplianceSubmission)
            .where(ProposalComplianceSubmission.template_reference_version_id == version_id)
            .values(template_reference_version_id=None)
        )
        session.execute(delete(AcademicRuleVersion).where(AcademicRuleVersion.template_reference_version_id == version_id))
        session.delete(version)
        session.commit()
    except Exception as error:
        session.rollback()
        raise _error("template_delete_failed", "The template could not be deleted. No historical submission was changed.", 409) from error
    if source is not None:
        try:
            source[0].unlink(missing_ok=True)
        except OSError:
            # Database deletion is already complete; an orphaned source file
            # should not turn a successful admin delete into a 500 response.
            pass
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
    allowed = {"page_size", "top_margin_mm", "bottom_margin_mm", "left_margin_mm", "right_margin_mm", "font_family", "font_size_pt", "line_spacing", "alignment", "heading_style", "page_numbering", "required_sections", "required_references", "required_captions", "required_tables", "required_figures", "required_appendices"}
    cleaned: dict[str, Any] = normalize_template_rules({key: value for key, value in rules.items() if key in allowed})
    existing_rules = _template_rules(session, version.id)
    if isinstance(existing_rules.get("source"), dict):
        cleaned["source"] = existing_rules["source"]
    for key in ("top_margin_mm", "bottom_margin_mm", "left_margin_mm", "right_margin_mm", "font_size_pt", "line_spacing", "required_references", "required_appendices", "required_captions", "required_tables", "required_figures"):
        if key in cleaned and cleaned[key] not in (None, ""):
            try:
                number = float(cleaned[key])
                cleaned[key] = int(number) if number.is_integer() and key.startswith("required_") else number
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
    report = build_compliance_report(submission=row, rules=rules, previous_versions=history, template_name=template_version.title)
    session.add(ProposalComplianceReport(submission_id=row.id, status=report["reportSummary"]["status"], score=report["reportSummary"]["score"], total_checks=report["finalResults"]["totalChecks"], report=report))
    session.flush()
    _ensure_version_comparison(session, row)
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
    report_data = build_compliance_report(submission=row, rules=rules, previous_versions=history, template_name=template_version.title)
    saved = session.scalar(select(ProposalComplianceReport).where(ProposalComplianceReport.submission_id == row.id).limit(1))
    if saved is None:
        saved = ProposalComplianceReport(submission_id=row.id, status=report_data["reportSummary"]["status"], score=report_data["reportSummary"]["score"], total_checks=report_data["finalResults"]["totalChecks"], report=report_data)
        session.add(saved)
    else:
        saved.status = report_data["reportSummary"]["status"]
        saved.score = report_data["reportSummary"]["score"]
        saved.total_checks = report_data["finalResults"]["totalChecks"]
        saved.report = report_data
    session.flush()
    _ensure_version_comparison(session, row)
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
    return {"submission": _submission_out(session, row), "report": _report_out(session, row, report.report) if report else None, "versionHistory": _version_history(session, row)}


@router.get("/reports")
def report_queue(actor: User = Depends(require_roles(*REVIEW_ROLES)), session: Session = Depends(get_db)):
    rows = session.scalars(select(ProposalComplianceSubmission).order_by(desc(ProposalComplianceSubmission.created_at), desc(ProposalComplianceSubmission.version))).all()
    return [_submission_out(session, row) for row in rows if _can_view(session, actor, row)]


@router.get("/submissions/{submission_id}/comparison")
def get_version_comparison(submission_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    row = session.get(ProposalComplianceSubmission, submission_id)
    if row is None or not _can_view(session, actor, row):
        raise _error("submission_not_found", "The proposal submission was not found.", 404)
    if session.scalar(select(ProposalComplianceReport).where(ProposalComplianceReport.submission_id == row.id).limit(1)) is None:
        raise _error("report_pending", "Run the compliance check before comparing versions.", 409)
    comparison, created = _ensure_version_comparison(session, row)
    if created:
        session.commit()
        session.refresh(comparison)
    if comparison is None:
        return {"status": "NO_PREVIOUS_VERSION", "message": "No previous version available for comparison.", "comparison": None}
    return {"status": "AVAILABLE", "comparison": _comparison_out(comparison)}


@router.get("/reports/{submission_id}")
def get_report(submission_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    row = session.get(ProposalComplianceSubmission, submission_id)
    if row is None or not _can_view(session, actor, row):
        raise _error("report_not_found", "The compliance report was not found.", 404)
    report = session.scalar(select(ProposalComplianceReport).where(ProposalComplianceReport.submission_id == row.id).limit(1))
    if report is None:
        raise _error("report_pending", "The compliance report is not available yet.", 409)
    return _report_out(session, row, report.report)


@router.post("/reports/{submission_id}/summary")
async def generate_report_ai_summary(submission_id: int, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    """Explain the verified report without sending the proposal or PDF to the model."""
    validate_mutating_origin(request)
    row = session.get(ProposalComplianceSubmission, submission_id)
    if row is None or not _can_view(session, actor, row):
        raise _error("report_not_found", "The compliance report was not found.", 404)
    saved = session.scalar(select(ProposalComplianceReport).where(ProposalComplianceReport.submission_id == row.id).limit(1))
    if saved is None:
        raise _error("report_pending", "The compliance report is not available yet.", 409)
    current = prepare_user_friendly_report(saved.report)
    if current.get("aiSummary") and current.get("aiSummaryStatus") in {"COMPLETED", "FALLBACK"}:
        return _report_out(session, row, current)
    actor_id = actor.id
    model_override = settings.ollama_fallback_model if provider_config().get("provider") == "ollama" else None
    session.rollback()
    result = await generate_report_summary(current, run_ai_json, rate_key=f"proposal-compliance-report:{actor_id}", model_override=model_override)
    refreshed = session.scalar(select(ProposalComplianceReport).where(ProposalComplianceReport.submission_id == row.id).with_for_update())
    if refreshed is None:
        session.rollback()
        raise _error("report_changed", "The compliance report changed during summary generation. Retry.", 409)
    report_payload = prepare_user_friendly_report(refreshed.report)
    report_payload["aiSummary"] = result.get("summary")
    report_payload["aiSummaryStatus"] = result.get("status")
    report_payload["aiSummaryMeta"] = {key: result.get(key) for key in ("source", "model", "provider", "generatedAt", "inputScope", "fallbackReason") if result.get(key) is not None}
    refreshed.report = report_payload
    session.commit()
    session.refresh(refreshed)
    return _report_out(session, row, refreshed.report)


@router.post("/comparisons/{comparison_id}/summary")
async def generate_version_comparison_summary(comparison_id: int, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    comparison = session.get(ProposalVersionComparison, comparison_id)
    current = session.get(ProposalComplianceSubmission, comparison.current_submission_id) if comparison else None
    if comparison is None or current is None or not _can_view(session, actor, current):
        raise _error("comparison_not_found", "The version comparison was not found.", 404)
    if comparison.ai_summary and comparison.ai_status in {"COMPLETED", "FALLBACK"}:
        return _comparison_out(comparison)
    structured_comparison = dict(comparison.comparison or {})
    actor_id = actor.id
    session.rollback()
    result = await generate_comparison_summary(structured_comparison, run_ai_json, rate_key=f"proposal-version-comparison:{actor_id}")
    generated_at = result.get("generatedAt")
    parsed_generated_at = None
    if isinstance(generated_at, str):
        try:
            parsed_generated_at = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except ValueError:
            parsed_generated_at = None
    saved = session.scalar(select(ProposalVersionComparison).where(ProposalVersionComparison.id == comparison_id).with_for_update())
    if saved is None:
        session.rollback()
        raise _error("comparison_changed", "The version comparison changed during summary generation. Retry.", 409)
    saved.ai_summary = result.get("summary")
    saved.ai_status = result.get("status")
    saved.ai_source = result.get("source")
    saved.ai_model = result.get("model")
    saved.ai_provider = result.get("provider")
    saved.ai_generated_at = parsed_generated_at
    session.commit()
    session.refresh(saved)
    return _comparison_out(saved)


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
    path = _safe_stored_path(row.storage_key)
    if path is None:
        raise _error("document_missing", "The original proposal file is no longer available.", 404)
    return _preview_response(path, row.content_type, row.filename)


@router.get("/reports/{submission_id}/template")
def get_original_template(submission_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    """Preview the exact university template attached to this compliance report."""
    row = session.get(ProposalComplianceSubmission, submission_id)
    if row is None or not _can_view(session, actor, row):
        raise _error("template_not_found", "The university template was not found.", 404)
    source = _template_source_path(session, row.template_reference_version_id or 0)
    if source is None:
        raise _error("template_preview_unavailable", "The original university template file is not available for preview.", 404)
    path, filename = source
    return _preview_response(path, None, filename)


@router.get("/reports/{submission_id}/annotated")
def get_annotated_document(submission_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    """Return a safe annotated copy; the student's original file is never modified."""
    row = session.get(ProposalComplianceSubmission, submission_id)
    if row is None or not _can_view(session, actor, row):
        raise _error("document_not_found", "The annotated proposal was not found.", 404)
    saved = session.scalar(select(ProposalComplianceReport).where(ProposalComplianceReport.submission_id == row.id).limit(1))
    if saved is None:
        raise _error("report_pending", "The compliance report is not available yet.", 409)
    path = _safe_stored_path(row.storage_key)
    if path is None:
        raise _error("document_missing", "The original proposal file is no longer available.", 404)
    try:
        preview = render_document_preview(path, row.content_type, row.filename, settings.document_storage_root)
        data = _render_annotated_document(preview.content, "application/pdf", preview.filename, saved.report)
    except (PdfExtractionError, DocumentPreviewError) as error:
        raise _error(error.code, error.message, 422) from error
    try:
        import fitz

        annotated_pdf = fitz.open(stream=data, filetype="pdf")
        try:
            page_count = annotated_pdf.page_count
        finally:
            annotated_pdf.close()
    except Exception:
        page_count = 1
    return Response(content=data, media_type="application/pdf", headers=_inline_headers(f'annotated-{_safe_filename(row.filename.rsplit(".", 1)[0])}.pdf', page_count))


@router.get("/reports/{submission_id}/pdf")
def download_report_pdf(submission_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    row = session.get(ProposalComplianceSubmission, submission_id)
    if row is None or not _can_view(session, actor, row):
        raise _error("report_not_found", "The compliance report was not found.", 404)
    saved = session.scalar(select(ProposalComplianceReport).where(ProposalComplianceReport.submission_id == row.id).limit(1))
    if saved is None:
        raise _error("report_pending", "The compliance report is not available yet.", 409)
    data = _render_pdf(saved.report)
    return Response(content=data, media_type="application/pdf", headers=_inline_headers(f"compliance-report-{submission_id}.pdf", 1))


def _render_pdf_legacy(report: dict[str, Any]) -> bytes:
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


def _page_label(pages: list[int] | None, page_count: int) -> str:
    normalized = sorted({int(page) for page in (pages or []) if int(page) > 0})
    if not normalized:
        normalized = list(range(1, max(1, int(page_count)) + 1))
    if len(normalized) == 1:
        return f"Page {normalized[0]}"
    if normalized == list(range(normalized[0], normalized[-1] + 1)):
        return f"Pages {normalized[0]}-{normalized[-1]}"
    return "Pages " + ", ".join(str(page) for page in normalized)


def _report_issues(report: dict[str, Any]) -> list[dict[str, Any]]:
    issues = report.get("documentDifferenceIssues")
    if isinstance(issues, list) and issues:
        return issues
    checks: list[dict[str, Any]] = []
    for category in report.get("categories", []):
        for check in category.get("checks", []):
            checks.append({**check, "category": check.get("category") or category.get("name") or "Template Compliance"})
    page_count = int(report.get("document", {}).get("pageCount") or 1)
    return build_document_difference_issues(checks, page_count)


def _render_pdf(report: dict[str, Any]) -> bytes:
    from io import BytesIO
    from xml.sax.saxutils import escape

    stream = BytesIO()
    document = SimpleDocTemplate(stream, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    styles["Title"].textColor = "#19304F"
    styles["Title"].fontSize = 20
    styles["Heading2"].textColor = "#19304F"
    report = prepare_user_friendly_report(report)
    summary = report.get("reportSummary", {})
    metadata = report.get("reportMetadata", {})
    proposal = report.get("proposal", {})
    template = report.get("template", {})
    issues = report.get("comparisonRows") or _report_issues(report)
    critical = [item for item in issues if item.get("statusCode") == "FAIL" or (item.get("severity") == "critical" and item.get("status") != "passed")]
    warnings = [item for item in issues if item.get("statusCode") in {"PARTIAL", "UNVERIFIABLE"} or (item.get("severity") == "warning" and item.get("status") != "passed")]
    status = summary.get("status") or "Needs Corrections"
    page_count = int(report.get("document", {}).get("pageCount") or 1)
    template_name = metadata.get("templateName") or template.get("title") or "Active University Template"
    analysis_date = str(metadata.get("analysisDate") or "").split("T", 1)[0] or "Current analysis"
    report_version = metadata.get("reportVersion") or "2.0"
    story = [
        Paragraph("Template Compliance and Document Difference Report", styles["Title"]),
        Paragraph("Strict comparison between university template and student document", styles["Normal"]),
        Spacer(1, 8),
    ]
    details = [
        ["Student / Project", proposal.get("title") or "Student document"],
        ["Template", template_name],
        ["Analysis date", analysis_date],
        ["Report version", report_version],
    ]
    story.append(Table([[Paragraph(f"<b>{escape(str(label))}</b>", styles["BodyText"]), Paragraph(escape(str(value)), styles["BodyText"])] for label, value in details], colWidths=[42 * mm, 128 * mm], style=TableStyle([["BACKGROUND", (0, 0), (0, -1), "#F3F6FB"], ["GRID", (0, 0), (-1, -1), 0.25, "#D8E0EA"], ["VALIGN", (0, 0), (-1, -1), "TOP"], ["LEFTPADDING", (0, 0), (-1, -1), 7], ["RIGHTPADDING", (0, 0), (-1, -1), 7], ["TOPPADDING", (0, 0), (-1, -1), 6], ["BOTTOMPADDING", (0, 0), (-1, -1), 6]])))
    story.append(Spacer(1, 12))
    summary_table = Table([
        ["Total Issues", "Critical Issues", "Warnings", "Submission Status"],
        [len([item for item in issues if item.get("status") != "passed"]), len(critical), len(warnings), status],
    ], colWidths=[42.5 * mm] * 4, style=TableStyle([["BACKGROUND", (0, 0), (-1, 0), "#1E2436"], ["TEXTCOLOR", (0, 0), (-1, 0), "white"], ["GRID", (0, 0), (-1, -1), 0.25, "#D8E0EA"], ["ALIGN", (0, 0), (-1, -1), "CENTER"], ["BACKGROUND", (0, 1), (-1, 1), "#F5F8FC"], ["FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"], ["TOPPADDING", (0, 0), (-1, -1), 8], ["BOTTOMPADDING", (0, 0), (-1, -1), 8]]))
    story.append(summary_table)
    story.append(Spacer(1, 14))
    for heading, group in (("What to Fix First", critical), ("Checks Requiring Verification", warnings), ("Passed Checks", [item for item in issues if item.get("statusCode") == "PASS" or item.get("status") == "passed"])):
        story.append(Paragraph(heading, styles["Heading2"]))
        if not group:
            story.append(Paragraph("No checks in this group.", styles["BodyText"]))
            story.append(Spacer(1, 6))
            continue
        for item in group:
            rows = [
                ("Issue", item.get("problem") or item.get("issue") or "Compliance requirement"),
                ("University Requirement", item.get("requirement") or item.get("originalTemplate") or "Requirement not configured"),
                ("Student Document", item.get("studentDocument") or "Measurement not detected"),
                ("Difference", item.get("difference") or "No difference detected"),
                ("Result", item.get("status") or "Verify"),
                ("Correction", item.get("correction") or item.get("requiredAction") or "Follow the active university template requirement."),
            ]
            story.append(Table([[Paragraph(f"<b>{escape(str(label))}</b>", styles["BodyText"]), Paragraph(escape(str(value)), styles["BodyText"])] for label, value in rows], colWidths=[48 * mm, 122 * mm], style=TableStyle([["BACKGROUND", (0, 0), (0, -1), "#F8FAFD"], ["GRID", (0, 0), (-1, -1), 0.25, "#D8E0EA"], ["VALIGN", (0, 0), (-1, -1), "TOP"], ["LEFTPADDING", (0, 0), (-1, -1), 7], ["RIGHTPADDING", (0, 0), (-1, -1), 7], ["TOPPADDING", (0, 0), (-1, -1), 6], ["BOTTOMPADDING", (0, 0), (-1, -1), 6]])))
            story.append(Spacer(1, 8))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Strict Rule: Page count, page numbering, page size, and approved template structure are mandatory. Every violation must show the exact affected page.", styles["BodyText"]))
    document.build(story)
    return stream.getvalue()


def _render_annotated_document_legacy(data: bytes, content_type: str, filename: str, report: dict[str, Any]) -> bytes:
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


def _render_annotated_document(data: bytes, content_type: str, filename: str, report: dict[str, Any]) -> bytes:
    """Annotate affected pages using the clean comparison issue contract."""
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
    issues = [item for item in _report_issues(report) if item.get("status") != "passed"]
    by_page: dict[int, list[dict[str, Any]]] = {}
    for issue in issues:
        for page_number in issue.get("affectedPages") or [1]:
            by_page.setdefault(max(1, int(page_number)), []).append(issue)
    for page_number, page_issues in by_page.items():
        if page_number > document.page_count:
            continue
        page = document[page_number - 1]
        for index, issue in enumerate(page_issues[:6]):
            top = 24 + index * 43
            rect = fitz.Rect(24, top, page.rect.width - 24, top + 35)
            page.draw_rect(rect, color=(0.88, 0.08, 0.14), fill=(1, 0.93, 0.94), width=1.6, overlay=True)
            label = f"{issue.get('issue', 'Compliance issue')} | {issue.get('difference', '')} | {_page_label(issue.get('affectedPages'), document.page_count)}"
            page.insert_textbox(rect + (5, 4, -5, -4), label[:300], fontsize=8, color=(0.55, 0.05, 0.08), overlay=True)
    appendix = document.new_page()
    appendix.insert_text((36, 45), "FYPHub - Annotated Compliance Findings", fontsize=16, color=(0.1, 0.18, 0.3))
    y = 75
    for issue in issues:
        text = "\n".join([
            f"Issue: {issue.get('issue', 'Compliance requirement')}",
            f"Original / University Template: {issue.get('originalTemplate', 'Template rule not configured')}",
            f"Student Document: {issue.get('studentDocument', 'Measurement not detected')}",
            f"Difference: {issue.get('difference', '')}",
            f"Strict Page Number: {_page_label(issue.get('affectedPages'), document.page_count)}",
            f"Required Action: {issue.get('requiredAction', '')}",
        ])
        box = fitz.Rect(36, y, appendix.rect.width - 36, y + 92)
        appendix.draw_rect(box, color=(0.88, 0.08, 0.14), fill=(1, 0.95, 0.95), width=1.2, overlay=True)
        appendix.insert_textbox(box + (8, 7, -8, -7), text[:900], fontsize=8, color=(0.18, 0.2, 0.25), overlay=True)
        y += 104
        if y > appendix.rect.height - 110:
            appendix = document.new_page(); y = 45
    output = BytesIO()
    document.save(output, garbage=4, deflate=True)
    document.close()
    return output.getvalue()
