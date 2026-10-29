"""Deterministic PDF/DOCX AST parsing with explicit measured unknowns."""

from __future__ import annotations

import io
import re
from statistics import median
from typing import Any

PT_TO_MM = 25.4 / 72
IN_TO_MM = 25.4


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _empty_ast(document_type: str) -> dict[str, Any]:
    return {"format": document_type, "pages": [], "page_geometry": {"size": "unknown", "width_pt": None, "height_pt": None, "pages": []}, "blocks": [], "paragraphs": [], "headings": [], "figures": [], "tables": [], "captions": [], "citations": [], "references": [], "section_word_counts": {}, "warnings": []}


def _normalise_text(value: str) -> str:
    value = value.replace("\u00ad", "")
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    return re.sub(r"\s*\n\s*", "\n", value).strip()


def _heading_level(text: str, style: str | None = None) -> int | None:
    if style and "heading" in style.casefold():
        match = re.search(r"(\d+)", style)
        return int(match.group(1)) if match else 1
    match = re.match(r"^(\d+(?:\.\d+)*)(?:[.)]|\s)\s*\S", text)
    return match.group(1).count(".") + 1 if match else None


def _citations(text: str) -> list[str]:
    return sorted(set(re.findall(r"\[[0-9]+\]|\([A-Z][A-Za-z-]+(?:,\s*\d{4})?\)", text)))


def _page_label(width_mm: float | None, height_mm: float | None) -> str | None:
    if width_mm is None or height_mm is None:
        return None
    short, long = sorted((width_mm, height_mm))
    if abs(short - 210) <= 3 and abs(long - 297) <= 3:
        return "A4"
    if abs(short - 215.9) <= 3 and abs(long - 279.4) <= 3:
        return "Letter"
    return "Custom"


def _page_label_pt(width_pt: float | None, height_pt: float | None) -> str | None:
    if width_pt is None or height_pt is None:
        return None
    short, long = sorted((width_pt, height_pt))
    if abs(short - 595.276) <= 3 and abs(long - 841.89) <= 3:
        return "A4"
    if abs(short - 612) <= 3 and abs(long - 792) <= 3:
        return "Letter"
    return "Custom"


def _length_to_points(value: Any) -> float | None:
    """Convert a python-docx length (EMU/twips-backed) to points."""
    if value is None:
        return None
    points = getattr(value, "pt", None)
    if points is not None:
        return float(points)
    inches = getattr(value, "inches", None)
    if inches is not None:
        return float(inches) * 72
    # python-docx Length values are EMU integers when no convenience
    # property is exposed by the installed version.
    return float(value) / 12700


def _add_pdf_metrics(ast: dict[str, Any], page_metrics: list[dict[str, Any]]) -> None:
    measurable = [item for item in page_metrics if item.get("content_bbox")]
    if not measurable:
        ast["margins"] = "unknown"
        ast["page_geometry"] = {"size": "unknown", "pages": page_metrics}
        return
    left = median(item["content_bbox"][0] for item in measurable)
    top = median(item["content_bbox"][1] for item in measurable)
    right = median(item["width"] - item["content_bbox"][2] for item in measurable)
    bottom = median(item["height"] - item["content_bbox"][3] for item in measurable)
    width_mm = median(item["width_mm"] for item in measurable)
    height_mm = median(item["height_mm"] for item in measurable)
    ast["margins"] = {"left_mm": round(left * PT_TO_MM, 2), "right_mm": round(right * PT_TO_MM, 2), "top_mm": round(top * PT_TO_MM, 2), "bottom_mm": round(bottom * PT_TO_MM, 2), "unit": "mm", "method": "median content bounding boxes across measurable pages", "pages": [{"page": item["page"], "left_mm": round(item["content_bbox"][0] * PT_TO_MM, 2), "right_mm": round((item["width"] - item["content_bbox"][2]) * PT_TO_MM, 2), "top_mm": round(item["content_bbox"][1] * PT_TO_MM, 2), "bottom_mm": round((item["height"] - item["content_bbox"][3]) * PT_TO_MM, 2)} for item in measurable]}
    ast["page_geometry"] = {"size": _page_label(width_mm, height_mm), "width_pt": round(width_mm / PT_TO_MM, 3), "height_pt": round(height_mm / PT_TO_MM, 3), "width_mm": round(width_mm, 2), "height_mm": round(height_mm, 2), "unit": "mm", "pages": page_metrics}


def parse_pdf(data: bytes) -> dict[str, Any]:
    ast = _empty_ast("PDF")
    try:
        import fitz  # type: ignore
    except ImportError:
        fitz = None
    if fitz is not None:
        try:
            document = fitz.open(stream=data, filetype="pdf")
            page_metrics: list[dict[str, Any]] = []
            line_gaps: list[float] = []
            paragraph_gaps: list[float] = []
            for page_number, page in enumerate(document, 1):
                blocks = page.get_text("dict").get("blocks", [])
                page_text = _normalise_text(page.get_text("text") or "")
                width, height = float(page.rect.width), float(page.rect.height)
                line_boxes: list[tuple[float, float, float, float]] = []
                page_lines: list[tuple[float, float, float]] = []
                ast["pages"].append({"page": page_number, "width": width, "height": height, "width_mm": round(width * PT_TO_MM, 2), "height_mm": round(height * PT_TO_MM, 2), "size": _page_label(width * PT_TO_MM, height * PT_TO_MM), "text": page_text[:20000]})
                ast["citations"].extend(_citations(page_text))
                for block in blocks:
                    if block.get("type") != 0:
                        continue
                    block_bbox = tuple(float(value) for value in block.get("bbox", (0, 0, 0, 0)))
                    for line in block.get("lines", []):
                        spans = line.get("spans", [])
                        text = _normalise_text("".join(str(span.get("text", "")) for span in spans))
                        if not text:
                            continue
                        line_bbox = tuple(float(value) for value in line.get("bbox", block_bbox))
                        line_boxes.append(line_bbox)
                        size = max((float(span.get("size", 0)) for span in spans), default=None)
                        family = next((span.get("font") for span in spans if span.get("font")), None)
                        origins = [
                            float(origin[1])
                            for span in spans
                            for origin in [span.get("origin")]
                            if isinstance(origin, (list, tuple)) and len(origin) > 1
                        ]
                        baseline = float(median(origins)) if origins else line_bbox[3]
                        page_lines.append((line_bbox[1], baseline, float(size or 0)))
                        item = {"text": text, "page": page_number, "font_family": family, "font_size": size, "bold": any("bold" in str(span.get("font", "")).casefold() for span in spans), "italic": any("italic" in str(span.get("font", "")).casefold() for span in spans), "bbox": list(line_bbox)}
                        ast["blocks"].append(item); ast["paragraphs"].append(item)
                        level = _heading_level(text)
                        if level is not None:
                            ast["headings"].append({"text": text, "level": level, "page": page_number})
                # Measure line and paragraph spacing from all text blocks on
                # this page, ordered by their vertical baseline.
                ordered_lines = sorted(page_lines, key=lambda item: item[1])
                for first, second in zip(ordered_lines, ordered_lines[1:]):
                    baseline_gap = second[1] - first[1]
                    if baseline_gap > 0:
                        line_gaps.append(round(baseline_gap, 2))
                    if second[0] - first[1] > 0 and first[2]:
                        paragraph_gaps.append(round((second[0] - first[1]) / first[2], 3))
                content_bbox = (min(box[0] for box in line_boxes), min(box[1] for box in line_boxes), max(box[2] for box in line_boxes), max(box[3] for box in line_boxes)) if line_boxes else None
                page_metrics.append({"page": page_number, "width": width, "height": height, "width_mm": width * PT_TO_MM, "height_mm": height * PT_TO_MM, "content_bbox": content_bbox})
            ast["citations"] = sorted(set(ast["citations"]))
            ast["references"] = [item["text"] for item in ast["paragraphs"] if re.match(r"^(references|bibliography)\b", item["text"], re.I)]
            _add_pdf_metrics(ast, page_metrics)
            if line_gaps:
                ast["line_spacing"] = round(median(line_gaps), 2)
            if paragraph_gaps:
                ast["paragraph_spacing"] = round(median(paragraph_gaps), 2)
            if not ast["pages"]:
                ast["warnings"].append(_warning("no_pages", "No PDF pages were detected."))
            return ast
        except Exception as error:
            ast["warnings"].append(_warning("pdf_parse_failed", f"PDF parsing failed safely: {type(error).__name__}."))
            return ast
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data), strict=False)
        for page_number, page in enumerate(reader.pages, 1):
            text = _normalise_text(page.extract_text() or "")
            width = float(page.mediabox.width) if page.mediabox else None
            height = float(page.mediabox.height) if page.mediabox else None
            width_mm = width * PT_TO_MM if width is not None else None
            height_mm = height * PT_TO_MM if height is not None else None
            ast["pages"].append({"page": page_number, "text": text[:20000], "width": width, "height": height, "width_mm": width_mm, "height_mm": height_mm, "size": _page_label(width_mm, height_mm)})
            ast["citations"].extend(_citations(text))
            for line in text.splitlines():
                line = _normalise_text(line)
                if not line:
                    continue
                item = {"text": line, "page": page_number, "font_family": None, "font_size": None, "bold": None, "italic": None}
                ast["blocks"].append(item); ast["paragraphs"].append(item)
                level = _heading_level(line)
                if level is not None:
                    ast["headings"].append({"text": line, "level": level, "page": page_number})
        ast["warnings"].append(_warning("geometry_unavailable", "Text geometry and font metrics are unavailable without the optional PDF geometry runtime."))
        return ast
    except Exception as error:
        ast["warnings"].append(_warning("pdf_parse_failed", f"PDF parsing failed safely: {type(error).__name__}."))
        return ast


def parse_docx(data: bytes) -> dict[str, Any]:
    ast = _empty_ast("DOCX")
    try:
        from docx import Document  # type: ignore
    except ImportError:
        ast["warnings"].append(_warning("python_docx_unavailable", "python-docx is unavailable; DOCX rules are unknown."))
        return ast
    try:
        document = Document(io.BytesIO(data))
        section_metrics = []
        for section in document.sections:
            width_mm = section.page_width.inches * IN_TO_MM if section.page_width else None
            height_mm = section.page_height.inches * IN_TO_MM if section.page_height else None
            width_pt = _length_to_points(section.page_width)
            height_pt = _length_to_points(section.page_height)
            section_metrics.append({"width_pt": round(width_pt, 3) if width_pt else None, "height_pt": round(height_pt, 3) if height_pt else None, "width_mm": round(width_mm, 2) if width_mm else None, "height_mm": round(height_mm, 2) if height_mm else None, "size": _page_label_pt(width_pt, height_pt), "margins": {"top_mm": round(section.top_margin.inches * IN_TO_MM, 2), "right_mm": round(section.right_margin.inches * IN_TO_MM, 2), "bottom_mm": round(section.bottom_margin.inches * IN_TO_MM, 2), "left_mm": round(section.left_margin.inches * IN_TO_MM, 2)}})
        ast["pages"] = [{"page": index, **item} for index, item in enumerate(section_metrics, 1)]
        first_section = section_metrics[0] if section_metrics else {}
        ast["page_geometry"] = {"size": first_section.get("size", "unknown"), "width_pt": first_section.get("width_pt"), "height_pt": first_section.get("height_pt"), "pages": ast["pages"]}
        ast["margins"] = section_metrics[0]["margins"] if len(section_metrics) == 1 else [item["margins"] for item in section_metrics]
        for paragraph in document.paragraphs:
            text = _normalise_text(paragraph.text)
            if not text:
                continue
            style = paragraph.style.name if paragraph.style else None
            runs = [run for run in paragraph.runs if run.text]
            line_spacing = paragraph.paragraph_format.line_spacing
            if hasattr(line_spacing, "pt"):
                line_spacing = line_spacing.pt
            elif not isinstance(line_spacing, (int, float, str, type(None))):
                line_spacing = None
            space_after = paragraph.paragraph_format.space_after
            paragraph_spacing = space_after.pt if space_after is not None and hasattr(space_after, "pt") else None
            style_font = paragraph.style.font if paragraph.style else None
            family = next((run.font.name for run in runs if run.font.name), None) or (style_font.name if style_font else None)
            size = next((_length_to_points(run.font.size) for run in runs if run.font.size), None) or (_length_to_points(style_font.size) if style_font and style_font.size else None)
            item = {"text": text, "page": 1, "style": style, "font_family": family, "font_size": size, "bold": any(run.bold for run in runs) if runs else None, "italic": any(run.italic for run in runs) if runs else None, "line_spacing": line_spacing, "paragraph_spacing": paragraph_spacing}
            ast["blocks"].append(item); ast["paragraphs"].append(item)
            level = _heading_level(text, style)
            if level is not None:
                ast["headings"].append({"text": text, "level": level, "page": 1, "style": style})
            if re.match(r"^(figure|table)\s+[0-9]+", text, re.I):
                ast["captions"].append({"text": text, "page": 1})
            ast["citations"].extend(_citations(text))
        for table in document.tables:
            ast["tables"].append({"rows": len(table.rows), "columns": len(table.columns)})
        ast["citations"] = sorted(set(ast["citations"]))
        ast["references"] = [item["text"] for item in ast["paragraphs"] if re.match(r"^(references|bibliography)\b", item["text"], re.I)]
        return ast
    except Exception as error:
        ast["warnings"].append(_warning("docx_parse_failed", f"DOCX parsing failed safely: {type(error).__name__}."))
        return ast


def parse_document(data: bytes, filename: str, mime_type: str | None = None) -> dict[str, Any]:
    suffix = filename.casefold().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "pdf" or mime_type == "application/pdf":
        return parse_pdf(data)
    if suffix == "docx" or mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return parse_docx(data)
    ast = _empty_ast(suffix.upper() or "UNKNOWN")
    ast["warnings"].append(_warning("unsupported_format", "Only PDF and DOCX documents are supported."))
    return ast
