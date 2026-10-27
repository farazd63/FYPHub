"""Deterministic, local extraction for one-page supervisor-request PDFs."""

from __future__ import annotations

import hashlib
import io
import re
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


@dataclass(frozen=True)
class ExtractionResult:
    content_type: str
    file_size: int
    sha256: str
    page_count: int
    extracted_text: str
    extracted_fields: dict[str, object]
    extracted_at: datetime


_FIELD_PATTERNS: dict[str, tuple[str, ...]] = {
    "title": (r"^proposal\s+title\s*[:\-]\s*(.+)$", r"^title\s*[:\-]\s*(.+)$"),
    "topic": (r"^(?:topic|area|research\s+area)\s*[:\-]\s*(.+)$",),
    "purpose": (r"^(?:problem\s+statement|problem|purpose|aim)\s*[:\-]\s*(.+)$",),
    "objectives": (r"^(?:objectives?|goals?)\s*[:\-]\s*(.+)$",),
    "methodology": (r"^(?:methodology|approach|methods?)\s*[:\-]\s*(.+)$",),
}


def _field(value: str | None, page: int = 1) -> dict[str, object]:
    if value is None:
        return {"value": None, "display": "Not detected in PDF", "source_page": None, "source": None}
    return {"value": value, "display": value, "source_page": page, "source": f"page {page}"}


def _extract_fields(text: str) -> dict[str, object]:
    fields: dict[str, object] = {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    matched_lines: set[int] = set()
    for name, patterns in _FIELD_PATTERNS.items():
        value: str | None = None
        for index, line in enumerate(lines):
            for pattern in patterns:
                match = re.match(pattern, line, flags=re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    matched_lines.add(index)
                    break
            if value:
                break
        fields[name] = _field(value)

    other = [
        {"value": line, "source_page": 1, "source": "page 1"}
        for index, line in enumerate(lines)
        if index not in matched_lines and not re.match(r"^(?:page|date)\s*[:\-]", line, flags=re.IGNORECASE)
    ]
    fields["other_sections"] = other
    fields["required_fields"] = ["title", "purpose"]
    fields["missing_required_fields"] = [name for name in ("title", "purpose") if not fields[name]["value"]]
    fields["warnings"] = [f"{name} was not detected in the PDF." for name in ("topic", "objectives", "methodology") if not fields[name]["value"]]
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
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip()).strip()
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
