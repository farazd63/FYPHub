"""Dynamic baseline extraction; values come only from the uploaded document."""

from __future__ import annotations

from collections import Counter
from typing import Any


REQUIRED_HEADINGS = ("Introduction", "Problem Statement", "Objectives", "Scope", "Methodology", "Expected Outcomes", "References")
REQUIRED_FORMATTING = (
    ("margins", "Margins"),
    ("default_font_family", "Font family"),
    ("default_font_size_pt", "Font size"),
    ("line_spacing", "Line spacing"),
    ("paragraph_spacing", "Paragraph spacing"),
)


def _heading_name(text: str) -> str:
    value = " ".join(str(text or "").split())
    value = value.split(":", 1)[0].strip(" .-_")
    value = __import__("re").sub(r"^\d+(?:\.\d+)*[.)]?\s*", "", value)
    return value


def _field_from_headings(headings: list[dict[str, Any]], aliases: tuple[str, ...]) -> str:
    for heading in headings:
        name = _heading_name(heading.get("text"))
        if any(alias in name.casefold() for alias in aliases):
            return str(heading.get("text"))
    return "Not specified in reference template"


def _rule_source(value: Any) -> str:
    return "Observed reference property" if value not in (None, "unknown", [], {}) else "Observed reference property"


def _missing_value(value: Any) -> bool:
    if value is None or value == "unknown" or value == "Not detected in reference template":
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, dict):
        return not value or all(_missing_value(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return not value
    return False


def extract_baseline_rules(ast: dict[str, Any]) -> dict[str, Any]:
    paragraphs = ast.get("paragraphs", [])
    headings = ast.get("headings", [])
    sizes = [item.get("font_size") for item in paragraphs if isinstance(item.get("font_size"), (int, float))]
    families = [item.get("font_family") for item in paragraphs if item.get("font_family")]
    heading_order = [{"text": item.get("text"), "level": item.get("level"), "page": item.get("page")} for item in headings]
    heading_names = [_heading_name(item.get("text")) for item in headings if item.get("text")]
    missing = [name for name in REQUIRED_HEADINGS if not any(name.casefold() in candidate.casefold() for candidate in heading_names)]
    warnings = [item for item in ast.get("warnings", []) if isinstance(item, dict) and item.get("code") not in {"pymupdf_unavailable"}]
    structural_available = bool(ast.get("pages") or ast.get("paragraphs") or ast.get("headings"))
    if not structural_available:
        warnings.append({"code": "structural_baseline_insufficient", "message": "The reference template did not contain readable structural or formatting information."})
    if missing:
        warnings.append({"code": "required_structural_fields_missing", "message": f"Important template sections were not detected: {', '.join(missing)}."})
    if not ast.get("paragraphs") or not headings:
        warnings.append({"code": "incomplete_official_template", "message": "This file does not appear to be a complete structured official template. Upload the approved university template PDF or DOCX."})
    rules: dict[str, Any] = {
        "page_geometry": {"pages": [{key: page.get(key) for key in ("page", "width", "height")} for page in ast.get("pages", [])]},
        "margins": ast.get("margins", "unknown"),
        "default_font_family": Counter(families).most_common(1)[0][0] if families else "unknown",
        "default_font_size_pt": Counter(sizes).most_common(1)[0][0] if sizes else "unknown",
        "heading_hierarchy": heading_order,
        "heading_order": [item.get("text") for item in headings],
        "paragraph_spacing": ast.get("paragraph_spacing", next((item.get("paragraph_spacing") for item in paragraphs if item.get("paragraph_spacing") is not None), "unknown")),
        "line_spacing": ast.get("line_spacing", next((item.get("line_spacing") for item in paragraphs if item.get("line_spacing") is not None), "unknown")),
        "expected_sections": [item.get("text") for item in headings if item.get("text")],
        "heading_style": "Numbered bold headings" if any(item.get("bold") for item in paragraphs if item.get("text") in [heading.get("text") for heading in headings]) else "unknown",
        "optional_sections": [],
        "word_count_bounds": {},
        "caption_style": "Detected figure/table captions" if ast.get("captions") else "Not detected in reference template",
        "citation_patterns": ast.get("citations", []),
        "reference_template_fields": {
            "purpose": _field_from_headings(headings, ("purpose",)),
            "problem_statement": _field_from_headings(headings, ("problem statement",)),
            "objectives": _field_from_headings(headings, ("objectives",)),
            "methodology": _field_from_headings(headings, ("methodology", "method")),
            "expected_outcomes": _field_from_headings(headings, ("expected outcomes", "outcomes")),
        },
        "structural_baseline_available": structural_available,
        "structural_baseline_status": "Available" if structural_available and not missing else "Incomplete",
        "provenance": {"formatting": _rule_source(ast.get("margins")), "structure": _rule_source(headings), "requirements": "Observed reference property"},
    }
    missing_fields = [f"Expected section: {name}" for name in missing]
    required_positions = []
    for required in REQUIRED_HEADINGS:
        position = next((index for index, heading in enumerate(heading_names) if required.casefold() in heading.casefold()), None)
        if position is not None:
            required_positions.append(position)
    if _missing_value(rules["heading_order"]) or (len(required_positions) == len(REQUIRED_HEADINGS) and required_positions != sorted(required_positions)):
        missing_fields.append("Heading order")
    if _missing_value(rules["heading_hierarchy"]) or any(item.get("level") is None for item in rules["heading_hierarchy"]):
        missing_fields.append("Heading hierarchy")
    for key, label in REQUIRED_FORMATTING:
        value = rules.get(key)
        if key == "margins" and isinstance(value, dict):
            value = value if all(side in value and not _missing_value(value.get(side)) for side in ("left_mm", "right_mm", "top_mm", "bottom_mm")) else "unknown"
        if _missing_value(value):
            missing_fields.append(label)
    rules["missing_fields"] = missing_fields
    rules["baseline_status"] = "COMPLETE" if rules["structural_baseline_available"] and not missing_fields and not warnings else "INCOMPLETE"
    if missing_fields and not any(item.get("code") == "incomplete_structural_baseline" for item in warnings):
        warnings.append({"code": "incomplete_structural_baseline", "message": f"Baseline activation requires review of: {', '.join(missing_fields)}."})
    confidence = "HIGH" if rules["structural_baseline_available"] and not missing_fields and not warnings else "MEDIUM" if rules["structural_baseline_available"] else "LOW"
    return {"rules": rules, "warnings": warnings, "confidence": confidence}
