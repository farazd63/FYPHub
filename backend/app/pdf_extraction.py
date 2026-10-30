"""Deterministic, local extraction for one-page supervisor-request PDFs and DOCX files."""

from __future__ import annotations

import hashlib
import io
import re
from docx import Document
from dataclasses import dataclass
from datetime import datetime, timezone

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_SUPERVISOR_REQUEST_PDF_BYTES = 5 * 1024 * 1024
EXTRACTION_RUNTIME = "pypdf-local"


class PdfExtractionError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def extract_proposal_document(data: bytes, content_type: str | None, filename: str | None) -> ExtractionResult:
    """Extract the shared proposal fields from a PDF or DOCX upload."""
    suffix = (filename or "").casefold().rsplit(".", 1)[-1]
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
            extracted_fields=_extract_fields(normalized),
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
    fields["warnings"] = [f"{name} was not detected in the PDF." for name in ("topic", "objectives", "methodology", "expected_outcomes") if not fields[name]["value"]]
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
        if page_count != 1:
            raise PdfExtractionError("invalid_page_count", "The proposal PDF must contain exactly one page.")
        text = reader.pages[0].extract_text() or ""
    except PdfExtractionError:
        raise
    except (PdfReadError, ValueError, OSError) as error:
        raise PdfExtractionError("invalid_pdf", "The proposal PDF could not be read safely.") from error
    normalized = _normalize_text(text)
    if len(normalized) < 20:
        raise PdfExtractionError("unreadable_pdf", "The one-page PDF does not contain readable text.")
    return ExtractionResult(
        content_type="application/pdf",
        file_size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        page_count=page_count,
        extracted_text=normalized,
        extracted_fields=_extract_fields(normalized),
        extracted_at=datetime.now(timezone.utc),
    )
