"""Server-side document preview generation for inline browser viewing."""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from html import escape
from pathlib import Path

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


PREVIEW_CACHE_VERSION = "docx-preview-v1"


class DocumentPreviewError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class DocumentPreview:
    content: bytes
    filename: str
    media_type: str
    page_count: int
    conversion: str


def _pdf_page_count(data: bytes) -> int:
    try:
        import fitz

        document = fitz.open(stream=data, filetype="pdf")
        try:
            if not document.page_count:
                raise DocumentPreviewError("preview_empty", "The document contains no pages to preview.")
            return document.page_count
        finally:
            document.close()
    except DocumentPreviewError:
        raise
    except Exception as error:
        raise DocumentPreviewError("preview_invalid", "The document could not be rendered for preview.") from error


def _render_text_fallback(data: bytes, filename: str) -> bytes:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise DocumentPreviewError("preview_invalid", "The text document could not be rendered for preview.") from error
    stream = io.BytesIO()
    document = SimpleDocTemplate(stream, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    story = [Paragraph(escape(filename), styles["Title"]), Spacer(1, 12)]
    for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        story.append(Paragraph(escape(line) if line else "&nbsp;", styles["BodyText"]))
        story.append(Spacer(1, 4))
    document.build(story)
    return stream.getvalue()


def _render_docx_fallback(data: bytes, filename: str) -> bytes:
    """Text-preserving fallback used only when LibreOffice is unavailable."""
    try:
        document = Document(io.BytesIO(data))
    except Exception as error:
        raise DocumentPreviewError("preview_invalid", "The DOCX document could not be rendered for preview.") from error
    stream = io.BytesIO()
    pdf = SimpleDocTemplate(stream, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    story = [Paragraph(escape(filename), styles["Title"]), Spacer(1, 10)]
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            story.append(Spacer(1, 8))
            continue
        style_name = (getattr(getattr(paragraph, "style", None), "name", "") or "").casefold()
        style = styles["Heading2"] if style_name.startswith("heading") else styles["BodyText"]
        story.append(Paragraph(escape(text), style))
        story.append(Spacer(1, 5))
    for table in document.tables:
        rows = [[Paragraph(escape(cell.text.strip()), styles["BodyText"]) for cell in row.cells] for row in table.rows]
        if rows:
            story.append(Table(rows, style=TableStyle([["GRID", (0, 0), (-1, -1), 0.35, "#B8C5D6"], ["VALIGN", (0, 0), (-1, -1), "TOP"]])))
            story.append(Spacer(1, 8))
    pdf.build(story)
    return stream.getvalue()


def _converter() -> str | None:
    return shutil.which("libreoffice") or shutil.which("soffice")


def _convert_docx(data: bytes, source_path: Path, filename: str) -> tuple[bytes, str]:
    converter = _converter()
    if converter:
        try:
            with tempfile.TemporaryDirectory(prefix="fyphub-docx-preview-") as temporary:
                output_dir = Path(temporary) / "output"
                profile_dir = Path(temporary) / "profile"
                output_dir.mkdir()
                profile_dir.mkdir()
                command = [
                    converter,
                    "--headless",
                    "--norestore",
                    "--nodefault",
                    "--nofirststartwizard",
                    f"-env:UserInstallation={profile_dir.as_uri()}",
                    "--convert-to",
                    "pdf:writer_pdf_Export",
                    "--outdir",
                    str(output_dir),
                    str(source_path),
                ]
                completed = subprocess.run(command, capture_output=True, text=True, timeout=90, check=False, env={**os.environ, "HOME": temporary})
                converted = output_dir / f"{source_path.stem}.pdf"
                if completed.returncode == 0 and converted.is_file() and converted.stat().st_size:
                    return converted.read_bytes(), "libreoffice"
        except (OSError, subprocess.SubprocessError):
            pass
    return _render_docx_fallback(data, filename), "python-docx-reportlab-fallback"


def _cache_path(storage_root: Path, data: bytes, filename: str) -> Path:
    digest = hashlib.sha256(PREVIEW_CACHE_VERSION.encode() + b"\0" + filename.encode("utf-8", "ignore") + b"\0" + data).hexdigest()
    directory = storage_root / "module-3" / "preview-cache"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{digest}.pdf"


def _cache_write(path: Path, data: bytes) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def render_document_preview(source_path: Path, content_type: str | None, filename: str | None, storage_root: Path) -> DocumentPreview:
    """Return a PDF preview without changing the uploaded source file."""
    if not source_path.is_file():
        raise DocumentPreviewError("document_missing", "The original document is no longer available.")
    source_name = filename or source_path.name
    suffix = source_path.suffix.casefold()
    data = source_path.read_bytes()
    if not data:
        raise DocumentPreviewError("preview_empty", "The document is empty and cannot be previewed.")
    if suffix == ".pdf" or (content_type or "").casefold() == "application/pdf":
        return DocumentPreview(content=data, filename=source_name, media_type="application/pdf", page_count=_pdf_page_count(data), conversion="original-pdf")
    if suffix == ".docx" or "wordprocessingml.document" in (content_type or "").casefold():
        cache = _cache_path(storage_root, data, source_name)
        if cache.is_file() and cache.stat().st_size:
            converted = cache.read_bytes()
            return DocumentPreview(content=converted, filename=f"{Path(source_name).stem}.pdf", media_type="application/pdf", page_count=_pdf_page_count(converted), conversion="cached")
        converted, conversion = _convert_docx(data, source_path, source_name)
        _cache_write(cache, converted)
        return DocumentPreview(content=converted, filename=f"{Path(source_name).stem}.pdf", media_type="application/pdf", page_count=_pdf_page_count(converted), conversion=conversion)
    if suffix in {".txt", ".text", ".md"} or (content_type or "").casefold() in {"text/plain", "text/markdown"}:
        converted = _render_text_fallback(data, source_name)
        return DocumentPreview(content=converted, filename=f"{Path(source_name).stem}.pdf", media_type="application/pdf", page_count=_pdf_page_count(converted), conversion="text-reportlab-fallback")
    raise DocumentPreviewError("preview_unsupported", "This document type cannot be previewed in the application.")


__all__ = ["DocumentPreview", "DocumentPreviewError", "render_document_preview"]
