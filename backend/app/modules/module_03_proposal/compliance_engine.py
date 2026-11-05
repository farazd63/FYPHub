"""Deterministic comparison between a submission and an active template."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _same(expected: Any, actual: Any) -> bool:
    if isinstance(expected, bool):
        return expected == bool(actual)
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) < 0.05
    return _text(expected).casefold() == _text(actual).casefold()


def _status(expected: Any, actual: Any) -> tuple[str, str | None]:
    if expected is None:
        return "UNVERIFIABLE", "The active template does not expose a measurable value for this requirement."
    if actual is None or actual == "":
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


def build_compliance_report(*, submission: Any, rules: dict[str, Any], previous_versions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    actual = submission.extracted_fields or {}
    checks: list[dict[str, Any]] = []
    category_items: dict[str, list[dict[str, Any]]] = {}
    violations: list[dict[str, Any]] = []

    fields = (
        ("Page Layout", "page_size", "Page Size"),
        ("Page Layout", "margin_mm", "Left Margin"),
        ("Page Layout", "right_margin_mm", "Right Margin"),
        ("Page Layout", "top_margin_mm", "Top Margin"),
        ("Page Layout", "bottom_margin_mm", "Bottom Margin"),
        ("Font Formatting", "font_family", "Font Family"),
        ("Font Formatting", "font_size_pt", "Font Size"),
        ("Paragraph Formatting", "line_spacing", "Line Spacing"),
        ("Headers and Footers", "page_numbering", "Page Numbering"),
        ("Tables and Figures", "table_count", "Table Count"),
        ("Tables and Figures", "figure_count", "Figure Count"),
    )
    for category, key, label in fields:
        if key not in rules:
            continue
        expected = rules.get(key)
        detected = actual.get(key)
        status, evidence = _status(expected, detected)
        item = {"id": f"{category.lower().replace(' ', '-')}-{key}", "name": label, "category": category, "status": status, "expected": expected, "actual": detected, "difference": (round(abs(float(expected) - float(detected)), 2) if isinstance(expected, (int, float)) and isinstance(detected, (int, float)) else None), "location": {"scope": "document", "page": 1}, "evidence": evidence or ""}
        checks.append(item)
        category_items.setdefault(category, []).append(item)
        if status == "FAIL":
            violations.append(_violation(item, len(violations) + 1, category))

    actual_sections = [str(item.get("name", "")) for item in actual.get("detected_headings", []) if item.get("name")]
    expected_sections = [str(item) for item in rules.get("required_sections", []) if str(item).strip()]
    section_results: list[dict[str, Any]] = []
    missing_sections: list[dict[str, str]] = []
    for index, expected in enumerate(expected_sections):
        match = _similar_section(expected, actual_sections)
        presence = "PASS" if match else "FAIL"
        order = "PASS" if match and index < len(actual_sections) and _text(actual_sections[index]).casefold() == _text(match).casefold() else "PARTIAL" if match else "FAIL"
        section_results.append({"name": expected, "check1": _pill(presence), "check2": _pill(order), "detected": match, "expected_order": index + 1, "detected_order": (actual_sections.index(match) + 1 if match in actual_sections else None)})
        if not match:
            missing_sections.append({"issue": "Missing Section", "details": expected})
            item = {"id": f"structure-{index + 1}", "name": f"Missing section: {expected}", "category": "Document Structure", "status": "FAIL", "expected": expected, "actual": None, "difference": None, "location": {"scope": "document", "page": None}, "evidence": "The required section was not detected in the uploaded proposal."}
            checks.append(item)
            category_items.setdefault("Document Structure", []).append(item)
            violations.append(_violation(item, len(violations) + 1, "Document Structure"))
    if expected_sections and actual_sections:
        ordered = [item for item in actual_sections if item in expected_sections]
        if ordered != [item for item in expected_sections if item in actual_sections]:
            missing_sections.append({"issue": "Incorrect Sequence", "details": "Detected sections are not in the active template order."})
            item = {"id": "sequence-order", "name": "Section Sequence", "category": "Section Sequence", "status": "FAIL", "expected": expected_sections, "actual": actual_sections, "difference": None, "location": {"scope": "document", "page": None}, "evidence": "The detected section order differs from the active university template."}
            checks.append(item)
            category_items.setdefault("Section Sequence", []).append(item)
            violations.append(_violation(item, len(violations) + 1, "Section Sequence"))
        else:
            item = {"id": "sequence-order", "name": "Section Sequence", "category": "Section Sequence", "status": "PASS", "expected": expected_sections, "actual": actual_sections, "difference": None, "location": {"scope": "document", "page": None}, "evidence": "The detected sections follow the active template order."}
            checks.append(item)
            category_items.setdefault("Section Sequence", []).append(item)

    categories = [{"name": category, "status": _category_status(items), "detail": _category_detail(items), "checks": items} for category, items in category_items.items()]
    passed = sum(item["status"] == "PASS" for item in checks)
    failed = sum(item["status"] == "FAIL" for item in checks)
    partial = sum(item["status"] in {"PARTIAL", "UNVERIFIABLE"} for item in checks)
    total = len(checks)
    score = round((passed / total) * 100) if total else 0
    report_status = "Compliant" if total and failed == 0 and partial == 0 else "Not Compliant" if failed else "Review Required"
    return {
        "reportSummary": {"score": score, "status": report_status, "totalIssues": failed + partial, "metrics": {"passed": passed, "failed": failed, "partial": partial, "total": total}},
        "categories": categories,
        "sectionCompliance": section_results,
        "violations": violations,
        "missingSections": missing_sections,
        "finalResults": {"totalChecks": total, "passed": passed, "failed": failed, "partial": partial, "totalViolations": len(violations), "severityBreakdown": {"major": sum(v["severity"] == "Major" for v in violations), "minor": sum(v["severity"] == "Minor" for v in violations), "info": sum(v["severity"] == "Info" for v in violations)}},
        "document": {"filename": submission.filename, "pageCount": submission.page_count, "previewText": submission.extracted_text[:800], "selectedPage": 1},
        "proposal": {"id": submission.id, "proposalKey": submission.proposal_key, "title": submission.title, "type": submission.proposal_type, "version": submission.version, "processingStatus": submission.processing_status},
        "template": {"versionId": getattr(submission, "template_reference_version_id", None), "rules": rules},
        "versionHistory": previous_versions or [],
        "engine": {"name": "FYPHub deterministic compliance engine", "source": "PYTHON", "advisory": False},
    }


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
    page = item.get("location", {}).get("page")
    location = "Document" if page is None else f"Page {page}"
    return {"id": f"V-{number:03d}", "severity": severity, "title": item["name"], "status": "Non-Compliant", "location": location, "requirement": item.get("expected"), "detected": item.get("actual"), "difference": item.get("difference"), "evidence": item.get("evidence", ""), "affectedArea": location, "pageNumber": page}
