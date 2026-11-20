"""Deterministic extraction of official university-template rules.

The uploaded template is the only rules source. PDFs are read with PyMuPDF,
DOCX files with python-docx, and OCR is attempted only when a PDF has no
extractable text. No model or sample-content heuristics are used to invent
rules.
"""

from __future__ import annotations

import io
import re
from collections import Counter
from statistics import median
from typing import Any, Iterable

from docx import Document

from ...pdf_extraction import PdfExtractionError


NOT_DETECTED = "Not detected"
MAIN_RULE_KEYS = (
    "page_size",
    "top_margin_mm",
    "bottom_margin_mm",
    "left_margin_mm",
    "right_margin_mm",
    "font_family",
    "font_size_pt",
    "line_spacing",
    "alignment",
    "heading_style",
    "page_numbering",
)
OPTIONAL_REQUIREMENT_KEYS = (
    "required_references",
    "required_captions",
    "required_tables",
    "required_figures",
    "required_appendices",
)

_NUMBERED_HEADING = re.compile(r"^(?:chapter\s+\d+|\d+(?:\.\d+)*[.)]?)\s+.+$", re.IGNORECASE)
_UPPER_HEADING = re.compile(r"^[A-Z][A-Z\s&:/()\-]{4,}$")
_FONT_ALIASES = {
    "timesnewromanpsmt": "Times New Roman",
    "timesnewromanps": "Times New Roman",
    "timesnewroman": "Times New Roman",
    "times": "Times New Roman",
    "arialmt": "Arial",
    "arial": "Arial",
    "calibri": "Calibri",
    "cambriamath": "Cambria",
    "cambria": "Cambria",
    "georgia": "Georgia",
    "couriernewpsmt": "Courier New",
    "couriernew": "Courier New",
}


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_font_name(value: Any) -> str:
    name = _clean_text(value)
    name = re.sub(r"^[A-Z]{6}\+", "", name)
    key = re.sub(r"[^a-z0-9]", "", name.casefold())
    return _FONT_ALIASES.get(key, name) if name else NOT_DETECTED


def _weighted_mode(items: Iterable[tuple[Any, int]], *, minimum_share: float = 0.55) -> Any:
    weighted: Counter[Any] = Counter()
    total = 0
    for value, weight in items:
        if value in (None, "", NOT_DETECTED):
            continue
        amount = max(1, int(weight))
        weighted[value] += amount
        total += amount
    if not weighted or not total:
        return NOT_DETECTED
    value, weight = weighted.most_common(1)[0]
    return value if len(weighted) == 1 or weight / total >= minimum_share else NOT_DETECTED


def _consistent_number(values: Iterable[float], *, tolerance: float = 0.75) -> float | str:
    numbers = [float(value) for value in values]
    if not numbers or max(numbers) - min(numbers) > tolerance:
        return NOT_DETECTED
    return round(float(median(numbers)), 2)


def _page_size(width_pt: float, height_pt: float) -> str:
    width_mm = float(width_pt) * 25.4 / 72
    height_mm = float(height_pt) * 25.4 / 72
    short, long = sorted((width_mm, height_mm))
    for name, expected_short, expected_long in (("A4", 210.0, 297.0), ("Letter", 215.9, 279.4)):
        if abs(short - expected_short) <= 1.0 and abs(long - expected_long) <= 1.0:
            return name
    return f"{round(width_mm, 2)} x {round(height_mm, 2)} mm"


def _heading_level(value: str) -> int:
    match = re.match(r"^(?:chapter\s+\d+|(\d+(?:\.\d+)*))[.)]?\s+", value, re.IGNORECASE)
    if not match or not match.group(1):
        return 1
    return match.group(1).count(".") + 1


def _dedupe_headings(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        name = _clean_text(item.get("name"))
        key = re.sub(r"\s+", " ", name.casefold())
        if not name or key in seen:
            continue
        seen.add(key)
        output.append({**item, "name": name, "level": item.get("level", _heading_level(name))})
    return output


def _looks_like_project_title(value: Any, index: int, page: Any = 1) -> bool:
    """Keep a cover-page project title out of the required section list."""
    name = _clean_text(value)
    if index != 0 or page not in (None, 1):
        return False
    if re.match(r"^(?:chapter\s+\d+|\d+(?:\.\d+)*[.)]?)\s+", name, re.IGNORECASE):
        return False
    return len(name) >= 32 and bool(re.search(r"[:\-]|\b(?:project|platform|system|management|application)\b", name, re.IGNORECASE))


def _required_section_names(headings: list[dict[str, Any]]) -> list[str]:
    return [
        str(item["name"])
        for index, item in enumerate(headings)
        if not _looks_like_project_title(item.get("name"), index, item.get("page"))
    ]


def _explicit_requirement(text: str, term: str) -> bool:
    term_pattern = rf"\b{term}(?:s)?\b"
    required = r"(?:must|required|mandatory|shall|should)"
    return bool(
        re.search(rf"{term_pattern}[^.\n]{{0,120}}\b{required}\b", text, re.IGNORECASE)
        or re.search(rf"\b{required}\b[^.\n]{{0,120}}{term_pattern}", text, re.IGNORECASE)
    )


def _optional_requirements(text: str, headings: list[dict[str, Any]]) -> dict[str, int]:
    names = "\n".join(str(item.get("name", "")) for item in headings)
    result: dict[str, int] = {}
    if re.search(r"\b(?:references|bibliography)\b", names, re.IGNORECASE) or _explicit_requirement(text, "reference"):
        result["required_references"] = 1
    if re.search(r"\bappendix(?:es)?\b", names, re.IGNORECASE) or _explicit_requirement(text, "appendix"):
        result["required_appendices"] = 1
    for term, key in (("caption", "required_captions"), ("table", "required_tables"), ("figure", "required_figures")):
        if _explicit_requirement(text, term):
            result[key] = 1
    return result


def _base_rules(*, source: dict[str, Any], headings: list[dict[str, Any]], text: str) -> dict[str, Any]:
    rules: dict[str, Any] = {key: NOT_DETECTED for key in MAIN_RULE_KEYS}
    rules["required_sections"] = _required_section_names(headings)
    rules["section_sequence"] = list(rules["required_sections"])
    rules["detected_headings"] = headings
    rules.update(_optional_requirements(text, headings))
    rules["source"] = source
    return rules


def _source_field(source: dict[str, Any], key: str, *, page: int | None, method: str) -> None:
    source.setdefault("field_provenance", {})[key] = {"source_page": page, "method": method}


def _pdf_lines(page: Any, page_number: int, warnings: list[str]) -> tuple[str, list[dict[str, Any]], bool]:
    text = _clean_text(page.get_text("text"))
    text_page = None
    used_ocr = False
    if not text:
        try:
            text_page = page.get_textpage_ocr(language="eng", dpi=150, full=True)
            text = _clean_text(page.get_text("text", textpage=text_page))
            used_ocr = bool(text)
            if used_ocr:
                warnings.append(f"OCR fallback used on page {page_number}.")
        except Exception:
            warnings.append(f"No readable text or OCR was available on page {page_number}.")
    try:
        payload = page.get_text("dict", textpage=text_page) if text_page is not None else page.get_text("dict")
    except Exception:
        payload = {"blocks": []}
    lines: list[dict[str, Any]] = []
    for block in payload.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = [span for span in line.get("spans", []) if _clean_text(span.get("text"))]
            line_text = _clean_text(" ".join(str(span.get("text", "")) for span in spans))
            if line_text:
                lines.append({"text": line_text, "bbox": line.get("bbox"), "spans": spans, "page": page_number})
    return text, lines, used_ocr


def _pdf_headings(lines: list[dict[str, Any]], body_size: float | str) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    for line in lines:
        value = _clean_text(line["text"])
        if len(value) > 140 or value.endswith((".", ",", ";")):
            continue
        spans = line.get("spans", [])
        sizes = [float(span.get("size")) for span in spans if span.get("size")]
        bold = any(int(span.get("flags", 0)) & 16 for span in spans)
        larger = isinstance(body_size, (int, float)) and bool(sizes) and max(sizes) >= float(body_size) * 1.15
        if not (bold or larger or _NUMBERED_HEADING.match(value) or _UPPER_HEADING.match(value)):
            continue
        headings.append({"name": value, "page": line["page"], "level": _heading_level(value)})
    return _dedupe_headings(headings)


def _pdf_alignment(lines: list[dict[str, Any]], left_edge: float, right_edge: float) -> str:
    values: list[tuple[str, int]] = []
    width = max(1.0, right_edge - left_edge)
    for line in lines:
        if len(line["text"]) < 20 or not line.get("bbox"):
            continue
        x0, _, x1, _ = line["bbox"]
        left_gap = x0 - left_edge
        right_gap = right_edge - x1
        if abs(left_gap - right_gap) <= 4 and left_gap > 4 and right_gap > 4:
            alignment = "CENTER"
        elif left_gap <= 4:
            alignment = "LEFT"
        elif right_gap <= 4:
            alignment = "RIGHT"
        else:
            continue
        values.append((alignment, len(line["text"])))
    return _weighted_mode(values, minimum_share=0.7)


def _extract_pdf(data: bytes, filename: str | None, content_type: str | None) -> dict[str, Any]:
    try:
        import fitz

        document = fitz.open(stream=data, filetype="pdf")
    except (ImportError, RuntimeError, ValueError) as error:
        raise PdfExtractionError("invalid_pdf", "The university template PDF could not be read safely.") from error
    warnings: list[str] = []
    all_text: list[str] = []
    all_lines: list[dict[str, Any]] = []
    sizes: list[tuple[float, float]] = []
    page_margins: list[tuple[float, float, float, float]] = []
    fonts: list[tuple[str, int]] = []
    font_sizes: list[tuple[float, int]] = []
    line_spacings: list[float] = []
    page_numbering = False
    page_numbering_page: int | None = None
    try:
        if not document.page_count:
            raise PdfExtractionError("invalid_page_count", "The university template PDF contains no pages.")
        for page_number, page in enumerate(document, start=1):
            page_text, lines, used_ocr = _pdf_lines(page, page_number, warnings)
            if page_text:
                all_text.append(f"[PAGE {page_number}]\n{page_text}")
            all_lines.extend(lines)
            sizes.append((float(page.rect.width), float(page.rect.height)))
            boxes = [line["bbox"] for line in lines if line.get("bbox")]
            if boxes:
                page_margins.append((min(box[0] for box in boxes), page.rect.width - max(box[2] for box in boxes), min(box[1] for box in boxes), page.rect.height - max(box[3] for box in boxes)))
            for line in lines:
                spans = line.get("spans", [])
                for span in spans:
                    span_text = _clean_text(span.get("text"))
                    if span_text and span.get("font"):
                        fonts.append((_normalize_font_name(span["font"]), max(1, len(span_text))))
                    if span_text and span.get("size"):
                        font_sizes.append((round(float(span["size"]), 2), max(1, len(span_text))))
                if re.search(r"^\s*(?:page\s+)?\d+(?:\s*(?:of|/)\s*\d+)?\s*$", line["text"], re.IGNORECASE) and line.get("bbox") and line["bbox"][1] > page.rect.height * 0.75:
                    page_numbering = True
                    page_numbering_page = page_numbering_page or page_number
            if re.search(r"\bpage\s+\d+\b", page_text, re.IGNORECASE):
                page_numbering = True
                page_numbering_page = page_numbering_page or page_number
            for block in page.get_text("dict", textpage=None).get("blocks", []):
                if block.get("type") != 0:
                    continue
                previous_line_top: float | None = None
                for line in block.get("lines", []):
                    bbox = line.get("bbox")
                    sizes_for_line = [float(span.get("size")) for span in line.get("spans", []) if span.get("size")]
                    if bbox and sizes_for_line and previous_line_top is not None and bbox[1] >= previous_line_top:
                        line_spacings.append((float(bbox[1]) - previous_line_top) / max(1.0, median(sizes_for_line)))
                    if bbox:
                        previous_line_top = float(bbox[1])
        text = "\n".join(all_text).strip()
        if not text:
            warnings.append("No readable template text was detected.")
        body_size = _weighted_mode(font_sizes)
        headings = _pdf_headings(all_lines, body_size)
        source: dict[str, Any] = {
            "filename": filename or "uploaded-template.pdf",
            "content_type": content_type or "application/pdf",
            "extraction_runtime": "pymupdf-template-v2",
            "ocr_used": any("OCR fallback used" in warning for warning in warnings),
            "warnings": warnings,
        }
        rules = _base_rules(source=source, headings=headings, text=text)
        if sizes and all(size == sizes[0] for size in sizes):
            rules["page_size"] = _page_size(*sizes[0])
            _source_field(source, "page_size", page=1, method="PDF page rectangle")
        if page_margins:
            left, right, top, bottom = zip(*page_margins)
            for key, values in (
                ("left_margin_mm", [value * 25.4 / 72 for value in left]),
                ("right_margin_mm", [value * 25.4 / 72 for value in right]),
                ("top_margin_mm", [value * 25.4 / 72 for value in top]),
                ("bottom_margin_mm", [value * 25.4 / 72 for value in bottom]),
            ):
                rules[key] = _consistent_number(values)
                if rules[key] != NOT_DETECTED:
                    _source_field(source, key, page=None, method="PDF text bounding boxes by side")
        if body_size != NOT_DETECTED:
            rules["font_size_pt"] = body_size
            _source_field(source, "font_size_pt", page=None, method="Weighted PDF text-span mode")
        font_family = _weighted_mode(fonts)
        if font_family != NOT_DETECTED:
            rules["font_family"] = font_family
            _source_field(source, "font_family", page=None, method="Weighted PDF text-span mode with font-name normalization")
        if line_spacings:
            rules["line_spacing"] = _consistent_number([round(value, 2) for value in line_spacings], tolerance=0.15)
            if rules["line_spacing"] != NOT_DETECTED:
                _source_field(source, "line_spacing", page=None, method="PDF line-box spacing ratio")
        if page_margins and sizes and all(size == sizes[0] for size in sizes):
            rules["alignment"] = _pdf_alignment(all_lines, min(item[0] for item in page_margins), max(sizes[0][0] - item[1] for item in page_margins))
            if rules["alignment"] != NOT_DETECTED:
                _source_field(source, "alignment", page=None, method="PDF line-box alignment")
        if headings:
            heading_styles = []
            for line in all_lines:
                if any(item["name"] == line["text"] for item in headings):
                    bold = any(int(span.get("flags", 0)) & 16 for span in line.get("spans", []))
                    heading_sizes = [float(span.get("size")) for span in line.get("spans", []) if span.get("size")]
                    if heading_sizes:
                        heading_styles.append((f"{'Bold' if bold else 'Regular'} {round(max(heading_sizes), 2)} pt", len(line["text"])))
            rules["heading_style"] = _weighted_mode(heading_styles)
            if rules["heading_style"] != NOT_DETECTED:
                _source_field(source, "heading_style", page=None, method="PDF heading-span flags and sizes")
        if page_numbering:
            rules["page_numbering"] = True
            _source_field(source, "page_numbering", page=page_numbering_page, method="PDF footer/page-number text")
        if not headings:
            source["warnings"].append("No clearly formatted template headings were detected; required sections were not inferred.")
        return rules
    finally:
        document.close()


def _docx_paragraph_font(paragraph: Any, run: Any, normal_style: Any) -> str:
    style_font = getattr(getattr(paragraph, "style", None), "font", None)
    return _normalize_font_name(run.font.name or getattr(style_font, "name", None) or getattr(normal_style.font, "name", None))


def _docx_run_size(paragraph: Any, run: Any, normal_style: Any) -> float | str:
    style_font = getattr(getattr(paragraph, "style", None), "font", None)
    size = run.font.size or getattr(style_font, "size", None) or getattr(normal_style.font, "size", None)
    return round(float(size.pt), 2) if size is not None and getattr(size, "pt", None) else NOT_DETECTED


def _docx_alignment(value: Any) -> str:
    name = str(value).split(".")[-1].split("(", 1)[0].strip().upper()
    return {"LEFT": "LEFT", "CENTER": "CENTER", "RIGHT": "RIGHT", "JUSTIFY": "JUSTIFY"}.get(name, NOT_DETECTED)


def _extract_docx(data: bytes, filename: str | None, content_type: str | None) -> dict[str, Any]:
    try:
        document = Document(io.BytesIO(data))
    except (ValueError, OSError, ImportError) as error:
        raise PdfExtractionError("invalid_docx", "The university template DOCX could not be read safely.") from error
    normal_style = document.styles["Normal"] if "Normal" in [style.name for style in document.styles] else document.styles[0]
    paragraphs = list(document.paragraphs)
    text_lines = [_clean_text(paragraph.text) for paragraph in paragraphs if _clean_text(paragraph.text)]
    for table in document.tables:
        for row in table.rows:
            text_lines.extend(_clean_text(cell.text) for cell in row.cells if _clean_text(cell.text))
    text = "\n".join(text_lines)
    headings: list[dict[str, Any]] = []
    for paragraph in paragraphs:
        value = _clean_text(paragraph.text)
        style_name = _clean_text(getattr(getattr(paragraph, "style", None), "name", ""))
        if value and style_name.casefold().startswith("heading"):
            headings.append({"name": value, "page": None, "level": _heading_level(value), "style": style_name})
    headings = _dedupe_headings(headings)
    source: dict[str, Any] = {
        "filename": filename or "uploaded-template.docx",
        "content_type": content_type or "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "extraction_runtime": "python-docx-template-v2",
        "ocr_used": False,
        "warnings": [],
    }
    rules = _base_rules(source=source, headings=headings, text=text)
    sections = list(document.sections)
    if sections:
        page_sizes = [(round(float(section.page_width.mm), 2), round(float(section.page_height.mm), 2)) for section in sections if section.page_width and section.page_height]
        if page_sizes and all(size == page_sizes[0] for size in page_sizes):
            rules["page_size"] = _page_size(page_sizes[0][0] * 72 / 25.4, page_sizes[0][1] * 72 / 25.4)
            _source_field(source, "page_size", page=None, method="DOCX section page size")
        margin_values = {
            "left_margin_mm": [float(section.left_margin.mm) for section in sections],
            "right_margin_mm": [float(section.right_margin.mm) for section in sections],
            "top_margin_mm": [float(section.top_margin.mm) for section in sections],
            "bottom_margin_mm": [float(section.bottom_margin.mm) for section in sections],
        }
        for key, values in margin_values.items():
            rules[key] = _consistent_number(values, tolerance=0.05)
            if rules[key] != NOT_DETECTED:
                _source_field(source, key, page=None, method="DOCX section margin setting")
    body_paragraphs = [paragraph for paragraph in paragraphs if _clean_text(paragraph.text) and not _clean_text(getattr(getattr(paragraph, "style", None), "name", "")).casefold().startswith("heading")]
    font_items: list[tuple[str, int]] = []
    size_items: list[tuple[float, int]] = []
    spacing_values: list[float] = []
    alignment_items: list[tuple[str, int]] = []
    for paragraph in body_paragraphs:
        text_length = max(1, len(_clean_text(paragraph.text)))
        for run in paragraph.runs:
            run_text = _clean_text(run.text)
            if not run_text:
                continue
            font = _docx_paragraph_font(paragraph, run, normal_style)
            size = _docx_run_size(paragraph, run, normal_style)
            if font != NOT_DETECTED:
                font_items.append((font, len(run_text)))
            if isinstance(size, (int, float)):
                size_items.append((size, len(run_text)))
        alignment = _docx_alignment(paragraph.alignment)
        if alignment != NOT_DETECTED:
            alignment_items.append((alignment, text_length))
        spacing = paragraph.paragraph_format.line_spacing
        if isinstance(spacing, (int, float)) and 0.5 <= float(spacing) <= 4:
            spacing_values.append(round(float(spacing), 2))
        elif getattr(spacing, "pt", None) and size_items:
            spacing_values.append(round(float(spacing.pt) / float(size_items[-1][0]), 2))
        else:
            rule_name = str(paragraph.paragraph_format.line_spacing_rule).upper()
            spacing_values.extend({"SINGLE": [1.0], "ONE_POINT_FIVE": [1.5], "DOUBLE": [2.0]}.get(rule_name, []))
    for key, value, method in (
        ("font_family", _weighted_mode(font_items), "Weighted DOCX run/style mode with font-name normalization"),
        ("font_size_pt", _weighted_mode(size_items), "Weighted DOCX run/style mode"),
        ("alignment", _weighted_mode(alignment_items, minimum_share=0.7), "Weighted DOCX paragraph alignment"),
    ):
        rules[key] = value
        if value != NOT_DETECTED:
            _source_field(source, key, page=None, method=method)
    rules["line_spacing"] = _consistent_number(spacing_values, tolerance=0.05) if spacing_values else NOT_DETECTED
    if rules["line_spacing"] != NOT_DETECTED:
        _source_field(source, "line_spacing", page=None, method="DOCX explicit paragraph spacing")
    style_items = [(str(item.get("style")), 1) for item in headings if item.get("style")]
    rules["heading_style"] = _weighted_mode(style_items, minimum_share=0.7)
    if rules["heading_style"] != NOT_DETECTED:
        _source_field(source, "heading_style", page=None, method="DOCX paragraph heading style")
    xml = document.part.element.xml
    if re.search(r"<w:(?:instrText|fldSimple)[^>]*>[^<]*\b(?:PAGE|NUMPAGES)\b", xml, re.IGNORECASE):
        rules["page_numbering"] = True
        _source_field(source, "page_numbering", page=None, method="DOCX PAGE field in document XML")
    if not headings:
        source["warnings"].append("No DOCX Heading styles were detected; required sections were not inferred.")
    return rules


def _section_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]
    if isinstance(value, str):
        return [_clean_text(item) for item in re.split(r"(?:\\n|\r?\n)", value) if _clean_text(item)]
    return []


_RULE_RANGES: dict[str, tuple[float, float]] = {
    "top_margin_mm": (10.0, 50.0),
    "bottom_margin_mm": (10.0, 50.0),
    "left_margin_mm": (10.0, 50.0),
    "right_margin_mm": (10.0, 50.0),
    "line_spacing": (0.8, 3.0),
    "font_size_pt": (8.0, 16.0),
}


def _clamp_detected_rule(key: str, value: Any) -> Any:
    if value in (None, "") or (isinstance(value, str) and value.strip().casefold().startswith("not detected")):
        return NOT_DETECTED
    bounds = _RULE_RANGES.get(key)
    if bounds is None:
        return value
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return NOT_DETECTED
    low, high = bounds
    if numeric < low or numeric > high:
        return NOT_DETECTED
    return numeric if key == "line_spacing" else round(numeric, 2)


def normalize_template_rules(rules: dict[str, Any]) -> dict[str, Any]:
    """Keep only comparable main rules and explicit optional requirements."""
    cleaned: dict[str, Any] = {}
    for key in MAIN_RULE_KEYS:
        if key in rules:
            cleaned[key] = _clamp_detected_rule(key, rules[key])
    sections = _section_list(rules.get("required_sections")) or _section_list(rules.get("section_sequence"))
    sections = [name for index, name in enumerate(sections) if not _looks_like_project_title(name, index)]
    if sections:
        cleaned["required_sections"] = sections
        cleaned["section_sequence"] = list(sections)
    for key in OPTIONAL_REQUIREMENT_KEYS:
        value = rules.get(key)
        if isinstance(value, bool):
            if value:
                cleaned[key] = 1
        elif isinstance(value, (int, float)) and value > 0:
            cleaned[key] = int(value)
        elif isinstance(value, str) and value.strip().casefold() in {"required", "yes", "true", "1"}:
            cleaned[key] = 1
    if isinstance(rules.get("detected_headings"), list):
        cleaned["detected_headings"] = rules["detected_headings"]
    if isinstance(rules.get("source"), dict):
        cleaned["source"] = rules["source"]
    return cleaned


def extract_template_rules(data: bytes, content_type: str | None, filename: str | None) -> dict[str, Any]:
    """Extract deterministic, comparison-ready rules from the official file."""
    suffix = (filename or "").casefold().rsplit(".", 1)[-1]
    normalized_content_type = (content_type or "").casefold()
    if suffix == "pdf" or normalized_content_type == "application/pdf":
        return normalize_template_rules(_extract_pdf(data, filename, content_type))
    if suffix == "docx" or normalized_content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        if not data.startswith(b"PK"):
            raise PdfExtractionError("invalid_docx", "Upload a valid university template DOCX file.")
        return normalize_template_rules(_extract_docx(data, filename, content_type))
    raise PdfExtractionError("unsupported_template", "Only PDF and DOCX university templates are supported.")


__all__ = ["MAIN_RULE_KEYS", "NOT_DETECTED", "OPTIONAL_REQUIREMENT_KEYS", "PdfExtractionError", "extract_template_rules", "normalize_template_rules"]
