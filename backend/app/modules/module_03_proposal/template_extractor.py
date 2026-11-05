"""Deterministic extraction of measurable template rules."""

from __future__ import annotations

import re
from typing import Any

from ...pdf_extraction import PdfExtractionError, extract_proposal_document


_NUMBERED_HEADING = re.compile(r"^(?:chapter\s+\d+|\d+(?:\.\d+)*[.)]?)\s+(.+)$", re.IGNORECASE)
_UPPER_HEADING = re.compile(r"^[A-Z][A-Z\s&:/()\-]{4,}$")


def _sections(text: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current_page = 1
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        page_match = re.match(r"\[PAGE\s+(\d+)\]", line, re.IGNORECASE)
        if page_match:
            current_page = int(page_match.group(1))
            continue
        if not line or len(line) > 140 or line.endswith((".", ",", ";")):
            continue
        numbered = _NUMBERED_HEADING.match(line)
        is_heading = bool(numbered or _UPPER_HEADING.match(line))
        if not is_heading:
            continue
        name = line.strip()
        key = re.sub(r"\s+", " ", name.casefold())
        if key in seen:
            continue
        seen.add(key)
        level = 1 if re.match(r"^(?:chapter\s+\d+|\d+\.?\s)", line, re.IGNORECASE) else 2
        sections.append({"name": name, "page": current_page, "level": level})
    return sections[:100]


def extract_template_rules(data: bytes, content_type: str | None, filename: str | None) -> dict[str, Any]:
    """Return only rules exposed by the uploaded template representation."""
    extracted = extract_proposal_document(data, content_type, filename)
    fields = extracted.extracted_fields
    headings = _sections(extracted.extracted_text)
    rules: dict[str, Any] = {
        "page_count": extracted.page_count,
        "required_sections": [item["name"] for item in headings],
        "section_sequence": [item["name"] for item in headings],
        "detected_headings": headings,
        "source": {
            "filename": filename or "uploaded-template",
            "content_type": extracted.content_type,
            "extraction_runtime": "deterministic-local",
            "warnings": list(fields.get("warnings", [])),
        },
    }
    measurable = (
        "page_size", "margin_mm", "right_margin_mm", "top_margin_mm", "bottom_margin_mm",
        "font_family", "font_size_pt", "line_spacing", "table_count", "figure_count", "page_numbering",
    )
    for name in measurable:
        if name in fields and fields[name] is not None:
            rules[name] = fields[name]
    if not headings:
        rules["required_sections"] = []
        rules["section_sequence"] = []
        rules["source"]["warnings"] = [*rules["source"]["warnings"], "No reliably formatted headings were detected."]
    return rules


__all__ = ["PdfExtractionError", "extract_template_rules"]
