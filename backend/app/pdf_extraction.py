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


def _docx_formatting(document: Document) -> dict[str, object]:
    """Read measurable formatting from the first DOCX section and its runs."""
    section = document.sections[0] if document.sections else None
    families: list[str] = []
    sizes: list[float] = []
    spacings: list[float] = []
    for paragraph in document.paragraphs:
        if paragraph.paragraph_format.line_spacing is not None:
            spacing = paragraph.paragraph_format.line_spacing
            if isinstance(spacing, (int, float)):
                spacings.append(float(spacing))
        for run in paragraph.runs:
            if run.font.name:
                families.append(run.font.name)
            if run.font.size and run.font.size.pt:
                sizes.append(float(run.font.size.pt))
    result: dict[str, object] = {}
    if section is not None:
        width = section.page_width.inches
        height = section.page_height.inches
        if width and height:
            result["page_size"] = "A4" if abs(width - 8.27) < 0.15 and abs(height - 11.69) < 0.15 else "Letter" if abs(width - 8.5) < 0.15 and abs(height - 11) < 0.15 else f"{round(width, 2)}x{round(height, 2)} in"
        result["margin_mm"] = round(section.left_margin.mm, 2)
        result["right_margin_mm"] = round(section.right_margin.mm, 2)
        result["top_margin_mm"] = round(section.top_margin.mm, 2)
        result["bottom_margin_mm"] = round(section.bottom_margin.mm, 2)
    if families:
        result["font_family"] = Counter(families).most_common(1)[0][0]
    if sizes:
        result["font_size_pt"] = round(float(median(sizes)), 2)
    if spacings:
        result["line_spacing"] = round(float(median(spacings)), 2)
    result["table_count"] = len(document.tables)
    result["figure_count"] = len(getattr(document, "inline_shapes", ()))
    result["page_numbering"] = any("PAGE" in paragraph.text.upper() for paragraph in document.paragraphs)
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
            "page_size": "A4" if abs(width_in - 8.27) < 0.15 and abs(height_in - 11.69) < 0.15 else "Letter" if abs(width_in - 8.5) < 0.15 and abs(height_in - 11) < 0.15 else f"{round(width_in, 2)}x{round(height_in, 2)} in",
            "page_count": document.page_count,
        }
        families: list[str] = []
        sizes: list[float] = []
        left_edges: list[float] = []
        right_edges: list[float] = []
        top_edges: list[float] = []
        bottom_edges: list[float] = []
        line_gaps: list[float] = []
        table_count = 0
        figure_count = 0
        page_numbering = False
        for page in document:
            page_rect = page.rect
            blocks = page.get_text("dict").get("blocks", [])
            table_count += len(page.find_tables().tables) if hasattr(page, "find_tables") else 0
            figure_count += len(page.get_images(full=True))
            page_text = page.get_text("text")
            page_numbering = page_numbering or bool(re.search(r"(?:page\s+\d+|\b\d+\s*(?:of|/)\s*\d+\b)", page_text, re.IGNORECASE))
            previous_line_bottom: float | None = None
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    line_box = line.get("bbox")
                    if not line_box:
                        continue
                    x0, y0, x1, y1 = line_box
                    left_edges.append(x0)
                    right_edges.append(page_rect.width - x1)
                    top_edges.append(y0)
                    bottom_edges.append(page_rect.height - y1)
                    if previous_line_bottom is not None and y0 >= previous_line_bottom:
                        line_gaps.append(y0 - previous_line_bottom)
                    previous_line_bottom = y1
                    for span in line.get("spans", []):
                        if span.get("font"):
                            families.append(str(span["font"]).split("+")[-1])
                        if span.get("size"):
                            sizes.append(float(span["size"]))
        if families:
            result["font_family"] = Counter(families).most_common(1)[0][0]
        if sizes:
            result["font_size_pt"] = round(float(median(sizes)), 2)
        if left_edges:
            result["margin_mm"] = round(float(median(left_edges)) * 25.4 / 72, 2)
            result["right_margin_mm"] = round(float(median(right_edges)) * 25.4 / 72, 2)
            result["top_margin_mm"] = round(float(median(top_edges)) * 25.4 / 72, 2)
            result["bottom_margin_mm"] = round(float(median(bottom_edges)) * 25.4 / 72, 2)
        if line_gaps and sizes:
            result["line_spacing"] = round(float(median(line_gaps)) / float(median(sizes)), 2)
        result["table_count"] = table_count
        result["figure_count"] = figure_count
        result["page_numbering"] = page_numbering
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
    "topic": ("research area", "topic", "area"),
    "purpose": ("problem statement", "project purpose", "purpose", "problem", "aim"),
    "objectives": ("project objectives", "objectives", "objective", "goals", "goal"),
    "methodology": ("methodology and approach", "methodology", "method", "approach", "methods"),
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
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if line:
            line = re.sub(r"\s*:\s*", ": ", line, count=1)
            normalized_lines.append(line)
    return "\n".join(normalized_lines).strip()


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
        text = "\n".join(f"[PAGE {index + 1}]\n{content}" for index, content in enumerate(page_text) if content)
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
