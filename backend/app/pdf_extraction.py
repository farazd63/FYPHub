"""Deterministic, local extraction for supervisor-request PDFs and DOCX files."""

from __future__ import annotations

import hashlib
import io
import re
from collections import Counter
from docx import Document
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_SUPERVISOR_REQUEST_PDF_BYTES = 5 * 1024 * 1024
EXTRACTION_RUNTIME = "pypdf-local"

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


def _normalize_document_font(value: object) -> str:
    name = re.sub(r"\s+", " ", str(value or "")).strip()
    name = re.sub(r"^[A-Z]{6}\+", "", name)
    key = re.sub(r"[^a-z0-9]", "", name.casefold())
    return _FONT_ALIASES.get(key, name)


def _weighted_mode(items: list[tuple[object, int]], minimum_share: float = 0.55) -> object | None:
    weighted: Counter[object] = Counter()
    total = 0
    for value, weight in items:
        if value in (None, ""):
            continue
        amount = max(1, int(weight))
        weighted[value] += amount
        total += amount
    if not weighted or not total:
        return None
    value, weight = weighted.most_common(1)[0]
    return value if len(weighted) == 1 or weight / total >= minimum_share else None


def _page_size_label(width_pt: float, height_pt: float) -> str:
    width_mm = width_pt * 25.4 / 72
    height_mm = height_pt * 25.4 / 72
    short, long = sorted((width_mm, height_mm))
    for name, expected_short, expected_long in (("A4", 210.0, 297.0), ("Letter", 215.9, 279.4)):
        if abs(short - expected_short) <= 1.0 and abs(long - expected_long) <= 1.0:
            return name
    return f"{round(width_mm, 2)} x {round(height_mm, 2)} mm"


def _docx_formatting(document: Document) -> dict[str, object]:
    """Read measurable formatting from the first DOCX section and its runs."""
    section = document.sections[0] if document.sections else None
    families: list[tuple[str, int]] = []
    sizes: list[tuple[float, int]] = []
    spacings: list[float] = []
    alignments: list[str] = []
    heading_styles: list[str] = []
    caption_count = 0
    reference_count = 0
    appendix_count = 0
    for paragraph in document.paragraphs:
        paragraph_text = paragraph.text.strip()
        if paragraph.alignment is not None:
            alignments.append(str(paragraph.alignment).split(".")[-1].split("(", 1)[0].strip().upper())
        style_name = getattr(getattr(paragraph, "style", None), "name", "") or ""
        if style_name.casefold().startswith("heading"):
            heading_styles.append(style_name)
        if re.match(r"^(?:figure|fig\.?|table)\s*\d+", paragraph_text, re.IGNORECASE):
            caption_count += 1
        if re.match(r"^(?:references|bibliography)\b", paragraph_text, re.IGNORECASE):
            reference_count += 1
        if re.match(r"^(?:appendix|appendices)\b", paragraph_text, re.IGNORECASE):
            appendix_count += 1
        if paragraph.paragraph_format.line_spacing is not None:
            spacing = paragraph.paragraph_format.line_spacing
            if isinstance(spacing, (int, float)):
                spacings.append(float(spacing))
            elif getattr(spacing, "pt", None) and paragraph.runs:
                run_size = next((run.font.size.pt for run in paragraph.runs if run.font.size and run.font.size.pt), None)
                if run_size:
                    spacings.append(float(spacing.pt) / float(run_size))
        else:
            spacing_rule = str(paragraph.paragraph_format.line_spacing_rule).upper()
            spacings.extend({"SINGLE": [1.0], "ONE_POINT_FIVE": [1.5], "DOUBLE": [2.0]}.get(spacing_rule.split(" ", 1)[0], []))
        for run in paragraph.runs:
            run_text = run.text.strip()
            style_font = getattr(getattr(paragraph, "style", None), "font", None)
            family = _normalize_document_font(run.font.name or getattr(style_font, "name", None))
            if family:
                families.append((family, max(1, len(run_text))))
            size = run.font.size or getattr(style_font, "size", None)
            if size and size.pt:
                sizes.append((round(float(size.pt), 2), max(1, len(run_text))))
    result: dict[str, object] = {}
    if section is not None:
        width = section.page_width.inches
        height = section.page_height.inches
        if width and height:
            result["page_size"] = _page_size_label(section.page_width.pt, section.page_height.pt)
            result["orientation"] = "Portrait" if height >= width else "Landscape"
        result["left_margin_mm"] = round(section.left_margin.mm, 2)
        result["margin_mm"] = round(section.left_margin.mm, 2)
        result["right_margin_mm"] = round(section.right_margin.mm, 2)
        result["top_margin_mm"] = round(section.top_margin.mm, 2)
        result["bottom_margin_mm"] = round(section.bottom_margin.mm, 2)
    if families:
        font_family = _weighted_mode(families)
        if font_family:
            result["font_family"] = font_family
    if sizes:
        font_size = _weighted_mode(sizes)
        if isinstance(font_size, (int, float)):
            result["font_size_pt"] = round(float(font_size), 2)
    if spacings:
        result["line_spacing"] = round(float(median(spacings)), 2)
    if alignments:
        result["alignment"] = Counter(alignments).most_common(1)[0][0]
    if heading_styles:
        result["heading_style"] = Counter(heading_styles).most_common(1)[0][0]
    result["table_count"] = len(document.tables)
    result["figure_count"] = len(getattr(document, "inline_shapes", ()))
    result["page_numbering"] = bool(re.search(r"<w:(?:instrText|fldSimple)[^>]*>[^<]*\b(?:PAGE|NUMPAGES)\b", document.part.element.xml, re.IGNORECASE))
    result["page_numbering_pages"] = [1] if result["page_numbering"] else []
    result["caption_count"] = caption_count
    result["reference_count"] = reference_count
    result["appendix_count"] = appendix_count
    return result


def _pdf_formatting(data: bytes) -> dict[str, object]:
    """Read measurable page, margin, and typography metadata from a PDF."""
    try:
        import fitz

        document = fitz.open(stream=data, filetype="pdf")
    except (ImportError, RuntimeError, ValueError):
        return {}
    try:
        if not document.page_count:
            return {}
        first_page = document[0]
        rect = first_page.rect
        width_in = rect.width / 72
        height_in = rect.height / 72
        result: dict[str, object] = {
            "page_size": _page_size_label(rect.width, rect.height),
            "orientation": "Portrait" if height_in >= width_in else "Landscape",
            "page_count": document.page_count,
        }
        families: list[tuple[str, int]] = []
        sizes: list[tuple[float, int]] = []
        left_edges: list[float] = []
        right_edges: list[float] = []
        top_edges: list[float] = []
        bottom_edges: list[float] = []
        line_gaps: list[float] = []
        table_count = 0
        figure_count = 0
        page_numbering = False
        page_numbering_pages: list[int] = []
        caption_count = 0
        reference_count = 0
        appendix_count = 0
        for page_index, page in enumerate(document, start=1):
            page_rect = page.rect
            blocks = page.get_text("dict").get("blocks", [])
            table_count += len(page.find_tables().tables) if hasattr(page, "find_tables") else 0
            figure_count += len(page.get_images(full=True))
            page_text = page.get_text("text")
            page_has_number = bool(re.search(r"(?:page\s+\d+|\b\d+\s*(?:of|/)\s*\d+\b)", page_text, re.IGNORECASE))
            page_numbering = page_numbering or page_has_number
            if page_has_number:
                page_numbering_pages.append(page_index)
            caption_count += len(re.findall(r"^(?:figure|fig\.?|table)\s*\d+", page_text, re.IGNORECASE | re.MULTILINE))
            reference_count += len(re.findall(r"^\s*(?:references|bibliography)\b", page_text, re.IGNORECASE | re.MULTILINE))
            appendix_count += len(re.findall(r"^\s*(?:appendix|appendices)\b", page_text, re.IGNORECASE | re.MULTILINE))
            for block in blocks:
                if block.get("type") != 0:
                    continue
                previous_line_top: float | None = None
                for line in block.get("lines", []):
                    line_box = line.get("bbox")
                    if not line_box:
                        continue
                    x0, y0, x1, y1 = line_box
                    left_edges.append(x0)
                    right_edges.append(page_rect.width - x1)
                    top_edges.append(y0)
                    bottom_edges.append(page_rect.height - y1)
                    line_sizes = [float(span.get("size")) for span in line.get("spans", []) if span.get("size")]
                    if previous_line_top is not None and y0 >= previous_line_top and line_sizes:
                        # Keep the physical baseline distance here.  The final
                        # line-spacing ratio is calculated against the median
                        # font size below.
                        line_gaps.append(y0 - previous_line_top)
                    previous_line_top = y0
                    for span in line.get("spans", []):
                        span_text = str(span.get("text") or "").strip()
                        weight = max(1, len(span_text))
                        if span.get("font") and span_text:
                            families.append((_normalize_document_font(str(span["font"]).split("+")[-1]), weight))
                        if span.get("size") and span_text:
                            sizes.append((round(float(span["size"]), 2), weight))
        if families:
            font_family = _weighted_mode(families)
            if font_family:
                result["font_family"] = font_family
        if sizes:
            font_size = _weighted_mode(sizes)
            if isinstance(font_size, (int, float)):
                result["font_size_pt"] = round(float(font_size), 2)
        if left_edges:
            result["left_margin_mm"] = round(float(min(left_edges)) * 25.4 / 72, 2)
            result["margin_mm"] = result["left_margin_mm"]
            result["right_margin_mm"] = round(float(min(right_edges)) * 25.4 / 72, 2)
            result["top_margin_mm"] = round(float(min(top_edges)) * 25.4 / 72, 2)
            result["bottom_margin_mm"] = round(float(min(bottom_edges)) * 25.4 / 72, 2)
        if line_gaps and sizes:
            size_values = [size for size, _weight in sizes]
            if size_values:
                result["line_spacing"] = round(float(median(line_gaps)) / float(median(size_values)), 2)
        result["table_count"] = table_count
        result["figure_count"] = figure_count
        result["page_numbering"] = page_numbering
        result["page_numbering_pages"] = page_numbering_pages
        result["caption_count"] = caption_count
        result["reference_count"] = reference_count
        result["appendix_count"] = appendix_count
        return result
    finally:
        document.close()


class PdfExtractionError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def extract_proposal_document(data: bytes, content_type: str | None, filename: str | None) -> ExtractionResult:
    """Extract proposal fields from PDF, DOCX, or UTF-8 TXT documents.

    Text-only documents deliberately expose no layout measurements. The
    compliance engine can therefore report those checks as UNVERIFIABLE rather
    than inventing formatting values.
    """
    suffix = (filename or "").casefold().rsplit(".", 1)[-1]
    normalized_content_type = (content_type or "").casefold()
    if suffix in {"txt", "text", "md"} or normalized_content_type in {"text/plain", "text/markdown"}:
        if len(data) > MAX_SUPERVISOR_REQUEST_PDF_BYTES:
            raise PdfExtractionError("file_too_large", "The text proposal exceeds the configured 5 MiB limit.")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise PdfExtractionError("invalid_text", "The TXT proposal must use UTF-8 text encoding.") from error
        normalized = _normalize_text(text)
        if len(normalized) < 20:
            raise PdfExtractionError("invalid_pdf", "The uploaded text proposal does not contain readable proposal content.")
        return ExtractionResult(
            content_type="text/plain",
            file_size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            page_count=1,
            extracted_text=normalized,
            extracted_fields=_extract_fields(normalized),
            extracted_at=datetime.now(timezone.utc),
        )
    if suffix == "docx" or (content_type or "").casefold() == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        if len(data) > MAX_SUPERVISOR_REQUEST_PDF_BYTES:
            raise PdfExtractionError("file_too_large", "The proposal document exceeds the configured 5 MiB limit.")
        if not data.startswith(b"PK") or not (filename or "").casefold().endswith(".docx"):
            raise PdfExtractionError("invalid_docx", "Upload a valid DOCX proposal file.")
        try:
            document = Document(io.BytesIO(data))
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        except (ValueError, OSError, ImportError) as error:
            raise PdfExtractionError("invalid_docx", "The proposal DOCX could not be read safely.") from error
        normalized = _normalize_text(text)
        if len(normalized) < 20:
            raise PdfExtractionError("unreadable_docx", "The DOCX proposal does not contain readable text.")
        return ExtractionResult(
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            page_count=1,
            extracted_text=normalized,
            extracted_fields={**_extract_fields(normalized), **_docx_formatting(document)},
            extracted_at=datetime.now(timezone.utc),
        )
    return extract_one_page_pdf(data, content_type, filename)


@dataclass(frozen=True)
class ExtractionResult:
    content_type: str
    file_size: int
    sha256: str
    page_count: int
    extracted_text: str
    extracted_fields: dict[str, object]
    extracted_at: datetime


_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "title": ("proposal title", "project title", "title"),
    "topic": ("topic / area", "research area", "topic", "area"),
    "purpose": ("problem statement / purpose", "problem statement", "project purpose", "purpose", "problem", "aim"),
    "objectives": ("project objectives", "objectives", "objective", "goals", "goal"),
    "methodology": ("methodology / approach", "methodology and approach", "methodology", "method", "approach", "methods"),
    "expected_outcomes": ("expected outcomes", "outcomes", "expected outcome", "outcome"),
    "scope": ("scope and limitations", "scope", "project scope", "scope of the project", "limitations"),
    "proposed_solution": ("proposed solution", "solution", "proposed system", "system proposal"),
}
_FIELD_HEADING = re.compile(
    rf"^\s*(?P<label>{'|'.join(sorted((re.escape(alias) for aliases in _FIELD_ALIASES.values() for alias in aliases), key=len, reverse=True))})\s*(?:(?::|-)\s*(?P<value>.*))?$",
    flags=re.IGNORECASE,
)


def _field(value: str | None, page: int = 1) -> dict[str, object]:
    if value is None:
        return {"value": None, "display": "Not detected in PDF", "source_page": None, "source": None}
    return {"value": value, "display": value, "source_page": page, "source": f"page {page}"}


def _normalize_text(text: str) -> str:
    """Normalize pypdf output while retaining line boundaries used by section parsing."""
    normalized_lines = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ").split("\n"):
        # Some PDFs expose unmapped glyphs as control characters. Remove those
        # markers before sending extracted content to the summary model.
        clean_line = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", raw_line)
        line = re.sub(r"[ \t]+", " ", clean_line).strip()
        if line:
            line = re.sub(r"\s*:\s*", ": ", line, count=1)
            normalized_lines.append(line)
    return "\n".join(normalized_lines).strip()


def _pdf_text_needs_ocr(text: str) -> bool:
    control_count = sum(1 for character in text if ord(character) < 32 and character not in "\r\n\t")
    return not text.strip() or control_count >= max(4, len(text) // 250)


def _fitz_pdf_text(data: bytes, *, ocr_fallback: bool = False) -> str:
    """Extract page text with PyMuPDF, which preserves custom-font PDFs better."""
    try:
        import fitz

        document = fitz.open(stream=data, filetype="pdf")
    except (ImportError, RuntimeError, ValueError):
        return ""
    try:
        pages = []
        for page_number, page in enumerate(document, start=1):
            content = (page.get_text("text") or "").strip()
            if ocr_fallback and _pdf_text_needs_ocr(content):
                try:
                    textpage = page.get_textpage_ocr(language="eng", dpi=120, full=True)
                    ocr_content = (page.get_text("text", textpage=textpage) or "").strip()
                    if len(ocr_content) >= 20:
                        content = ocr_content
                except Exception:
                    pass
            if content:
                pages.append(f"[PAGE {page_number}]\n{content}")
        return "\n".join(pages)
    finally:
        document.close()


def extract_pdf_text_for_summary(data: bytes) -> str:
    """Return readable PDF text, using OCR only for damaged/unreadable pages."""
    return _normalize_text(_fitz_pdf_text(data, ocr_fallback=True))


def _heading(line: str) -> tuple[str, str | None] | None:
    match = _FIELD_HEADING.match(line)
    if not match:
        return None
    label = re.sub(r"\s+", " ", match.group("label")).strip().casefold()
    for name, aliases in _FIELD_ALIASES.items():
        if label in aliases:
            value = (match.group("value") or "").strip() or None
            return name, value
    return None


def _extract_fields(text: str) -> dict[str, object]:
    fields: dict[str, object] = {name: _field(None) for name in _FIELD_ALIASES}
    lines = _normalize_text(text).splitlines()
    sections: list[tuple[int, int, str, str | None]] = []
    for index, line in enumerate(lines):
        matched = _heading(line)
        if matched:
            sections.append((index, index, matched[0], matched[1]))

    matched_lines: set[int] = set()
    for position, (start, _, name, inline_value) in enumerate(sections):
        end = sections[position + 1][0] if position + 1 < len(sections) else len(lines)
        content_lines = [inline_value] if inline_value else []
        content_lines.extend(lines[start + 1:end])
        value = " ".join(line.strip() for line in content_lines if line and line.strip()).strip() or None
        if value is not None:
            current = fields[name]["value"]
            fields[name] = _field(value if current is None else f"{current} {value}")
        matched_lines.update(range(start, end))

    other = [
        {"value": line, "source_page": 1, "source": "page 1"}
        for index, line in enumerate(lines)
        if index not in matched_lines and not re.match(r"^(?:page|date)\s*[:\-]", line, flags=re.IGNORECASE)
    ]
    fields["other_sections"] = other
    fields["required_fields"] = ["title", "purpose"]
    fields["missing_required_fields"] = [name for name in ("title", "purpose") if not fields[name]["value"]]
    fields["warnings"] = [f"{name} was not detected in the uploaded document." for name in ("topic", "objectives", "methodology", "scope", "proposed_solution", "expected_outcomes") if not fields[name]["value"]]
    return fields


def extract_one_page_pdf(data: bytes, content_type: str | None, filename: str | None) -> ExtractionResult:
    if len(data) > MAX_SUPERVISOR_REQUEST_PDF_BYTES:
        raise PdfExtractionError("file_too_large", "The proposal PDF exceeds the configured 5 MiB limit.")
    if not data.startswith(b"%PDF-"):
        raise PdfExtractionError("invalid_pdf", "Upload exactly one PDF proposal file.")
    if content_type and content_type.lower() != "application/pdf":
        raise PdfExtractionError("invalid_pdf", "The proposal file must have PDF content type.")
    if filename and not filename.lower().endswith(".pdf"):
        raise PdfExtractionError("invalid_pdf", "The proposal filename must use the .pdf extension.")
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        page_count = len(reader.pages)
        if page_count < 1:
            raise PdfExtractionError("invalid_page_count", "The proposal PDF contains no pages.")
        page_text = [(reader.pages[index].extract_text() or "").strip() for index in range(page_count)]
        pypdf_text = "\n".join(f"[PAGE {index + 1}]\n{content}" for index, content in enumerate(page_text) if content)
        fitz_text = _fitz_pdf_text(data)
        text = fitz_text if len(_normalize_text(fitz_text)) >= 20 else pypdf_text
    except PdfExtractionError:
        raise
    except (PdfReadError, ValueError, OSError) as error:
        raise PdfExtractionError("invalid_pdf", "The proposal PDF could not be read safely.") from error
    normalized = _normalize_text(text)
    if len(normalized) < 20:
        raise PdfExtractionError("unreadable_pdf", "The PDF does not contain readable text.")
    return ExtractionResult(
        content_type="application/pdf",
        file_size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        page_count=page_count,
        extracted_text=normalized,
        extracted_fields={**_extract_fields(normalized), **_pdf_formatting(data)},
        extracted_at=datetime.now(timezone.utc),
    )
