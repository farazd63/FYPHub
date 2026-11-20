"""Deterministic comparison between a submission and an active template."""

from __future__ import annotations

from difflib import SequenceMatcher
from datetime import datetime, timezone
import re
from typing import Any

from .report_summary import prepare_user_friendly_report


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _not_detected(value: Any) -> bool:
    return value is None or _text(value).casefold() in {"", "not detected", "not detected in pdf", "not detected in the provided report"}


def _document_pages(page_count: Any) -> list[int]:
    try:
        count = max(1, int(page_count))
    except (TypeError, ValueError):
        count = 1
    return list(range(1, count + 1))


def _format_number(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def _format_comparison_value(value: Any, *, label: str, template: bool = False) -> str:
    if _not_detected(value):
        return "Template rule not configured" if template else "Measurement not detected"
    if isinstance(value, bool):
        if label == "Page Numbering":
            return "Page number required on every page" if value else "Page number not required"
        return "Required" if value else "Not required"
    if label == "Page Count":
        return f"{_format_number(value)} page" if int(value) == 1 else f"{_format_number(value)} pages"
    if label in {"Left Margin", "Right Margin", "Top Margin", "Bottom Margin"}:
        return f"{_format_number(value)} mm"
    if isinstance(value, list):
        return " → ".join(_text(item) for item in value if _text(item)) or "No required sections configured"
    return _text(value)


def _page_range_label(pages: list[int]) -> str:
    normalized = sorted(set(pages))
    if len(normalized) == 1:
        return f"Page {normalized[0]}"
    if normalized == list(range(normalized[0], normalized[-1] + 1)):
        return f"Pages {normalized[0]}-{normalized[-1]}"
    return "Pages " + ", ".join(str(page) for page in normalized)


def _required_action(label: str, expected: Any, status: str) -> str:
    if status == "PASS":
        return "No action required."
    if label == "Page Count":
        return f"Submit exactly {_format_comparison_value(expected, label=label, template=True)}."
    if label == "Page Size":
        return f"Convert the document to {_format_comparison_value(expected, label=label, template=True)}."
    if label == "Page Orientation":
        return f"Set the document orientation to {_format_comparison_value(expected, label=label, template=True)}."
    if label == "Page Numbering":
        return "Add the correct page number to every affected page."
    if label == "Template Structure" or label == "Section Sequence":
        return "Use the university template without changing its structure."
    if label.startswith("Missing section"):
        return f"Add the required section: {label.split(':', 1)[-1].strip()}."
    if label in {"Left Margin", "Right Margin", "Top Margin", "Bottom Margin"}:
        return "Match the approved template margin."
    if expected is None or expected == "":
        return "Provide a document format that allows this requirement to be checked."
    return f"Update the document to match the approved template {label.lower()} rule."


def _issue_severity(item: dict[str, Any]) -> str:
    if item.get("status") == "PASS":
        return "passed"
    strict_labels = {
        "Page Count", "Page Size", "Page Orientation", "Left Margin", "Right Margin",
        "Top Margin", "Bottom Margin", "Page Numbering", "Template Structure", "Section Sequence",
    }
    strict_categories = {"Document Structure", "Section Sequence", "Template Structure"}
    return "critical" if item.get("name") in strict_labels or item.get("category") in strict_categories or str(item.get("name", "")).startswith("Missing section") else "warning"


def _difference_text(item: dict[str, Any]) -> str:
    status = item.get("status")
    if status == "PASS":
        return "Matches the approved university template."
    expected = item.get("expected")
    actual = item.get("actual")
    label = str(item.get("name", "Issue"))
    if status in {"PARTIAL", "UNVERIFIABLE"}:
        return "Evidence was insufficient to verify this requirement."
    if expected is None or actual is None or expected == "" or actual == "":
        return "The required value or section was not found in the uploaded document."
    if isinstance(expected, bool) and isinstance(actual, bool):
        if label == "Page Numbering":
            return "Page numbering requirement violated"
        return "Requirement does not match the approved template."
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        delta = round(float(actual) - float(expected), 2)
        sign = "+" if delta > 0 else ""
        unit = " pages" if label == "Page Count" else " mm" if "Margin" in label else ""
        suffix = " — page limit violated" if label == "Page Count" and delta > 0 else ""
        return f"{sign}{_format_number(delta)}{unit}{suffix}"
    if label == "Page Size":
        return "Wrong page size"
    if label == "Page Orientation":
        return "Wrong page orientation"
    if label == "Page Numbering":
        return "Page numbering requirement violated"
    if label in {"Template Structure", "Section Sequence"} or label.startswith("Missing section"):
        return "Required template structure not followed"
    return "Does not match the approved university template."


def _clean_issue(item: dict[str, Any], page_count: int, *, affected_pages: list[int] | None = None) -> dict[str, Any]:
    pages = sorted(set(affected_pages or _document_pages(page_count))) or [1]
    label = str(item.get("name") or "Compliance requirement")
    status = str(item.get("status") or "UNVERIFIABLE")
    severity = _issue_severity(item)
    actual = item.get("actual")
    if status in {"PARTIAL", "UNVERIFIABLE"}:
        student_document = "Could not verify from the uploaded document"
    elif _not_detected(actual):
        student_document = "Not found in the uploaded document"
    else:
        student_document = _format_comparison_value(actual, label=label)
    if label == "Page Numbering" and status != "PASS":
        student_document = f"Page number missing on {_page_range_label(pages)}"
    status_label = {"PASS": "Passed", "FAIL": "Failed", "PARTIAL": "Verify", "UNVERIFIABLE": "Verify"}.get(status, "Verify")
    priority = "High" if status == "FAIL" and severity == "critical" else "Medium"
    return {
        "id": str(item.get("id") or label.lower().replace(" ", "-")),
        "category": str(item.get("category") or "Template Compliance"),
        "severity": severity,
        "issue": label,
        "originalTemplate": _format_comparison_value(item.get("expected"), label=label, template=True),
        "studentDocument": student_document,
        "difference": _difference_text(item),
        "affectedPages": pages,
        "requiredAction": _required_action(label, item.get("expected"), status),
        "status": "passed" if status == "PASS" else "failed" if status == "FAIL" else "warning",
        "statusCode": status,
        "statusLabel": status_label,
        "priority": priority,
        "evidence": item.get("evidence", "") or "Evidence was not recorded for this check.",
    }


def build_document_difference_issues(checks: list[dict[str, Any]], page_count: int) -> list[dict[str, Any]]:
    """Map internal checks to the student-facing six-field comparison contract."""
    all_pages = _document_pages(page_count)
    clean: list[dict[str, Any]] = []
    for item in checks:
        location = item.get("location") if isinstance(item.get("location"), dict) else {}
        page = location.get("page")
        label = str(item.get("name") or "")
        document_wide = label in {"Page Count", "Page Size", "Page Orientation", "Page Numbering", "Template Structure", "Section Sequence"} or str(item.get("category")) in {"Document Structure", "Template Structure", "Section Sequence"}
        if label == "Page Numbering" and isinstance(location.get("page_numbering_pages"), list):
            numbered_pages = {int(value) for value in location["page_numbering_pages"] if isinstance(value, int) and value > 0}
            pages = [value for value in all_pages if value not in numbered_pages] or all_pages
        else:
            pages = all_pages if document_wide or not isinstance(page, int) or page < 1 else [int(page)]
        clean.append(_clean_issue(item, page_count, affected_pages=pages))
    return clean


def _same(expected: Any, actual: Any) -> bool:
    if isinstance(expected, bool):
        return expected == bool(actual)
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) < 0.05
    return _text(expected).casefold() == _text(actual).casefold()


def _status(expected: Any, actual: Any) -> tuple[str, str | None]:
    if _not_detected(expected):
        return "UNVERIFIABLE", "The active template does not expose a measurable value for this requirement."
    if _not_detected(actual):
        return "UNVERIFIABLE", "The uploaded document does not expose a measurable value for this requirement."
    return ("PASS", "The detected document value matches the active university template.") if _same(expected, actual) else ("FAIL", "The detected document value does not match the active template requirement.")


def _category_status(items: list[dict[str, Any]]) -> str:
    statuses = {item["status"] for item in items}
    if "FAIL" in statuses:
        return "FAIL"
    if "UNVERIFIABLE" in statuses or "PARTIAL" in statuses:
        return "PARTIAL"
    return "PASS"


def _similar_section(expected: str, actual_sections: list[str]) -> str | None:
    expected_key = _text(expected).casefold()
    best = max(actual_sections, key=lambda item: SequenceMatcher(None, expected_key, _text(item).casefold()).ratio(), default=None)
    if best and SequenceMatcher(None, expected_key, _text(best).casefold()).ratio() >= 0.82:
        return best
    return None


def _field_value(fields: dict[str, Any], name: str) -> str:
    value = fields.get(name)
    if isinstance(value, dict):
        value = value.get("value")
    return _text(value)


def _tokens(value: str) -> set[str]:
    stop_words = {"about", "after", "also", "and", "are", "because", "been", "being", "between", "from", "have", "into", "more", "that", "their", "there", "these", "they", "this", "through", "with", "will", "would"}
    return {token for token in re.findall(r"[a-z0-9]{4,}", value.casefold()) if token not in stop_words}


def _consistency_item(name: str, left_name: str, right_name: str, left: str, right: str) -> dict[str, Any]:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    overlap = len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))
    if not left or not right:
        status = "UNVERIFIABLE"
        evidence = f"{left_name} or {right_name} was not detected."
    elif overlap >= 0.2:
        status = "PASS"
        evidence = f"{round(overlap * 100)}% of the smaller vocabulary overlaps between {left_name} and {right_name}."
    elif overlap >= 0.08:
        status = "PARTIAL"
        evidence = f"Only {round(overlap * 100)}% of the smaller vocabulary overlaps between {left_name} and {right_name}."
    else:
        status = "FAIL"
        evidence = f"No meaningful vocabulary overlap was detected between {left_name} and {right_name}."
    return {
        "id": f"academic-consistency-{name}",
        "name": name,
        "category": "Academic Consistency",
        "status": status,
        "expected": f"{left_name} is aligned with {right_name}",
        "actual": round(overlap, 3) if left and right else None,
        "difference": None,
        "location": {"scope": "document", "page": 1, "document_level": True},
        "evidence": evidence,
    }


def build_change_summary(previous_fields: dict[str, Any] | None, current_fields: dict[str, Any] | None, previous_version: int, current_version: int) -> dict[str, Any]:
    """Produce a safe, auditable AI-style summary without sending proposal text externally."""
    before = previous_fields or {}
    after = current_fields or {}
    changed: list[str] = []
    for key in ("purpose", "objectives", "methodology", "scope", "proposed_solution", "expected_outcomes", "detected_headings"):
        before_value = before.get(key)
        after_value = after.get(key)
        if key != "detected_headings":
            before_value = before_value.get("value") if isinstance(before_value, dict) else before_value
            after_value = after_value.get("value") if isinstance(after_value, dict) else after_value
        if _text(before_value) != _text(after_value):
            changed.append(key.replace("_", " ").title())
    return {
        "source": "AI_ASSISTED_DETERMINISTIC",
        "model": "local-change-analyzer",
        "fromVersion": previous_version,
        "toVersion": current_version,
        "summary": "No substantive section changes detected." if not changed else f"Updated {', '.join(changed)}.",
        "changedSections": changed,
        "advisory": True,
    }


def build_compliance_report(*, submission: Any, rules: dict[str, Any], previous_versions: list[dict[str, Any]] | None = None, template_name: str | None = None) -> dict[str, Any]:
    actual = submission.extracted_fields or {}
    checks: list[dict[str, Any]] = []
    category_items: dict[str, list[dict[str, Any]]] = {}
    violations: list[dict[str, Any]] = []

    comparison_rules = dict(rules)
    if "left_margin_mm" not in comparison_rules and "margin_mm" in comparison_rules:
        comparison_rules["left_margin_mm"] = comparison_rules["margin_mm"]
    fields = (
        ("Page Layout", "page_size", "Page Size"),
        ("Page Layout", "left_margin_mm", "Left Margin"),
        ("Page Layout", "right_margin_mm", "Right Margin"),
        ("Page Layout", "top_margin_mm", "Top Margin"),
        ("Page Layout", "bottom_margin_mm", "Bottom Margin"),
        ("Font Formatting", "font_family", "Font Family"),
        ("Font Formatting", "font_size_pt", "Font Size"),
        ("Paragraph Formatting", "line_spacing", "Line Spacing"),
        ("Paragraph Formatting", "alignment", "Alignment"),
        ("Heading Styles", "heading_style", "Heading Style"),
        ("Headers and Footers", "page_numbering", "Page Numbering"),
    )
    for category, key, label in fields:
        if key not in comparison_rules or _not_detected(comparison_rules.get(key)):
            continue
        expected = comparison_rules.get(key)
        detected = actual.get(key)
        status, evidence = _status(expected, detected)
        location = {"scope": "document", "page": 1, "document_level": True}
        if key == "page_numbering":
            location["page_numbering_pages"] = actual.get("page_numbering_pages", [])
        item = {"id": f"{category.lower().replace(' ', '-')}-{key}", "name": label, "category": category, "status": status, "expected": expected, "actual": detected, "difference": (round(abs(float(expected) - float(detected)), 2) if isinstance(expected, (int, float)) and isinstance(detected, (int, float)) else None), "location": location, "evidence": evidence or ""}
        checks.append(item)
        category_items.setdefault(category, []).append(item)
        if status == "FAIL":
            violations.append(_violation(item, len(violations) + 1, category))

    actual_heading_rows = [item for item in actual.get("detected_headings", []) if item.get("name")]
    actual_sections = [str(item.get("name", "")) for item in actual_heading_rows]
    expected_sections = [str(item) for item in (comparison_rules.get("required_sections") or comparison_rules.get("section_sequence") or []) if str(item).strip()]
    section_results: list[dict[str, Any]] = []
    missing_sections: list[dict[str, str]] = []
    for index, expected in enumerate(expected_sections):
        match = _similar_section(expected, actual_sections)
        presence = "PASS" if match else "FAIL"
        order = "PASS" if match and index < len(actual_sections) and _text(actual_sections[index]).casefold() == _text(match).casefold() else "PARTIAL" if match else "REVIEW"
        matched_row = next((row for row in actual_heading_rows if str(row.get("name", "")) == match), None)
        detected_order = actual_sections.index(match) + 1 if match in actual_sections else None
        section_number = _section_number(match or expected, index + 1)
        section_results.append({"name": expected, "check1": _pill(presence), "check2": _pill(order), "detected": match, "expected_order": index + 1, "detected_order": detected_order, "page": matched_row.get("page") if matched_row else None, "sectionNumber": section_number})
        if not match:
            missing_sections.append({"issue": "Missing Section", "details": expected})
            item = {"id": f"structure-{index + 1}", "name": f"Missing section: {expected}", "category": "Document Structure", "status": "FAIL", "expected": expected, "actual": None, "difference": None, "location": {"scope": "document", "page": None, "section_number": _section_number(expected, index + 1), "section_name": expected}, "evidence": "The required section was not detected in the uploaded proposal."}
            checks.append(item)
            category_items.setdefault("Document Structure", []).append(item)
            violations.append(_violation(item, len(violations) + 1, "Document Structure"))
    if expected_sections and actual_sections:
        ordered = [item for item in actual_sections if item in expected_sections]
        if ordered != [item for item in expected_sections if item in actual_sections]:
            missing_sections.append({"issue": "Incorrect Sequence", "details": "Detected sections are not in the active template order."})
            item = {"id": "sequence-order", "name": "Section Sequence", "category": "Section Sequence", "status": "FAIL", "expected": expected_sections, "actual": actual_sections, "difference": None, "location": {"scope": "document", "page": actual_heading_rows[0].get("page") if actual_heading_rows else None, "section_number": "order", "section_name": "Required section sequence"}, "evidence": "The detected section order differs from the active university template."}
            checks.append(item)
            category_items.setdefault("Section Sequence", []).append(item)
        else:
            item = {"id": "sequence-order", "name": "Section Sequence", "category": "Section Sequence", "status": "PASS", "expected": expected_sections, "actual": actual_sections, "difference": None, "location": {"scope": "document", "page": 1, "document_level": True}, "evidence": "The detected sections follow the active university template order."}
            checks.append(item)
            category_items.setdefault("Section Sequence", []).append(item)
    # Optional structural rules let an administrator require references,
    # appendices, and captions without hard-coding a particular university format.
    structural_counts = (
        ("required_references", "reference_count", "References"),
        ("required_appendices", "appendix_count", "Appendices"),
        ("required_captions", "caption_count", "Captions"),
        ("required_tables", "table_count", "Tables"),
        ("required_figures", "figure_count", "Figures"),
    )
    for rule_key, actual_key, label in structural_counts:
        if rule_key not in comparison_rules or _not_detected(comparison_rules.get(rule_key)):
            continue
        expected = comparison_rules.get(rule_key)
        try:
            expected_number = int(expected)
        except (TypeError, ValueError):
            continue
        detected = actual.get(actual_key)
        status = "UNVERIFIABLE" if detected is None else "PASS" if int(detected) >= expected_number else "FAIL"
        item = {"id": f"structure-{actual_key}", "name": label, "category": "Document Structure", "status": status, "expected": expected_number, "actual": detected, "difference": None, "location": {"scope": "document", "page": 1, "document_level": True}, "evidence": f"At least {expected_number} {label.lower()} required."}
        checks.append(item)
        category_items.setdefault("Document Structure", []).append(item)
        if status == "FAIL":
            violations.append(_violation(item, len(violations) + 1, "Document Structure"))

    consistency_pairs = (
        ("Problem / Objectives", "problem_statement", "objectives"),
        ("Objectives / Methodology", "objectives", "methodology"),
        ("Problem / Proposed Solution", "purpose", "proposed_solution"),
        ("Objectives / Expected Outcomes", "objectives", "expected_outcomes"),
        ("Scope / Methodology", "scope", "methodology"),
    )
    for name, left_key, right_key in consistency_pairs:
        item = _consistency_item(name, left_key.replace("_", " ").title(), right_key.replace("_", " ").title(), _field_value(actual, left_key), _field_value(actual, right_key))
        checks.append(item)
        category_items.setdefault("Academic Consistency", []).append(item)
        if item["status"] == "FAIL":
            violations.append(_violation(item, len(violations) + 1, "Academic Consistency"))

    categories = [{"name": category, "status": _category_status(items), "detail": _category_detail(items), "checks": items} for category, items in category_items.items()]
    passed = sum(item["status"] == "PASS" for item in checks)
    failed = sum(item["status"] == "FAIL" for item in checks)
    partial = sum(item["status"] in {"PARTIAL", "UNVERIFIABLE"} for item in checks)
    total = len(checks)
    score = round((passed / total) * 100) if total else 0
    clean_issues = build_document_difference_issues(checks, submission.page_count)
    critical_issues = [item for item in clean_issues if item["severity"] == "critical" and item["status"] != "passed"]
    warning_issues = [item for item in clean_issues if item["severity"] == "warning" and item["status"] != "passed"]
    report_status = "Needs Major Corrections" if any(item["status"] == "failed" for item in critical_issues) else "Needs Corrections" if critical_issues or warning_issues else "Compliant"
    report = {
        "reportSummary": {"score": score, "status": report_status, "totalIssues": failed + partial, "metrics": {"passed": passed, "failed": failed, "partial": partial, "total": total}},
        "reportMetadata": {"reportVersion": "2.0", "templateName": template_name or f"{submission.proposal_type.title()} University Template", "analysisDate": datetime.now(timezone.utc).isoformat()},
        "documentDifferenceIssues": clean_issues,
        "categories": categories,
        "sectionCompliance": section_results,
        "violations": violations,
        "missingSections": missing_sections,
        "finalResults": {"totalChecks": total, "passed": passed, "failed": failed, "partial": partial, "totalViolations": len(violations), "severityBreakdown": {"major": sum(v["severity"] == "Major" for v in violations), "minor": sum(v["severity"] == "Minor" for v in violations), "info": sum(v["severity"] == "Info" for v in violations)}},
        "document": {"filename": submission.filename, "pageCount": submission.page_count, "previewText": submission.extracted_text[:800], "selectedPage": 1},
        "proposal": {"id": submission.id, "proposalKey": submission.proposal_key, "title": submission.title, "type": submission.proposal_type, "version": submission.version, "processingStatus": submission.processing_status},
        "template": {"versionId": getattr(submission, "template_reference_version_id", None), "title": template_name or f"{submission.proposal_type.title()} University Template", "rules": rules},
        "versionHistory": previous_versions or [],
        "academicConsistency": category_items.get("Academic Consistency", []),
        "engine": {"name": "FYPHub deterministic compliance engine", "source": "PYTHON", "advisory": False},
    }
    return prepare_user_friendly_report(report)


def _pill(value: str) -> str:
    return {"PASS": "Pass", "FAIL": "Fail", "PARTIAL": "Partial"}.get(value, "Review")


def _category_detail(items: list[dict[str, Any]]) -> str:
    failed = next((item for item in items if item["status"] == "FAIL"), None)
    if failed:
        return f"{failed['name']} does not match"
    partial = next((item for item in items if item["status"] in {"PARTIAL", "UNVERIFIABLE"}), None)
    return "Some values cannot be verified" if partial else "All configured checks pass"


def _violation(item: dict[str, Any], number: int, category: str) -> dict[str, Any]:
    severity = "Major" if category in {"Page Layout", "Document Structure", "Section Sequence"} else "Minor"
    location_data = item.get("location", {})
    page = location_data.get("page")
    section_number = location_data.get("section_number")
    section_name = location_data.get("section_name")
    if section_number:
        location = f"Page {page} · Section {section_number} · {section_name or item['name']}" if page else f"Page not detected · Section {section_number} · {section_name or item['name']}"
    elif location_data.get("document_level"):
        location = f"Page {page} · Document-level formatting"
    else:
        location = "Document"
    return {"id": f"V-{number:03d}", "severity": severity, "title": item["name"], "status": "Non-Compliant", "location": location, "requirement": item.get("expected"), "detected": item.get("actual"), "difference": item.get("difference"), "evidence": item.get("evidence", ""), "affectedArea": location, "pageNumber": page}


def _section_number(name: str, fallback: int) -> str:
    match = re.match(r"^\s*(?:chapter\s+)?(\d+(?:\.\d+)*)", _text(name), re.IGNORECASE)
    return match.group(1) if match else str(fallback)
