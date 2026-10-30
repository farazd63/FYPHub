"""Module 03 API with existing cookie-session authorization."""

from __future__ import annotations

import hashlib
import asyncio
import os
import re
from datetime import datetime, timezone
from pathlib import PurePath
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...auth import get_current_user, validate_mutating_origin
from ...database import get_db
from ...models import SupervisorRequest, SupervisorRequestStatus, User, UserRole
from .models import M03CheckRun, M03ComplianceFinding, M03ComplianceReport, M03ExtractionStatus, M03ProposalDocument, M03ProposalType, M03ReferenceTemplate, M03TemplateRule
from .schemas_baseline import MetadataVersionWrite, RuleVersionWrite
from .schemas_report import ReportOut
from .services.admin_template_extractor import extract_baseline_rules
from .services.ast_parser import parse_document
from .services.check_1_visual import run_visual_check
from .services.check_2_structural import run_structural_check
from .services.check_3_semantic_llm import run_semantic_check
from .services.compliance_aggregator import aggregate_report
from .services.template_repository import active_template, latest_rule_version, next_template_version, rule_content_hash, save_rules

router = APIRouter(prefix="/api/v1/module-03")
MAX_BYTES = int(os.getenv("FYPHUB_M03_MAX_BYTES", str(15 * 1024 * 1024)))
READ_ROLES = (UserRole.STUDENT, UserRole.SUPERVISOR, UserRole.COORDINATOR, UserRole.ADMIN)


def _error(code: str, message: str, code_status: int = status.HTTP_409_CONFLICT) -> HTTPException:
    return HTTPException(code_status, detail={"code": code, "message": message})


def _actor(request: Request, session: Session = Depends(get_db)) -> User:
    return get_current_user(request, session)


def _require(actor: User, *roles: UserRole) -> User:
    if actor.role not in roles:
        raise _error("forbidden", "Insufficient permissions.", status.HTTP_403_FORBIDDEN)
    return actor


def _safe_filename(value: str) -> str:
    name = PurePath(value.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name[:255] or "module-03-document"


def _validate_upload(file: UploadFile, content: bytes) -> str:
    filename = _safe_filename(file.filename or "module-03-document")
    suffix = filename.casefold().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix not in {"pdf", "docx"} or not content:
        raise _error("invalid_document", "Module 03 accepts readable PDF or DOCX documents.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if len(content) > MAX_BYTES:
        raise _error("document_too_large", "The document exceeds the configured Module 03 size limit.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if suffix == "pdf" and not content.startswith(b"%PDF"):
        raise _error("invalid_pdf", "The uploaded file is not a readable PDF.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if suffix == "docx" and not content.startswith(b"PK"):
        raise _error("invalid_docx", "The uploaded file is not a readable DOCX.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return filename


def _template_out(row: M03ReferenceTemplate) -> dict:
    assessment = _baseline_assessment(row)
    return {"id": row.id, "template_type": row.template_type, "filename": row.filename, "version": row.version, "version_label": f"v{row.version} {row.version_kind.casefold()}", "version_kind": row.version_kind, "parent_template_id": row.parent_template_id, "template_metadata": row.template_metadata, "provenance": row.provenance, "extraction_status": row.extraction_status, "extracted_rules": row.extracted_rules, "extraction_warnings": row.extraction_warnings, "confidence": row.confidence, "baseline_status": assessment["status"], "missing_fields": assessment["missing_fields"], "activation_mode": row.activation_mode, "is_active": row.is_active, "sha256": row.sha256, "file_size": row.file_size, "created_at": row.created_at, "activated_at": row.activated_at}


def _baseline_assessment(row: M03ReferenceTemplate) -> dict[str, object]:
    rules = row.extracted_rules if isinstance(row.extracted_rules, dict) else {}
    missing = [str(item) for item in rules.get("missing_fields", []) if str(item).strip()]
    if not missing and not rules.get("baseline_status") == "COMPLETE":
        if not rules.get("expected_sections"):
            missing.append("Expected sections")
        if not rules.get("heading_order"):
            missing.append("Heading order")
        if not rules.get("heading_hierarchy") or any(item.get("level") is None for item in rules.get("heading_hierarchy", []) if isinstance(item, dict)):
            missing.append("Heading hierarchy")
        for key, label in (("margins", "Margins"), ("default_font_family", "Font family"), ("default_font_size_pt", "Font size"), ("line_spacing", "Line spacing"), ("paragraph_spacing", "Paragraph spacing")):
            value = rules.get(key)
            if key == "margins" and isinstance(value, dict):
                value = value if all(side in value and value.get(side) not in (None, "unknown", "") for side in ("left_mm", "right_mm", "top_mm", "bottom_mm")) else "unknown"
            if value is None or value == "unknown" or value == "Not detected in reference template" or value == {} or value == []:
                missing.append(label)
    confidence = str(row.confidence or "UNKNOWN").upper()
    if confidence != "HIGH":
        missing.append(f"Confidence {confidence}")
    if str(row.extraction_status).upper() != "EXTRACTED":
        missing.append(f"Extraction status {row.extraction_status}")
    deduped = list(dict.fromkeys(missing))
    return {"status": "COMPLETE" if not deduped else "INCOMPLETE", "missing_fields": deduped}


def _proposal_out(row: M03ProposalDocument) -> dict:
    return {"proposal_id": row.proposal_id, "proposal_type": row.proposal_type, "document_id": str(row.id), "version": row.version, "extraction_status": row.extraction_status, "ast": row.ast, "extraction_warnings": row.extraction_warnings}


def _report_out(row: M03ComplianceReport) -> dict:
    return {"report_id": row.report_id, "proposal_id": row.proposal_id, "proposal_type": row.proposal_type, "report_version": row.report_version, "status": row.status, "check_1": row.check_1, "check_2": row.check_2, "check_3": row.check_3, "total_findings": sum(row.severity_counts.values()), "severity_counts": row.severity_counts, "remediation": row.remediation, "advisory_summary": row.advisory_summary, "runtime_metadata": row.runtime_metadata, "generated_at": row.generated_at}


def _active_proposal(session: Session, proposal_id: str) -> M03ProposalDocument:
    row = session.scalar(select(M03ProposalDocument).where(M03ProposalDocument.proposal_id == proposal_id, M03ProposalDocument.is_active.is_(True)).order_by(M03ProposalDocument.version.desc()))
    if row is None:
        raise _error("proposal_not_found", "The proposal document was not found.", status.HTTP_404_NOT_FOUND)
    return row


def _authorized_proposal(session: Session, proposal_id: str, actor: User) -> M03ProposalDocument:
    row = _active_proposal(session, proposal_id)
    if actor.role == UserRole.ADMIN:
        return row
    if actor.role == UserRole.STUDENT and str(actor.id) == row.owner_user_id:
        return row
    if actor.role == UserRole.SUPERVISOR:
        try:
            requester_id = int(row.owner_user_id); supervisor_id = int(actor.id)
        except (TypeError, ValueError):
            requester_id = supervisor_id = -1
        if requester_id > 0 and session.scalar(select(SupervisorRequest.id).where(SupervisorRequest.requester_user_id == requester_id, SupervisorRequest.supervisor_id == supervisor_id, SupervisorRequest.status == SupervisorRequestStatus.ACCEPTED.value)):
            return row
    if actor.role == UserRole.COORDINATOR:
        return row
    raise _error("proposal_forbidden", "This proposal is outside your authorized scope.", status.HTTP_403_FORBIDDEN)


def _audit(session: Session, actor: User, action: str, target_id: str, values: dict) -> None:
    from ...main import add_admin_audit_event
    try:
        actor_id = int(actor.id)
    except (TypeError, ValueError):
        return
    add_admin_audit_event(session, actor_id=actor_id, affected_user_id=None, target_type="MODULE_03", target_id=abs(hash(target_id)) % 2147483647 or 1, action=action, changed_values=values)


@router.get("/admin/templates")
def list_templates(actor: User = Depends(_actor), session: Session = Depends(get_db)):
    _require(actor, UserRole.ADMIN)
    return [_template_out(row) for row in session.scalars(select(M03ReferenceTemplate).order_by(M03ReferenceTemplate.template_type, M03ReferenceTemplate.version.desc())).all()]


@router.post("/admin/templates", status_code=status.HTTP_201_CREATED)
@router.post("/admin/templates/upload", status_code=status.HTTP_201_CREATED)
async def upload_template(request: Request, template_type: str = Form(...), document: UploadFile = File(...), actor: User = Depends(_actor), session: Session = Depends(get_db)):
    _require(actor, UserRole.ADMIN); validate_mutating_origin(request)
    template_type = template_type.strip().upper()
    if template_type not in {M03ProposalType.SHORT.value, M03ProposalType.LONG.value}:
        raise _error("invalid_template_type", "Template type must be SHORT or LONG.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    content = await document.read(); filename = _validate_upload(document, content)
    ast = parse_document(content, filename, document.content_type); extracted = extract_baseline_rules(ast); version = next_template_version(session, template_type)
    row = M03ReferenceTemplate(template_type=template_type, filename=filename, storage_key=f"module-03/templates/{template_type.lower()}/v{version}-{filename}", sha256=hashlib.sha256(content).hexdigest(), mime_type=document.content_type or "application/octet-stream", file_size=len(content), content=content, version=version, version_kind="REFERENCE", template_metadata={}, provenance="Observed reference property", extraction_status="EXTRACTED" if ast.get("pages") or ast.get("paragraphs") else "FAILED", extracted_rules=extracted["rules"], extraction_warnings=extracted["warnings"], confidence=extracted["confidence"], uploaded_by_user_id=str(actor.id), is_active=False)
    session.add(row); session.flush(); save_rules(session, row, provenance=row.provenance); _audit(session, actor, "module03_template_uploaded", str(row.id), {"template_type": template_type, "version": version, "version_kind": row.version_kind, "sha256": row.sha256}); session.commit(); session.refresh(row)
    return _template_out(row)


@router.get("/admin/templates/{template_id}")
def template_detail(template_id: int, actor: User = Depends(_actor), session: Session = Depends(get_db)):
    _require(actor, UserRole.ADMIN); row = session.get(M03ReferenceTemplate, template_id)
    if row is None: raise _error("template_not_found", "The baseline template was not found.", status.HTTP_404_NOT_FOUND)
    return _template_out(row)


@router.post("/admin/templates/{template_id}/activate")
def activate_template(template_id: int, request: Request, active: bool = Form(True), activation_mode: str = Form("COMPLETE"), confirm_partial: bool = Form(False), actor: User = Depends(_actor), session: Session = Depends(get_db)):
    _require(actor, UserRole.ADMIN); validate_mutating_origin(request); row = session.get(M03ReferenceTemplate, template_id)
    if row is None: raise _error("template_not_found", "The baseline template was not found.", status.HTTP_404_NOT_FOUND)
    if active:
        assessment = _baseline_assessment(row)
        mode = activation_mode.strip().upper()
        if mode not in {"COMPLETE", "PARTIAL"}:
            raise _error("invalid_activation_mode", "Activation mode must be COMPLETE or PARTIAL.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        if assessment["status"] == "INCOMPLETE" and (mode != "PARTIAL" or not confirm_partial):
            raise _error("incomplete_baseline", "This baseline is incomplete. Confirm partial activation to continue.")
        if assessment["status"] == "COMPLETE" and mode == "PARTIAL":
            raise _error("invalid_activation_mode", "A complete baseline must be activated as COMPLETE.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        for previous in session.scalars(select(M03ReferenceTemplate).where(M03ReferenceTemplate.template_type == row.template_type, M03ReferenceTemplate.id != row.id, M03ReferenceTemplate.is_active.is_(True))).all(): previous.is_active = False
        row.is_active = True; row.activation_mode = mode; row.activated_at = datetime.now(timezone.utc); action = "module03_template_activated"
    else:
        row.is_active = False; action = "module03_template_deactivated"
    _audit(session, actor, action, str(row.id), {"template_type": row.template_type, "version": row.version, "is_active": active, "activation_mode": row.activation_mode, "confidence": row.confidence, "missing_fields": _baseline_assessment(row)["missing_fields"]}); session.commit(); session.refresh(row); return _template_out(row)


@router.post("/admin/templates/{template_id}/deactivate")
def deactivate_template(template_id: int, request: Request, actor: User = Depends(_actor), session: Session = Depends(get_db)):
    _require(actor, UserRole.ADMIN); validate_mutating_origin(request)
    row = session.get(M03ReferenceTemplate, template_id)
    if row is None:
        raise _error("template_not_found", "The baseline template was not found.", status.HTTP_404_NOT_FOUND)
    row.is_active = False
    _audit(session, actor, "module03_template_deactivated", str(row.id), {"template_type": row.template_type, "version": row.version, "is_active": False})
    session.commit(); session.refresh(row)
    return _template_out(row)


@router.get("/admin/templates/{template_id}/rules")
def template_rules(template_id: int, actor: User = Depends(_actor), session: Session = Depends(get_db)):
    _require(actor, UserRole.ADMIN)
    if session.get(M03ReferenceTemplate, template_id) is None: raise _error("template_not_found", "The baseline template was not found.", status.HTTP_404_NOT_FOUND)
    return [{"id": row.id, "reference_template_id": row.reference_template_id, "rule_key": row.rule_key, "rule_value": row.rule_value, "rule_version": row.rule_version, "content_hash": row.content_hash, "source": row.source, "provenance": row.provenance, "confidence": row.confidence, "created_at": row.created_at} for row in session.scalars(select(M03TemplateRule).where(M03TemplateRule.reference_template_id == template_id).order_by(M03TemplateRule.rule_version, M03TemplateRule.id)).all()]


@router.post("/admin/templates/{template_id}/metadata-version", status_code=status.HTTP_201_CREATED)
def create_metadata_version(template_id: int, payload: MetadataVersionWrite, request: Request, actor: User = Depends(_actor), session: Session = Depends(get_db)):
    _require(actor, UserRole.ADMIN); validate_mutating_origin(request)
    source = session.get(M03ReferenceTemplate, template_id)
    if source is None:
        raise _error("template_not_found", "The baseline template was not found.", status.HTTP_404_NOT_FOUND)
    if payload.template_metadata == source.template_metadata and not payload.confirm_duplicate:
        raise _error("duplicate_metadata_version", "Metadata is unchanged. Confirm explicitly to create a duplicate version.", status.HTTP_409_CONFLICT)
    version = next_template_version(session, source.template_type)
    row = M03ReferenceTemplate(template_type=source.template_type, filename=source.filename, storage_key=f"module-03/templates/{source.template_type.lower()}/v{version}-{source.filename}", sha256=source.sha256, mime_type=source.mime_type, file_size=source.file_size, content=source.content, version=version, version_kind="METADATA", parent_template_id=source.id, template_metadata=payload.template_metadata, provenance=payload.provenance, extraction_status=source.extraction_status, extracted_rules=source.extracted_rules, extraction_warnings=source.extraction_warnings, confidence=source.confidence, uploaded_by_user_id=str(actor.id), is_active=False)
    session.add(row); session.flush(); save_rules(session, row, provenance=payload.provenance); _audit(session, actor, "module03_template_metadata_version_created", str(row.id), {"template_type": row.template_type, "version": row.version, "version_kind": row.version_kind, "provenance": payload.provenance}); session.commit(); session.refresh(row)
    return _template_out(row)


@router.post("/admin/templates/{template_id}/rule-version", status_code=status.HTTP_201_CREATED)
def create_rule_version(template_id: int, payload: RuleVersionWrite, request: Request, actor: User = Depends(_actor), session: Session = Depends(get_db)):
    _require(actor, UserRole.ADMIN); validate_mutating_origin(request)
    row = session.get(M03ReferenceTemplate, template_id)
    if row is None:
        raise _error("template_not_found", "The baseline template was not found.", status.HTTP_404_NOT_FOUND)
    if payload.rules is not None:
        row.extracted_rules = payload.rules
    next_version = latest_rule_version(session, row.id) + 1
    content_hash = rule_content_hash(row.extracted_rules)
    duplicate = session.scalar(select(M03TemplateRule.id).where(M03TemplateRule.reference_template_id == row.id, M03TemplateRule.content_hash == content_hash))
    if duplicate is not None and not payload.confirm_duplicate:
        raise _error("duplicate_rule_version", "Formatting rules are unchanged. Confirm explicitly to create a duplicate version.", status.HTTP_409_CONFLICT)
    rule_version, created = save_rules(session, row, rule_version=next_version, provenance=payload.provenance, confirm_duplicate=True)
    _audit(session, actor, "module03_template_rule_version_created", str(row.id), {"template_type": row.template_type, "rule_version": rule_version, "provenance": payload.provenance, "created": created})
    session.commit(); session.refresh(row)
    return {"template": _template_out(row), "rule_version": rule_version, "created": created, "provenance": payload.provenance}


@router.post("/student/proposals/upload", status_code=status.HTTP_201_CREATED)
async def upload_proposal(request: Request, proposal_type: str = Form(...), document: UploadFile = File(...), actor: User = Depends(_actor), session: Session = Depends(get_db)):
    _require(actor, UserRole.STUDENT); validate_mutating_origin(request); proposal_type = proposal_type.strip().upper()
    if proposal_type not in {M03ProposalType.SHORT.value, M03ProposalType.LONG.value}: raise _error("invalid_proposal_type", "Proposal type must be SHORT or LONG.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    baseline = active_template(session, proposal_type)
    if baseline is None: raise _error("active_baseline_missing", "An active Admin baseline is required for this proposal type.")
    content = await document.read(); filename = _validate_upload(document, content); ast = parse_document(content, filename, document.content_type); proposal_id = str(uuid4())
    row = M03ProposalDocument(proposal_id=proposal_id, proposal_type=proposal_type, owner_user_id=str(actor.id), filename=filename, storage_key=f"module-03/proposals/{proposal_id}/v1-{filename}", sha256=hashlib.sha256(content).hexdigest(), mime_type=document.content_type or "application/octet-stream", file_size=len(content), content=content, version=1, extraction_status=M03ExtractionStatus.EXTRACTED.value if ast.get("pages") or ast.get("paragraphs") else M03ExtractionStatus.FAILED.value, ast=ast, extraction_warnings=ast.get("warnings", []))
    session.add(row); session.flush(); _audit(session, actor, "module03_proposal_uploaded", proposal_id, {"proposal_type": proposal_type, "version": 1, "sha256": row.sha256}); session.commit(); session.refresh(row); return _proposal_out(row)


def _run_report(session: Session, proposal: M03ProposalDocument, actor: User) -> M03ComplianceReport:
    baseline = active_template(session, proposal.proposal_type)
    if baseline is None: raise _error("active_baseline_missing", "The active baseline for this proposal no longer exists.")
    check_1 = run_visual_check(proposal.ast, baseline.extracted_rules); check_2 = run_structural_check(proposal.ast, baseline.extracted_rules); check_3 = asyncio.run(run_semantic_check(proposal.ast)); aggregate = aggregate_report(proposal.proposal_type, _template_out(baseline), _proposal_out(proposal), check_1, check_2, check_3)
    report_version = int(session.scalar(select(func.max(M03ComplianceReport.report_version)).where(M03ComplianceReport.proposal_id == proposal.proposal_id)) or 0) + 1; report_id = str(uuid4())
    report = M03ComplianceReport(report_id=report_id, proposal_id=proposal.proposal_id, proposal_document_id=str(proposal.id), baseline_template_id=str(baseline.id), proposal_type=proposal.proposal_type, report_version=report_version, status=aggregate["status"], check_1=check_1, check_2=check_2, check_3=check_3, severity_counts=aggregate["severity_counts"], remediation=aggregate["remediation"], advisory_summary=aggregate["advisory_summary"], runtime_metadata=aggregate["runtime_metadata"], generated_by_user_id=str(actor.id))
    session.add(report); session.flush()
    for finding in list(check_1.get("findings", [])) + list(check_2.get("findings", [])):
        session.add(M03ComplianceFinding(report_id=report_id, check_name=finding["check_name"], severity=finding["severity"], rule_reference=finding["rule_reference"], student_value=finding.get("student_value") if isinstance(finding.get("student_value"), dict) else {"value": finding.get("student_value")}, baseline_value=finding.get("baseline_value") if isinstance(finding.get("baseline_value"), dict) else {"value": finding.get("baseline_value")}, evidence=finding.get("evidence", {}), remediation=finding.get("remediation", ""), confidence=finding.get("confidence", "UNKNOWN")))
    for name, result in (("CHECK_1_VISUAL", check_1), ("CHECK_2_STRUCTURAL", check_2), ("CHECK_3_SEMANTIC_LLM", check_3)):
        session.add(M03CheckRun(proposal_id=proposal.proposal_id, report_id=report_id, check_name=name, status=result.get("status", "UNKNOWN"), runtime=str(result.get("runtime", "deterministic")), model=result.get("model"), result=result))
    _audit(session, actor, "module03_compliance_report_generated", report_id, {"proposal_id": proposal.proposal_id, "report_version": report_version, "status": report.status}); session.commit(); session.refresh(report); return report


@router.post("/student/proposals/{proposal_id}/audit", response_model=ReportOut)
def audit_proposal(proposal_id: str, actor: User = Depends(_actor), session: Session = Depends(get_db)):
    proposal = _authorized_proposal(session, proposal_id, _require(actor, UserRole.STUDENT)); return _report_out(_run_report(session, proposal, actor))


@router.get("/student/proposals/{proposal_id}/reports", response_model=list[ReportOut])
def student_reports(proposal_id: str, actor: User = Depends(_actor), session: Session = Depends(get_db)):
    proposal = _authorized_proposal(session, proposal_id, _require(actor, *READ_ROLES)); return [_report_out(row) for row in session.scalars(select(M03ComplianceReport).where(M03ComplianceReport.proposal_id == proposal.proposal_id).order_by(M03ComplianceReport.report_version.desc())).all()]


@router.get("/student/proposals/{proposal_id}/reports/{report_id}", response_model=ReportOut)
def student_report(proposal_id: str, report_id: str, actor: User = Depends(_actor), session: Session = Depends(get_db)):
    _authorized_proposal(session, proposal_id, _require(actor, *READ_ROLES)); row = session.scalar(select(M03ComplianceReport).where(M03ComplianceReport.proposal_id == proposal_id, M03ComplianceReport.report_id == report_id))
    if row is None: raise _error("report_not_found", "The compliance report was not found.", status.HTTP_404_NOT_FOUND)
    return _report_out(row)


@router.get("/supervisor/proposals/{proposal_id}/reports/{report_id}", response_model=ReportOut)
def supervisor_report(proposal_id: str, report_id: str, actor: User = Depends(_actor), session: Session = Depends(get_db)):
    _authorized_proposal(session, proposal_id, _require(actor, UserRole.SUPERVISOR, UserRole.ADMIN)); row = session.scalar(select(M03ComplianceReport).where(M03ComplianceReport.proposal_id == proposal_id, M03ComplianceReport.report_id == report_id))
    if row is None: raise _error("report_not_found", "The compliance report was not found.", status.HTTP_404_NOT_FOUND)
    return _report_out(row)


@router.get("/supervisor/proposals/{proposal_id}/reports", response_model=list[ReportOut])
def supervisor_reports(proposal_id: str, actor: User = Depends(_actor), session: Session = Depends(get_db)):
    proposal = _authorized_proposal(session, proposal_id, _require(actor, UserRole.SUPERVISOR, UserRole.ADMIN))
    rows = session.scalars(select(M03ComplianceReport).where(M03ComplianceReport.proposal_id == proposal.proposal_id).order_by(M03ComplianceReport.report_version.desc())).all()
    return [_report_out(row) for row in rows]


@router.get("/coordinator/proposals/{proposal_id}/reports/{report_id}", response_model=ReportOut)
def coordinator_report(proposal_id: str, report_id: str, actor: User = Depends(_actor), session: Session = Depends(get_db)):
    _authorized_proposal(session, proposal_id, _require(actor, UserRole.COORDINATOR, UserRole.ADMIN)); row = session.scalar(select(M03ComplianceReport).where(M03ComplianceReport.proposal_id == proposal_id, M03ComplianceReport.report_id == report_id))
    if row is None: raise _error("report_not_found", "The compliance report was not found.", status.HTTP_404_NOT_FOUND)
    return _report_out(row)


@router.get("/coordinator/proposals/{proposal_id}/reports", response_model=list[ReportOut])
def coordinator_reports(proposal_id: str, actor: User = Depends(_actor), session: Session = Depends(get_db)):
    proposal = _authorized_proposal(session, proposal_id, _require(actor, UserRole.COORDINATOR, UserRole.ADMIN))
    rows = session.scalars(select(M03ComplianceReport).where(M03ComplianceReport.proposal_id == proposal.proposal_id).order_by(M03ComplianceReport.report_version.desc())).all()
    return [_report_out(row) for row in rows]
