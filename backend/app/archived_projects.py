"""Authorized logical FYP archive management and deterministic knowledge search."""

import hashlib
from io import BytesIO
import os
import re
import uuid
from datetime import datetime
from pathlib import PurePath

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
import xlrd
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles, validate_mutating_origin
from .database import get_db
from .models import AcademicCycle, AdminAuditEvent, ArchiveImportBatch, ArchivedProject, ArchivedProjectDocument, ArchivedProjectDocumentType, User, UserRole

router = APIRouter(prefix="/api/v1/archived-projects")
admin_archive_router = APIRouter(prefix="/api/v1/admin/archive", tags=["archive-import"])
READ_ROLES = (UserRole.STUDENT, UserRole.SUPERVISOR, UserRole.COORDINATOR, UserRole.ADMIN)
ARCHIVE_MAX_BYTES = int(os.getenv("FYPHUB_ARCHIVE_MAX_BYTES", str(10 * 1024 * 1024)))
DOCUMENT_TYPES = {item.value for item in ArchivedProjectDocumentType}
ARCHIVE_METADATA_FIELDS = ("title", "abstract_summary", "keywords", "academic_year", "department_program", "project_scope", "completion_stage", "implemented_scope", "remaining_gaps", "future_work", "supervisor_display_reference", "source_label", "source_metadata")

def _cell_text(value: object) -> str:
    return "" if value is None else str(value)


_EXCEL_ERROR_VALUES = {"#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NUM!", "#NULL!"}


def _clean_cell(value: object, *, is_formula: bool = False) -> str:
    """Return only literal cell content; discard formulas and Excel errors."""
    if is_formula:
        return ""
    text = _cell_text(value)
    stripped = text.strip()
    return "" if not stripped or stripped.upper() in _EXCEL_ERROR_VALUES else stripped


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _is_email_value(value: str) -> bool:
    return bool(_EMAIL_RE.fullmatch(value.strip()))


def _last_content_row(clean_rows: list[list[str]], start: int) -> int:
    """Find the true end of a worksheet, preferring the last literal email row.

    Excel often keeps formatting, copied formulas, or cached display values far
    below the real data. Those rows must never become archive records. If an
    email column/value exists, it is the authoritative end marker; otherwise
    we fall back to the last row containing a literal value.
    """
    if start >= len(clean_rows):
        return start - 1
    email_header_indexes = {
        index for index, value in enumerate(clean_rows[start])
        if "email" in re.sub(r"[^a-z0-9]", "", value.casefold())
    }
    email_rows: list[int] = []
    for row_number in range(start, len(clean_rows)):
        row = clean_rows[row_number]
        if any(_is_email_value(row[index]) for index in email_header_indexes if index < len(row)):
            email_rows.append(row_number)
        elif not email_header_indexes and any(_is_email_value(value) for value in row):
            email_rows.append(row_number)
    if email_rows:
        return email_rows[-1]
    return max((row_number for row_number in range(start, len(clean_rows)) if any(clean_rows[row_number])), default=start - 1)


def _xls_value(cell, datemode: int):
    if cell.ctype == xlrd.XL_CELL_DATE:
        return xlrd.xldate_as_datetime(cell.value, datemode)
    if cell.ctype == xlrd.XL_CELL_BOOLEAN:
        return bool(cell.value)
    if cell.ctype == xlrd.XL_CELL_ERROR:
        return xlrd.error_text_from_code.get(cell.value, str(cell.value))
    return cell.value


def parse_archive_workbook(content: bytes, cycle: AcademicCycle, *, header_row: int | None = None, has_headers: bool = True) -> dict:
    """Extract every populated column without imposing an archive schema."""
    if len(content) > ARCHIVE_MAX_BYTES:
        raise _error("archive_file_too_large", "The Excel file exceeds the configured size limit.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    workbook = None
    try:
        if content.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
            workbook = xlrd.open_workbook(file_contents=content)
            sheets = [
                (
                    sheet.name,
                    [[_xls_value(sheet.cell(row, column), workbook.datemode) for column in range(sheet.ncols)] for row in range(sheet.nrows)],
                    [[_xls_value(sheet.cell(row, column), workbook.datemode) for column in range(sheet.ncols)] for row in range(sheet.nrows)],
                    [[sheet.cell(row, column).ctype == getattr(xlrd, "XL_CELL_FORMULA", 6) for column in range(sheet.ncols)] for row in range(sheet.nrows)],
                )
                for sheet in workbook.sheets()
            ]
        else:
            # Read the workbook twice: the formula workbook gives us the original
            # shape, while the data-only workbook gives us Excel's displayed
            # (cached) values. Formula text is not useful archive content and
            # unevaluated formulas are treated as blank cells.
            workbook = load_workbook(BytesIO(content), read_only=True, data_only=False)
            value_workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
            try:
                sheets = [
                    (
                        sheet.title,
                        list(sheet.iter_rows(values_only=True)),
                        list(value_sheet.iter_rows(values_only=True)),
                        [[isinstance(value, str) and value.startswith("=") for value in row] for row in sheet.iter_rows(values_only=True)],
                    )
                    for sheet, value_sheet in zip(workbook.worksheets, value_workbook.worksheets)
                ]
            finally:
                value_workbook.close()
    except Exception as error:
        raise _error("invalid_archive_workbook", "Upload a readable .xls or .xlsx workbook.", status.HTTP_422_UNPROCESSABLE_CONTENT) from error
    finally:
        if workbook is not None:
            if hasattr(workbook, "close"):
                workbook.close()
            elif hasattr(workbook, "release_resources"):
                workbook.release_resources()
    valid = []
    extracted_sheets = []
    skipped_rows = 0
    for sheet_name, rows, display_rows, formula_rows in sheets:
        clean_display_rows = [
            [_clean_cell(value, is_formula=column < len(formula_rows[row]) and formula_rows[row][column]) for column, value in enumerate(values)]
            for row, values in enumerate(display_rows)
        ]
        populated = [index for index, row in enumerate(clean_display_rows) if any(value != "" for value in row)]
        if not populated:
            continue
        start = header_row - 1 if header_row is not None else populated[0]
        if start >= len(rows):
            continue
        end = _last_content_row(clean_display_rows, start)
        if end < start:
            continue
        # Include columns which contain data even when their header is blank,
        # but only within the real data boundary (never formatting residue).
        indexes = [index for index in range(max(len(row) for row in clean_display_rows[start:end + 1]))
                   if any(index < len(row) and row[index] != "" for row in clean_display_rows[start:end + 1])]
        columns = [{"key": get_column_letter(index + 1), "label": clean_display_rows[start][index] if has_headers and index < len(clean_display_rows[start]) else ""} for index in indexes]
        extracted_sheets.append({"name": sheet_name, "columns": columns, "header_row": start + 1 if has_headers else None})
        # Report discarded rows for diagnostics, but never turn them into
        # records. Formula rows are counted even when they occur after the
        # last email boundary; formatted-but-empty rows remain uncounted.
        for row_number in range(start + (1 if has_headers else 0), len(clean_display_rows)):
            if not any(clean_display_rows[row_number]) and row_number < len(rows) and any(value not in (None, "") for value in rows[row_number]):
                skipped_rows += 1
        for row_number in range(start + (1 if has_headers else 0), end + 1):
            values = clean_display_rows[row_number]
            if not any(value != "" for value in values):
                continue
            data = {column["key"]: values[index] if index < len(values) else "" for column, index in zip(columns, indexes)}
            valid.append({"row": row_number + 1, "sheet": sheet_name, "columns": columns, "data": data})
    if not extracted_sheets:
        raise _error("empty_archive_workbook", "The workbook contains no content at the selected row.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return {"valid_rows": valid, "invalid_rows": [], "total_rows": len(valid), "skipped_rows": skipped_rows, "sheets": extracted_sheets,
            "cycle": {"id": cycle.id, "academic_year": cycle.academic_year, "session": cycle.session}}


def _column_token(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _mapped_value(columns: list[dict], cells: dict[str, str], *aliases: str) -> str:
    wanted = {_column_token(alias) for alias in aliases}
    for column in columns:
        if _column_token(column.get("label")) in wanted:
            value = cells.get(column["key"], "").strip()
            if value:
                return value
    return ""


_PROJECT_TITLE_ALIASES = (
    "title", "project title", "project name", "fyp title", "fyp project title",
    "research title", "research project title", "project topic", "project",
    "topic", "proposed title", "proposal title",
)


def _project_title(columns: list[dict], cells: dict[str, str]) -> str:
    """Read a project title only from an explicit project-title column.

    The old importer used the first populated cell as a fallback.  That made a
    student name (or a registration number) become the archived project title
    whenever the workbook's first column was a member column.  A title is now
    deliberately empty when the workbook does not identify one.
    """
    explicit = _mapped_value(columns, cells, *_PROJECT_TITLE_ALIASES)
    if explicit:
        return explicit[:255]
    for column in columns:
        token = _column_token(column.get("label"))
        if not token or any(part in token for part in ("student", "member", "registration", "email", "supervisor", "leader")):
            continue
        if "projecttitle" in token or "projectname" in token or "fyptitle" in token or "proposaltitle" in token:
            value = str(cells.get(column["key"], "") or "").strip()
            if value:
                return value[:255]
    return ""


def _column_values(columns: list[dict], cells: dict[str, str], predicate) -> list[str]:
    values: list[str] = []
    for column in columns:
        if predicate(_column_token(column.get("label"))):
            value = str(cells.get(column["key"], "") or "").strip()
            if value:
                values.append(value)
    return values


def _member_rows(columns: list[dict], cells: dict[str, str]) -> list[dict]:
    """Extract member data from one source row without treating it as a project."""
    title_keys = {column["key"] for column in columns if _column_token(column.get("label")) in {_column_token(alias) for alias in _PROJECT_TITLE_ALIASES}}
    name_columns = [column for column in columns if column["key"] not in title_keys and any(token in _column_token(column.get("label")) for token in ("member", "student", "fullname", "studentname", "membername", "groupmember"))]
    # A workbook often has a simple "Name" heading for a member table.  It is
    # safe to use it only when the sheet also has a registration/email column.
    has_identity_column = any(token in _column_token(column.get("label")) for column in columns for token in ("registration", "regno", "rollno", "email"))
    if not name_columns and has_identity_column:
        name_columns = [column for column in columns if column["key"] not in title_keys and _column_token(column.get("label")) in {"name", "fullname"}]
    registration_values = _column_values(columns, cells, lambda token: any(part in token for part in ("registration", "registrationnumber", "regno", "rollno", "studentid")))
    email_values = _column_values(columns, cells, lambda token: "email" in token)
    designation_values = _column_values(columns, cells, lambda token: any(part in token for part in ("designation", "role", "membertype")))
    rows: list[dict] = []
    for index, column in enumerate(name_columns):
        name = str(cells.get(column["key"], "") or "").strip()
        if not name:
            continue
        rows.append({
            "name": name,
            "registration_number": registration_values[index] if index < len(registration_values) else None,
            "email": email_values[index] if index < len(email_values) else None,
            "designation": designation_values[index] if index < len(designation_values) else None,
        })
    leader = _mapped_value(columns, cells, "group leader", "group leader name", "leader", "leader name")
    leader_registration = _mapped_value(columns, cells, "group leader registration number", "leader registration number", "leader registration", "registration number")
    if leader and not any(_same_member(leader, item.get("name"), leader_registration, item.get("registration_number"), None, item.get("email")) for item in rows):
        rows.insert(0, {"name": leader, "registration_number": leader_registration or None, "email": email_values[0] if email_values else None, "designation": "Leader"})
    return rows


def _same_member(name_a: str | None, name_b: str | None, registration_a: str | None = None, registration_b: str | None = None, email_a: str | None = None, email_b: str | None = None) -> bool:
    if registration_a and registration_b and normalize_title(registration_a) == normalize_title(registration_b):
        return True
    if email_a and email_b and email_a.casefold().strip() == email_b.casefold().strip():
        return True
    return bool(name_a and name_b and normalize_title(name_a) == normalize_title(name_b))


def _merge_member_values(existing: list[dict], incoming: list[dict]) -> list[dict]:
    merged = [dict(item) for item in existing if isinstance(item, dict) and item.get("name")]
    for candidate in incoming:
        if not candidate.get("name"):
            continue
        match = next((item for item in merged if _same_member(
            candidate.get("name"), item.get("name"), candidate.get("registration_number"), item.get("registration_number"), candidate.get("email"), item.get("email"))), None)
        if match is None:
            merged.append({key: value for key, value in candidate.items() if value not in (None, "")})
        else:
            for key, value in candidate.items():
                if value not in (None, "") and not match.get(key):
                    match[key] = value
    return merged


def _first_non_empty(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _unique_text(values: list[object]) -> str:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        token = normalize_title(text)
        if text and token not in seen:
            seen.add(token)
            result.append(text)
    return "\n".join(result)


def _import_display(columns: list[dict], cells: dict[str, str]) -> tuple[str, str]:
    title = _project_title(columns, cells)
    summary = _mapped_value(columns, cells, "abstract", "summary", "abstract summary", "description", "project description")
    return title[:255], summary


def _apply_imported_cells(project: ArchivedProject, columns: list[dict], cells: dict[str, str]) -> None:
    """Apply an edited imported row while preserving its original Excel columns."""
    title, summary = _import_display(columns, cells)
    group_name = _mapped_value(columns, cells, "group", "group name", "team", "team name")
    leader_name = _mapped_value(columns, cells, "group leader", "group leader name", "leader", "leader name")
    supervisor = _mapped_value(columns, cells, "supervisor", "supervisor name", "advisor")
    domain = _mapped_value(columns, cells, "domain", "category", "project category", "department", "department/program")
    technologies = _mapped_value(columns, cells, "technologies", "technologies used", "tools", "technology")
    status_value = _mapped_value(columns, cells, "project status", "status")
    completion_raw = _mapped_value(columns, cells, "completion percentage", "completion", "progress")
    completion = None
    if completion_raw:
        match = re.search(r"-?\d+(?:\.\d+)?", completion_raw)
        if match:
            completion = max(0, min(100, int(float(match.group(0)))))
    registration = _mapped_value(columns, cells, "group leader registration number", "leader registration number", "registration number")
    members = _member_rows(columns, cells)
    project.title = (title or project.title)[:255]
    project.normalized_title = normalize_title(project.title)
    project.abstract_summary = summary
    project.academic_year = _mapped_value(columns, cells, "academic year", "year") or project.academic_year
    project.session_name = _mapped_value(columns, cells, "session", "semester") or project.session_name
    project.department_program = domain
    project.project_scope = domain
    project.group_name = group_name or None
    project.group_leader_name = leader_name or None
    project.group_leader_registration_number = registration or None
    if members:
        project.group_members = _merge_member_values(project.group_members or [], members)
    project.supervisor_name = supervisor or None
    project.supervisor_display_reference = supervisor or None
    project.project_code = _mapped_value(columns, cells, "project code", "code") or None
    project.problem_statement = _mapped_value(columns, cells, "problem statement", "problem") or None
    project.objectives = _mapped_value(columns, cells, "objectives", "objective") or None
    project.methodology = _mapped_value(columns, cells, "methodology", "method") or None
    project.technologies_used = technologies or None
    project.main_features = _mapped_value(columns, cells, "main features", "features") or None
    project.project_status = status_value or None
    project.completion_stage = status_value
    project.completion_percentage = completion
    project.outcomes_results = _mapped_value(columns, cells, "outcomes", "results", "outcomes/results") or None
    project.normalized_group_name = normalize_title(group_name or "")


def _archive_import_project(item: dict, cycle: AcademicCycle, batch_id: str | None = None) -> ArchivedProject:
    """Build one archive parent from one Excel row.

    The confirm endpoint normally calls :func:`_archive_import_group`; this
    helper remains useful for preview/tests and intentionally refuses to invent
    a title when the workbook has no project-title column.
    """
    columns = item["columns"]
    cells = item["data"]
    title, summary = _import_display(columns, cells)
    group_name = _mapped_value(columns, cells, "group", "group name", "team", "team name")
    leader_name = _mapped_value(columns, cells, "group leader", "group leader name", "leader", "leader name")
    supervisor = _mapped_value(columns, cells, "supervisor", "supervisor name", "advisor")
    domain = _mapped_value(columns, cells, "domain", "category", "project category", "department", "department/program")
    technologies = _mapped_value(columns, cells, "technologies", "technologies used", "tools", "technology")
    status_value = _mapped_value(columns, cells, "project status", "status")
    completion_raw = _mapped_value(columns, cells, "completion percentage", "completion", "progress")
    completion = None
    if completion_raw:
        match = re.search(r"-?\d+(?:\.\d+)?", completion_raw)
        if match:
            completion = max(0, min(100, int(float(match.group(0)))))
    registration = _mapped_value(columns, cells, "group leader registration number", "leader registration number", "registration number")
    group_members = _member_rows(columns, cells)
    stable_group = group_name or ""
    return ArchivedProject(
        title=title, normalized_title=normalize_title(title) if batch_id else f"excel {uuid.uuid4().hex}", normalized_group_name=normalize_title(stable_group), group_name=group_name or None,
        abstract_summary=summary, keywords=[], academic_cycle_id=cycle.id, academic_year=str(cycle.academic_year),
        department_program=domain, project_scope=domain, completion_stage=status_value or "", implemented_scope="",
        remaining_gaps="", future_work="", supervisor_display_reference=supervisor or None, source_label="EXCEL_IMPORT",
        source_metadata={"imported": True, "batch_id": batch_id, "sheet": item["sheet"], "row": item["row"], "columns": columns, "cells": cells, "source_row_start": item["row"], "source_row_end": item["row"], "source_rows": [{"sheet": item["sheet"], "row": item["row"], "cells": cells}]},
        project_code=_mapped_value(columns, cells, "project code", "code" ) or None,
        group_leader_name=leader_name or None, group_leader_registration_number=registration or None,
        group_members=group_members, supervisor_name=supervisor or None, session_name=cycle.session,
        problem_statement=_mapped_value(columns, cells, "problem statement", "problem") or None,
        objectives=_mapped_value(columns, cells, "objectives", "objective") or None,
        methodology=_mapped_value(columns, cells, "methodology", "method") or None,
        technologies_used=technologies or None, project_status=status_value or None, completion_percentage=completion,
        outcomes_results=_mapped_value(columns, cells, "outcomes", "results", "outcomes/results") or None,
        is_visible_to_students=True,
    )


def _resolved_import_rows(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Forward-fill merged Excel cells and return rows plus safe orphan rows."""
    resolved: list[dict] = []
    orphans: list[dict] = []
    current_by_sheet: dict[str, dict[str, object]] = {}
    for item in items:
        columns = item["columns"]
        cells = dict(item["data"])
        title, summary = _import_display(columns, cells)
        sheet = item.get("sheet", "")
        state = current_by_sheet.setdefault(sheet, {"title": "", "group": "", "supervisor": "", "summary": "", "block": 0})
        group = _mapped_value(columns, cells, "group", "group name", "team", "team name")
        supervisor = _mapped_value(columns, cells, "supervisor", "supervisor name", "advisor")
        if title:
            same_project_block = normalize_title(title) == normalize_title(state["title"])
            if same_project_block and not group:
                # Repeated explicit titles with no group are ambiguous source
                # blocks.  Keep them separate rather than merging unrelated
                # teams; blank-title member rows continue the current block.
                state["block"] = int(state["block"]) + 1
            state["title"] = title
            # A new title starts a new source block.  Forward-fill group and
            # supervisor only for continuation rows (blank title) or repeated
            # title rows; never leak the previous project's group into a new
            # project whose group cell is blank.
            if not same_project_block:
                state["group"] = ""
                state["supervisor"] = ""
                state["summary"] = ""
        elif not state["title"]:
            orphans.append(item)
            continue
        if summary:
            state["summary"] = summary
        if group:
            state["group"] = group
        if supervisor:
            state["supervisor"] = supervisor
        enriched = dict(item)
        enriched["resolved_title"] = state["title"]
        enriched["resolved_group"] = group or state["group"]
        enriched["resolved_supervisor"] = supervisor or state["supervisor"]
        enriched["resolved_summary"] = summary or state["summary"]
        enriched["resolved_block"] = state["block"]
        resolved.append(enriched)
    return resolved, orphans


def _merge_source_cells(items: list[dict]) -> tuple[list[dict], dict[str, str]]:
    """Preserve all original columns while exposing a single editable value per key."""
    columns: list[dict] = []
    by_key: dict[str, dict] = {}
    values: dict[str, list[str]] = {}
    for item in items:
        for column in item["columns"]:
            key = column["key"]
            if key not in by_key:
                by_key[key] = {"key": key, "label": column.get("label", "")}
                columns.append(by_key[key])
                values[key] = []
        for key, value in item["data"].items():
            text = str(value or "").strip()
            if text and text not in values.setdefault(key, []):
                values[key].append(text)
    return columns, {key: "\n".join(value_list) for key, value_list in values.items()}


def _group_mapped_value(items: list[dict], *aliases: str) -> str:
    return _first_non_empty(*(_mapped_value(item["columns"], item["data"], *aliases) for item in items))


def _import_row_errors(item: dict) -> list[str]:
    errors: list[str] = []
    for column in item.get("columns", []):
        label = _column_token(column.get("label"))
        value = str(item.get("data", {}).get(column["key"], "") or "").strip()
        if value and "email" in label and not _is_email_value(value):
            errors.append(f"Invalid email in {column.get('label') or column['key']}")
    return errors


def _archive_import_group(items: list[dict], cycle: AcademicCycle, batch_id: str | None = None) -> ArchivedProject:
    """Create one parent archive entity for all rows sharing one safe key."""
    first = items[0]
    project = _archive_import_project({**first, "data": {**first["data"], **{}}}, cycle, batch_id=batch_id)
    title = next((item.get("resolved_title") for item in items if item.get("resolved_title")), project.title)
    group = next((item.get("resolved_group") for item in items if item.get("resolved_group")), "")
    supervisor = next((item.get("resolved_supervisor") for item in items if item.get("resolved_supervisor")), project.supervisor_name or "")
    summaries = [item.get("resolved_summary") or _import_display(item["columns"], item["data"])[1] for item in items]
    columns, cells = _merge_source_cells(items)
    members: list[dict] = []
    for item in items:
        members = _merge_member_values(members, _member_rows(item["columns"], item["data"]))
    # Forward-filled values must also be represented in the structured parent.
    project.title = title[:255]
    project.normalized_title = normalize_title(project.title)
    project.group_name = group or None
    project.normalized_group_name = normalize_title(group) or f"__source_block_{first.get('resolved_block', first.get('row', 'unknown'))}"
    project.supervisor_name = supervisor or None
    project.supervisor_display_reference = supervisor or None
    project.abstract_summary = _unique_text(summaries)
    project.department_program = _group_mapped_value(items, "domain", "category", "project category", "department", "department/program") or project.department_program
    project.project_scope = project.department_program
    project.project_code = _group_mapped_value(items, "project code", "code") or project.project_code
    project.problem_statement = _group_mapped_value(items, "problem statement", "problem") or project.problem_statement
    project.objectives = _group_mapped_value(items, "objectives", "objective") or project.objectives
    project.methodology = _group_mapped_value(items, "methodology", "method") or project.methodology
    project.technologies_used = _group_mapped_value(items, "technologies", "technologies used", "tools", "technology") or project.technologies_used
    project.main_features = _group_mapped_value(items, "main features", "features") or project.main_features
    project.project_status = _group_mapped_value(items, "project status", "status") or project.project_status
    project.completion_stage = project.project_status or project.completion_stage
    project.outcomes_results = _group_mapped_value(items, "outcomes", "results", "outcomes/results") or project.outcomes_results
    completion_value = _group_mapped_value(items, "completion percentage", "completion", "progress")
    if completion_value:
        match = re.search(r"-?\d+(?:\.\d+)?", completion_value)
        if match:
            project.completion_percentage = max(0, min(100, int(float(match.group(0)))))
    project.group_members = members
    project.group_leader_name = next((item.get("name") for item in members if str(item.get("designation") or "").casefold() == "leader"), members[0].get("name") if members else None)
    project.group_leader_registration_number = next((item.get("registration_number") for item in members if item.get("name") == project.group_leader_name), None)
    project.source_row_number = min(item["row"] for item in items)
    project.source_metadata = {
        "imported": True, "batch_id": batch_id, "sheet": first.get("sheet"),
        "row": project.source_row_number, "columns": columns, "cells": cells,
        "source_row_start": min(item["row"] for item in items),
        "source_row_end": max(item["row"] for item in items),
        "source_rows": [{"sheet": item.get("sheet"), "row": item["row"], "cells": item["data"]} for item in items],
    }
    return project


def _import_group_key(item: dict, cycle: AcademicCycle) -> tuple[int, str, str]:
    group = normalize_title(item.get("resolved_group") or "")
    if not group:
        group = f"__source_block_{item.get('resolved_block', item.get('row', 'unknown'))}"
    return (cycle.id, normalize_title(item.get("resolved_title") or item.get("title") or ""), group)


def _merge_imported_project(target: ArchivedProject, incoming: ArchivedProject) -> int:
    """Merge one grouped import into an existing project without overwriting data."""
    target.group_members = _merge_member_values(target.group_members or [], incoming.group_members or [])
    for field in ("abstract_summary", "department_program", "project_scope", "completion_stage", "implemented_scope", "remaining_gaps", "future_work", "group_name", "supervisor_name", "supervisor_display_reference", "project_code", "group_leader_name", "group_leader_registration_number", "session_name", "problem_statement", "objectives", "methodology", "technologies_used", "main_features", "project_status", "completion_percentage", "outcomes_results"):
        if getattr(target, field, None) in (None, "", 0) and getattr(incoming, field, None) not in (None, "", 0):
            setattr(target, field, getattr(incoming, field))
    if not target.normalized_group_name and incoming.normalized_group_name:
        target.normalized_group_name = incoming.normalized_group_name
    existing_metadata = target.source_metadata or {}
    incoming_metadata = incoming.source_metadata or {}
    columns, cells = _merge_source_cells([
        {"columns": existing_metadata.get("columns", []), "data": existing_metadata.get("cells", {})},
        {"columns": incoming_metadata.get("columns", []), "data": incoming_metadata.get("cells", {})},
    ])
    rows = list(existing_metadata.get("source_rows", [])) + list(incoming_metadata.get("source_rows", []))
    target.source_metadata = {
        **existing_metadata, "columns": columns, "cells": cells,
        "source_rows": rows,
        "source_row_start": min([row.get("row") for row in rows if row.get("row")] or [target.source_row_number or 0]),
        "source_row_end": max([row.get("row") for row in rows if row.get("row")] or [target.source_row_number or 0]),
    }
    return len(target.group_members or [])


def normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.casefold())).strip()


def clean_filename(value: str) -> str:
    name = PurePath(value.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name[:255] or "archive-document.pdf"


class ArchiveCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=255)
    abstract_summary: str = Field(min_length=1, max_length=10000)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    academic_cycle_id: int | None = Field(default=None, gt=0)
    academic_year: str = Field(min_length=1, max_length=64)
    department_program: str = Field(min_length=1, max_length=255)
    project_scope: str = Field(min_length=1, max_length=255)
    completion_stage: str = Field(min_length=1, max_length=100)
    implemented_scope: str = Field(min_length=1, max_length=10000)
    remaining_gaps: str = Field(min_length=1, max_length=10000)
    future_work: str = Field(min_length=1, max_length=10000)
    supervisor_display_reference: str | None = Field(default=None, max_length=255)
    source_label: str = Field(min_length=1, max_length=64)
    source_metadata: dict = Field(default_factory=dict)

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, values: list[str]) -> list[str]:
        cleaned = [item.strip() for item in values if item.strip()]
        if any(len(item) > 100 for item in cleaned):
            raise ValueError("Each keyword must be 100 characters or fewer.")
        return list(dict.fromkeys(cleaned))


class ArchiveUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=255)
    abstract_summary: str | None = Field(default=None, min_length=1, max_length=10000)
    keywords: list[str] | None = Field(default=None, max_length=30)
    academic_year: str | None = Field(default=None, min_length=1, max_length=64)
    department_program: str | None = Field(default=None, min_length=1, max_length=255)
    project_scope: str | None = Field(default=None, min_length=1, max_length=255)
    completion_stage: str | None = Field(default=None, min_length=1, max_length=100)
    implemented_scope: str | None = Field(default=None, min_length=1, max_length=10000)
    remaining_gaps: str | None = Field(default=None, min_length=1, max_length=10000)
    future_work: str | None = Field(default=None, min_length=1, max_length=10000)
    supervisor_display_reference: str | None = Field(default=None, max_length=255)
    source_label: str | None = Field(default=None, min_length=1, max_length=64)
    source_metadata: dict | None = None

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return list(dict.fromkeys(item.strip() for item in values if item.strip()))


def _error(code: str, message: str, code_status: int = status.HTTP_409_CONFLICT) -> HTTPException:
    return HTTPException(code_status, detail={"code": code, "message": message})


def _audit(session: Session, actor: User, project: ArchivedProject, action: str, changed: dict | None = None) -> None:
    from .main import add_admin_audit_event

    add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type="ARCHIVED_PROJECT", target_id=project.id, action=action, changed_values=changed or {})


def _document_out(document: ArchivedProjectDocument) -> dict:
    return {"id": document.id, "document_type": document.document_type, "display_name": document.display_name, "file_hash": document.file_hash, "mime_type": document.mime_type, "file_size": document.file_size, "version": document.version, "created_at": document.created_at, "is_active": document.is_active, "document_url": f"/api/v1/archived-projects/{document.archived_project_id}/documents/{document.id}"}


def _project_out(session: Session, project: ArchivedProject, *, include_history: bool = False, actor: User | None = None) -> dict:
    statement = select(ArchivedProjectDocument).where(ArchivedProjectDocument.archived_project_id == project.id)
    if not include_history:
        statement = statement.where(ArchivedProjectDocument.is_active.is_(True))
    documents = session.scalars(statement.order_by(ArchivedProjectDocument.document_type, ArchivedProjectDocument.version.desc())).all()
    public = actor is not None and actor.role == UserRole.STUDENT
    public_members = [{"name": member.get("name"), "full_name": member.get("full_name") or member.get("name"), "registration_number": member.get("registration_number"), "email": member.get("email"), "designation": member.get("designation")} for member in (project.group_members or []) if isinstance(member, dict)]
    source_metadata = {} if public else (project.source_metadata or {})
    return {"id": project.id, "title": project.title, "project_title": project.title, "normalized_title": project.normalized_title, "abstract_summary": project.abstract_summary, "keywords": project.keywords or [], "academic_cycle_id": project.academic_cycle_id, "academic_year": project.academic_year, "session": project.session_name, "department_program": project.department_program, "domain": project.department_program, "project_scope": project.project_scope, "group_name": project.group_name or project.group_leader_name, "completion_stage": project.completion_stage, "implemented_scope": project.implemented_scope, "remaining_gaps": project.remaining_gaps, "future_work": project.future_work, "supervisor_display_reference": project.supervisor_display_reference, "source_label": project.source_label, "source_batch_id": None if public else project.source_batch_id, "source_row_number": None if public else project.source_row_number, "source_row_start": None if public else source_metadata.get("source_row_start"), "source_row_end": None if public else source_metadata.get("source_row_end"), "source_metadata": source_metadata, "project_code": project.project_code, "group_leader_name": project.group_leader_name, "group_leader_registration_number": None if public else project.group_leader_registration_number, "group_members": public_members if public else (project.group_members or []), "members": public_members if public else (project.group_members or []), "supervisor_name": project.supervisor_name, "supervisor": project.supervisor_name, "problem_statement": project.problem_statement, "objectives": project.objectives, "methodology": project.methodology, "technologies_used": project.technologies_used, "main_features": project.main_features, "project_status": project.project_status, "completion_percentage": project.completion_percentage, "outcomes_results": project.outcomes_results, "repository_url": project.repository_url, "report_url": project.report_url, "presentation_url": project.presentation_url, "external_reference": project.external_reference, "notes": project.notes, "is_visible_to_students": project.is_visible_to_students, "created_at": project.created_at, "updated_at": project.updated_at, "archived_at": project.archived_at, "is_active": project.is_active, "documents": [_document_out(item) for item in documents]}


def _active_project(session: Session, project_id: int, actor: User | None = None) -> ArchivedProject:
    project = session.scalar(select(ArchivedProject).where(ArchivedProject.id == project_id, ArchivedProject.is_active.is_(True)))
    if project is None or (actor is not None and actor.role == UserRole.STUDENT and not project.is_visible_to_students):
        raise _error("archive_not_found", "Archived project was not found.", status.HTTP_404_NOT_FOUND)
    return project


def _metadata_snapshot(project: ArchivedProject) -> dict:
    return {field: list(getattr(project, field)) if field == "keywords" else getattr(project, field) for field in ARCHIVE_METADATA_FIELDS}


def _validate_document(file: UploadFile, content: bytes) -> str:
    if file.content_type != "application/pdf" or not (file.filename or "").lower().endswith(".pdf"):
        raise _error("invalid_document_type", "Archive documents must be PDF files.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if not content or len(content) > ARCHIVE_MAX_BYTES:
        raise _error("document_size_invalid", "The archive PDF is empty or exceeds the configured size limit.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if not content.startswith(b"%PDF"):
        raise _error("invalid_pdf", "The uploaded archive file is not a readable PDF.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return clean_filename(file.filename or "archive-document.pdf")


def _next_version(session: Session, project_id: int, document_type: str) -> int:
    current = session.scalar(select(func.max(ArchivedProjectDocument.version)).where(ArchivedProjectDocument.archived_project_id == project_id, ArchivedProjectDocument.document_type == document_type))
    return int(current or 0) + 1


@router.get("/search")
def search_archives(q: str | None = Query(default=None, max_length=255), academic_year: str | None = Query(default=None, max_length=64), session_name: str | None = Query(default=None, max_length=16), department: str | None = Query(default=None, max_length=255), supervisor: str | None = Query(default=None, max_length=255), technology: str | None = Query(default=None, max_length=255), project_scope: str | None = Query(default=None, max_length=255), completion_stage: str | None = Query(default=None, max_length=100), _: User = Depends(require_roles(*READ_ROLES)), session: Session = Depends(get_db)):
    statement = select(ArchivedProject).where(ArchivedProject.is_active.is_(True), ArchivedProject.is_visible_to_students.is_(True))
    if academic_year:
        statement = statement.where(ArchivedProject.academic_year == academic_year.strip())
    if session_name:
        statement = statement.where(ArchivedProject.session_name == session_name.strip().upper())
    if department:
        statement = statement.where(ArchivedProject.department_program.ilike(f"%{department.strip()}%"))
    if supervisor:
        statement = statement.where(ArchivedProject.supervisor_name.ilike(f"%{supervisor.strip()}%"))
    if technology:
        statement = statement.where(ArchivedProject.technologies_used.ilike(f"%{technology.strip()}%"))
    if project_scope:
        statement = statement.where(ArchivedProject.project_scope.ilike(f"%{project_scope.strip()}%"))
    if completion_stage:
        statement = statement.where(ArchivedProject.completion_stage.ilike(f"%{completion_stage.strip()}%"))
    projects = session.scalars(statement).all()
    normalized = normalize_title(q or "")
    query_tokens = set(normalized.split())
    ranked: list[tuple[int, ArchivedProject, str]] = []
    for project in projects:
        title = normalize_title(project.title) if (project.source_metadata or {}).get("imported") else project.normalized_title
        keywords = {normalize_title(item) for item in (project.keywords or [])}
        summary = normalize_title(project.abstract_summary)
        scope = normalize_title(project.project_scope)
        technology = normalize_title(project.technologies_used or "")
        gaps = normalize_title(project.remaining_gaps)
        if not normalized:
            score, reason = 0, "all active projects"
        elif title == normalized:
            score, reason = 100, "exact title match"
        elif title.startswith(normalized) or normalized in title:
            score, reason = 80, "normalized title match"
        elif query_tokens.intersection(keywords):
            score, reason = 60, "keyword match"
        elif query_tokens.intersection(set(summary.split())):
            score, reason = 40, "summary match"
        elif query_tokens.intersection(set(scope.split())):
            score, reason = 30, "scope match"
        elif query_tokens.intersection(set(technology.split())):
            score, reason = 30, "technology match"
        elif query_tokens.intersection(set(gaps.split())):
            score, reason = 20, "remaining gaps match"
        else:
            continue
        ranked.append((score, project, reason))
    ranked.sort(key=lambda item: (-item[0], item[1].normalized_title, item[1].id))
    results = []
    for rank, (score, project, reason) in enumerate(ranked, 1):
        active_count = session.scalar(select(func.count()).select_from(ArchivedProjectDocument).where(ArchivedProjectDocument.archived_project_id == project.id, ArchivedProjectDocument.is_active.is_(True))) or 0
        results.append({"rank": rank, "id": project.id, "title": project.title, "short_summary": project.abstract_summary[:500], "academic_year": project.academic_year, "session": project.session_name, "group_name": project.group_name or project.group_leader_name, "group_members": project.group_members or [], "supervisor_name": project.supervisor_name, "domain": project.department_program, "department_program": project.department_program, "project_scope": project.project_scope, "completion_stage": project.completion_stage, "project_status": project.project_status, "completion_percentage": project.completion_percentage, "technologies_used": project.technologies_used, "implemented_scope": project.implemented_scope[:500], "remaining_gaps": project.remaining_gaps[:500], "available_documents_count": active_count, "match_score": score, "match_reason": reason})
    return {"semantic_search": "unavailable", "advisory": True, "results": results}


@router.get("/admin/list")
def admin_archive_list(_: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    return [_project_out(session, project, include_history=True) for project in session.scalars(select(ArchivedProject).order_by(ArchivedProject.updated_at.desc(), ArchivedProject.id.desc())).all()]


@router.get("/admin/detail/{project_id}")
def admin_archive_detail(project_id: int, _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    project = session.get(ArchivedProject, project_id)
    if project is None:
        raise _error("archive_not_found", "Archived project was not found.", status.HTTP_404_NOT_FOUND)
    return _project_out(session, project, include_history=True)


@router.get("/{project_id}")
def read_archive(project_id: int, actor: User = Depends(require_roles(*READ_ROLES)), session: Session = Depends(get_db)):
    return _project_out(session, _active_project(session, project_id, actor), actor=actor)


@router.get("/{project_id}/documents/{document_id}")
def read_archive_document(project_id: int, document_id: int, actor: User = Depends(require_roles(*READ_ROLES)), session: Session = Depends(get_db)):
    project = _active_project(session, project_id, actor)
    document = session.scalar(select(ArchivedProjectDocument).where(ArchivedProjectDocument.id == document_id, ArchivedProjectDocument.archived_project_id == project.id, ArchivedProjectDocument.is_active.is_(True)))
    if document is None:
        raise _error("document_not_found", "Archive document was not found.", status.HTTP_404_NOT_FOUND)
    filename = clean_filename(document.display_name)
    from fastapi.responses import StreamingResponse
    from io import BytesIO

    return StreamingResponse(BytesIO(document.content), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})


@router.post("/admin", status_code=status.HTTP_201_CREATED)
def create_archive(payload: ArchiveCreate, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    project = ArchivedProject(normalized_title=normalize_title(payload.title), **payload.model_dump())
    if not project.normalized_title:
        raise _error("invalid_title", "Title must contain letters or numbers.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if session.scalar(select(ArchivedProject).where(ArchivedProject.normalized_title == project.normalized_title, ArchivedProject.academic_year == project.academic_year, ArchivedProject.is_active.is_(True))):
        raise _error("duplicate_active_title", "An active archive with this title already exists in the academic year.")
    try:
        session.add(project); session.flush(); _audit(session, actor, project, "archived_project_created", {"source_label": project.source_label}); session.commit(); session.refresh(project); return _project_out(session, project)
    except IntegrityError as error:
        session.rollback(); raise _error("duplicate_active_title", "An active archive with this title already exists in the academic year.") from error
    except Exception as error:
        session.rollback(); raise _error("archive_create_failed", "The archived project could not be created.", status.HTTP_500_INTERNAL_SERVER_ERROR) from error


@router.patch("/admin/{project_id}")
def update_archive(project_id: int, payload: ArchiveUpdate, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    project = session.scalar(select(ArchivedProject).where(ArchivedProject.id == project_id))
    if project is None:
        raise _error("archive_not_found", "Archived project was not found.", status.HTTP_404_NOT_FOUND)
    changes = payload.model_dump(exclude_unset=True)
    source = project.source_metadata or {}
    if source.get("imported") and "columns" in source and "cells" in source:
        submitted = (changes.get("source_metadata") or {}).get("cells")
        if submitted is not None:
            keys = {column["key"] for column in source["columns"]}
            if not isinstance(submitted, dict) or set(submitted) != keys or any(not isinstance(value, str) for value in submitted.values()):
                raise _error("invalid_excel_cells", "Keep the original Excel columns and provide text cell values.", status.HTTP_422_UNPROCESSABLE_CONTENT)
            changes["source_metadata"] = {**source, "cells": submitted}
            _apply_imported_cells(project, source["columns"], submitted)
            changes.pop("source_metadata", None)
            project.source_metadata = {**source, "cells": submitted}
    if "title" in changes:
        changes["normalized_title"] = normalize_title(changes["title"])
    if "title" in changes or "academic_year" in changes:
        title = changes.get("normalized_title", normalize_title(project.title)); year = changes.get("academic_year", project.academic_year)
        duplicate = session.scalar(select(ArchivedProject).where(ArchivedProject.id != project.id, ArchivedProject.normalized_title == title, ArchivedProject.normalized_group_name == project.normalized_group_name, ArchivedProject.academic_year == year, ArchivedProject.is_active.is_(True)))
        if duplicate:
            raise _error("duplicate_active_title", "An active archive with this title already exists in the academic year.")
    try:
        before = _metadata_snapshot(project)
        for key, value in changes.items(): setattr(project, key, value)
        after = _metadata_snapshot(project)
        _audit(session, actor, project, "archived_project_updated", {"before": before, "after": after}); session.commit(); session.refresh(project); return _project_out(session, project, include_history=True)
    except IntegrityError as error:
        session.rollback(); raise _error("duplicate_active_title", "An active archive with this title already exists in the academic year.") from error


@router.delete("/admin/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_archive(project_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    """Permanently remove an archive record and all of its stored document versions."""
    validate_mutating_origin(request)
    project = session.get(ArchivedProject, project_id)
    if project is None:
        raise _error("archive_not_found", "Archived project was not found.", status.HTTP_404_NOT_FOUND)
    try:
        session.execute(select(ArchivedProjectDocument.id).where(ArchivedProjectDocument.archived_project_id == project_id).with_for_update()).all()
        session.query(ArchivedProjectDocument).filter(ArchivedProjectDocument.archived_project_id == project_id).delete(synchronize_session=False)
        _audit(session, actor, project, "archived_project_deleted", {"source_label": project.source_label})
        session.delete(project)
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise _error("archive_in_use", "This archive is referenced by other data and cannot be deleted.", status.HTTP_409_CONFLICT) from error
    return None


@router.post("/admin/{project_id}/rollback/{event_id}")
def rollback_archive_metadata(project_id: int, event_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    project = session.get(ArchivedProject, project_id)
    event = session.get(AdminAuditEvent, event_id)
    if project is None or event is None or event.target_type != "ARCHIVED_PROJECT" or event.target_id != project_id or event.action != "archived_project_updated":
        raise _error("rollback_not_available", "The requested archive metadata snapshot was not found.", status.HTTP_404_NOT_FOUND)
    before = (event.changed_values or {}).get("before") if isinstance(event.changed_values, dict) else None
    if not isinstance(before, dict) or any(field not in before for field in ARCHIVE_METADATA_FIELDS):
        raise _error("rollback_not_available", "The audit event does not contain a complete metadata snapshot.", status.HTTP_409_CONFLICT)
    normalized_title = normalize_title(str(before["title"]))
    duplicate = session.scalar(select(ArchivedProject).where(ArchivedProject.id != project.id, ArchivedProject.normalized_title == normalized_title, ArchivedProject.academic_year == before["academic_year"], ArchivedProject.is_active.is_(True)))
    if duplicate:
        raise _error("duplicate_active_title", "The historical title conflicts with another active archive.")
    snapshot = _metadata_snapshot(project)
    for field in ARCHIVE_METADATA_FIELDS: setattr(project, field, before[field])
    project.normalized_title = normalized_title
    _audit(session, actor, project, "archived_project_metadata_rolled_back", {"source_event_id": event_id, "before": snapshot, "after": _metadata_snapshot(project)})
    session.commit(); session.refresh(project)
    return _project_out(session, project, include_history=True)


@router.post("/admin/{project_id}/active")
def set_archive_active(project_id: int, request: Request, active: bool = Form(...), actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    project = session.get(ArchivedProject, project_id)
    if project is None:
        raise _error("archive_not_found", "Archived project was not found.", status.HTTP_404_NOT_FOUND)
    project.is_active = active
    project.archived_at = None if active else datetime.now(project.updated_at.tzinfo) if project.updated_at and project.updated_at.tzinfo else datetime.utcnow()
    _audit(session, actor, project, "archived_project_activated" if active else "archived_project_deactivated", {"is_active": active})
    session.commit(); return _project_out(session, project, include_history=True)


@router.post("/admin/{project_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_archive_document(project_id: int, request: Request, document_type: str = Form(...), display_name: str | None = Form(default=None), document: UploadFile = File(...), actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    project = session.get(ArchivedProject, project_id)
    if project is None:
        raise _error("archive_not_found", "Archived project was not found.", status.HTTP_404_NOT_FOUND)
    document_type = document_type.strip().upper()
    if document_type not in DOCUMENT_TYPES:
        raise _error("invalid_document_type", "Unsupported archive document type.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    content = await document.read()
    filename = _validate_document(document, content)
    try:
        previous = session.scalars(select(ArchivedProjectDocument).where(ArchivedProjectDocument.archived_project_id == project.id, ArchivedProjectDocument.document_type == document_type, ArchivedProjectDocument.is_active.is_(True)).with_for_update()).all()
        for item in previous: item.is_active = False
        version = _next_version(session, project.id, document_type)
        row = ArchivedProjectDocument(archived_project_id=project.id, document_type=document_type, display_name=clean_filename(display_name or filename), storage_key=f"archive/{project.id}/{document_type.lower()}/v{version}-{filename}", file_hash=hashlib.sha256(content).hexdigest(), mime_type="application/pdf", file_size=len(content), content=content, version=version, uploaded_by_id=actor.id, is_active=True)
        session.add(row); session.flush(); _audit(session, actor, project, "archived_project_document_uploaded", {"document_type": document_type, "version": version, "file_hash": row.file_hash}); session.commit(); session.refresh(row); return _document_out(row)
    except Exception as error:
        session.rollback(); raise _error("archive_document_upload_failed", "The archive document could not be saved.", status.HTTP_500_INTERNAL_SERVER_ERROR) from error


@router.get("/admin/{project_id}/documents/history")
def archive_document_history(project_id: int, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    project = session.get(ArchivedProject, project_id)
    if project is None:
        raise _error("archive_not_found", "Archived project was not found.", status.HTTP_404_NOT_FOUND)
    return [_document_out(item) for item in session.scalars(select(ArchivedProjectDocument).where(ArchivedProjectDocument.archived_project_id == project.id).order_by(ArchivedProjectDocument.document_type, ArchivedProjectDocument.version.desc())).all()]


@router.delete("/admin/{project_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_archive_document(project_id: int, document_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    document = session.scalar(select(ArchivedProjectDocument).where(ArchivedProjectDocument.id == document_id, ArchivedProjectDocument.archived_project_id == project_id))
    project = session.get(ArchivedProject, project_id)
    if project is None or document is None:
        raise _error("document_not_found", "Archive document was not found.", status.HTTP_404_NOT_FOUND)
    try:
        session.delete(document)
        _audit(session, actor, project, "archived_project_document_deleted", {"document_id": document_id, "document_type": document.document_type, "version": document.version})
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise _error("document_in_use", "This archive document cannot be deleted while referenced.", status.HTTP_409_CONFLICT) from error
    return None


async def _read_archive_upload(file: UploadFile) -> bytes:
    if not (file.filename or "").lower().endswith((".xls", ".xlsx")):
        raise _error("invalid_archive_file_type", "Upload an .xls or .xlsx workbook.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return await file.read()


@admin_archive_router.post("/import/preview")
async def archive_import_preview(academic_cycle_id: int = Form(...), file: UploadFile = File(...), header_row: int | None = Form(default=None, ge=1), has_headers: bool = Form(default=True), _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    cycle = session.get(AcademicCycle, academic_cycle_id)
    if cycle is None or cycle.academic_year is None or not cycle.session:
        raise _error("invalid_academic_cycle", "Select an existing academic cycle with a year and session.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return parse_archive_workbook(await _read_archive_upload(file), cycle, header_row=header_row, has_headers=has_headers)


@admin_archive_router.post("/import/confirm")
@admin_archive_router.post("/projects/import")
async def archive_import_confirm(request: Request, academic_cycle_id: int = Form(...), file: UploadFile = File(...), header_row: int | None = Form(default=None, ge=1), has_headers: bool = Form(default=True), actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    cycle = session.get(AcademicCycle, academic_cycle_id)
    if cycle is None or cycle.academic_year is None or not cycle.session:
        raise _error("invalid_academic_cycle", "Select an existing academic cycle with a year and session.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    preview = parse_archive_workbook(await _read_archive_upload(file), cycle, header_row=header_row, has_headers=has_headers)
    if preview["invalid_rows"]:
        raise _error("archive_import_has_invalid_rows", "Fix invalid rows before confirming the import.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    batch_id = uuid.uuid4().hex
    created: list[ArchivedProject] = []
    duplicate_count = 0
    invalid_count = len(preview.get("invalid_rows", []))
    row_validation_warnings: list[str] = []
    usable_rows: list[dict] = []
    for item in preview["valid_rows"]:
        errors = _import_row_errors(item)
        if errors:
            invalid_count += 1
            row_validation_warnings.extend([f"Excel row {item['row']}: {error}." for error in errors])
        else:
            usable_rows.append(item)
    resolved_rows, orphan_rows = _resolved_import_rows(usable_rows)
    grouped: dict[tuple[int, str, str], list[dict]] = {}
    for item in resolved_rows:
        key = _import_group_key(item, cycle)
        if not key[1]:
            orphan_rows.append(item)
            continue
        grouped.setdefault(key, []).append(item)
    existing = session.scalars(select(ArchivedProject).where(ArchivedProject.academic_cycle_id == cycle.id, ArchivedProject.is_active.is_(True))).all()
    existing_by_key = {(cycle.id, normalize_title(project.title), normalize_title(project.normalized_group_name or project.group_name or "")): project for project in existing}
    seen: set[tuple[int, str, str]] = set()
    merged_existing: list[ArchivedProject] = []
    members_attached = 0
    try:
        batch = ArchiveImportBatch(batch_id=batch_id, original_file_name=clean_filename(file.filename or "archive.xlsx"), uploaded_by_id=actor.id, total_rows=preview["total_rows"], import_status="PROCESSING")
        session.add(batch)
        session.flush()
        for key, items in grouped.items():
            if key in seen:
                duplicate_count += len(items)
                continue
            seen.add(key)
            project = _archive_import_group(items, cycle, batch_id=batch_id)
            raw_member_count = sum(len(_member_rows(item["columns"], item["data"])) for item in items)
            duplicate_count += max(0, raw_member_count - len(project.group_members or []))
            existing_project = existing_by_key.get(key)
            if existing_project is not None:
                before_members = len(existing_project.group_members or [])
                members_attached += max(0, len(_merge_member_values(existing_project.group_members or [], project.group_members or [])) - before_members)
                _merge_imported_project(existing_project, project)
                duplicate_count += len(items)
                merged_existing.append(existing_project)
                _audit(session, actor, existing_project, "archived_project_import_merged", {"academic_cycle_id": cycle.id, "source": "excel", "batch_id": batch_id, "rows": [item["row"] for item in items]})
                continue
            project.source_batch_id = batch_id
            project.source_row_number = min(item["row"] for item in items)
            session.add(project); session.flush(); _audit(session, actor, project, "archived_project_imported", {"academic_cycle_id": cycle.id, "source": "excel", "batch_id": batch_id, "rows": [item["row"] for item in items]}); created.append(project)
            members_attached += len(project.group_members or [])
        batch.inserted_rows = len(created)
        batch.skipped_rows = duplicate_count + len(orphan_rows) + int(preview.get("skipped_rows", 0))
        batch.invalid_rows = invalid_count
        batch.import_status = "COMPLETED"
        session.commit()
    except HTTPException:
        session.rollback(); raise
    except Exception as error:
        session.rollback(); raise _error("archive_import_failed", "The archive import could not be completed.", status.HTTP_500_INTERNAL_SERVER_ERROR) from error
    return {
        "batch_id": batch_id,
        "total_rows": preview["total_rows"],
        "source_rows_processed": preview["total_rows"],
        "unique_projects_created": len(created),
        "inserted": len(created),
        "inserted_count": len(created),
        "imported_count": len(created),
        "members_attached": members_attached,
        "duplicates_skipped": duplicate_count,
        "skipped_rows": duplicate_count + len(orphan_rows) + int(preview.get("skipped_rows", 0)),
        "invalid_rows": invalid_count,
        "orphan_rows": len(orphan_rows),
        "ambiguous_rows": 0,
        "warnings": (["Rows without an explicit or forward-filled project title were skipped."] if orphan_rows else []) + row_validation_warnings,
        "projects": [_project_out(session, project) for project in created] + [_project_out(session, project) for project in merged_existing],
    }


@admin_archive_router.get("/projects")
def admin_archive_projects(
    search: str | None = Query(default=None, max_length=255), academic_cycle_id: int | None = None,
    session_name: str | None = Query(default=None, max_length=16), supervisor: str | None = Query(default=None, max_length=255),
    domain: str | None = Query(default=None, max_length=255), source_batch_id: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
    sort: str = Query(default="updated_at"), direction: str = Query(default="desc"),
    _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db),
) -> dict[str, object]:
    statement = select(ArchivedProject).where(ArchivedProject.is_active.is_(True))
    if search and search.strip(): statement = statement.where(ArchivedProject.title.ilike(f"%{search.strip()}%"))
    if academic_cycle_id is not None: statement = statement.where(ArchivedProject.academic_cycle_id == academic_cycle_id)
    if session_name: statement = statement.where(ArchivedProject.session_name == session_name.strip().upper())
    if supervisor: statement = statement.where(ArchivedProject.supervisor_name.ilike(f"%{supervisor.strip()}%"))
    if domain: statement = statement.where(ArchivedProject.department_program.ilike(f"%{domain.strip()}%"))
    if source_batch_id: statement = statement.where(ArchivedProject.source_batch_id == source_batch_id.strip())
    sort_column = {"title": ArchivedProject.title, "cycle": ArchivedProject.academic_year, "completion": ArchivedProject.completion_percentage, "created_at": ArchivedProject.created_at, "updated_at": ArchivedProject.updated_at}.get(sort, ArchivedProject.updated_at)
    statement = statement.order_by(sort_column.asc() if direction.lower() == "asc" else sort_column.desc(), ArchivedProject.id.desc())
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    projects = session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_project_out(session, project, include_history=True) for project in projects], "page": page, "page_size": page_size, "total": total}


@admin_archive_router.post("/projects/repair-imported")
def repair_imported_archive(request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> dict[str, object]:
    """Safely consolidate obvious duplicate imported parents.

    Old batches may contain student names as titles and cannot be repaired
    without a trustworthy title column. Those rows are reported as ambiguous;
    this endpoint never guesses or deletes them.
    """
    validate_mutating_origin(request)
    projects = session.scalars(select(ArchivedProject).where(ArchivedProject.is_active.is_(True), ArchivedProject.source_label == "EXCEL_IMPORT").order_by(ArchivedProject.id)).all()
    by_key: dict[tuple[int | None, str, str], ArchivedProject] = {}
    merged: list[int] = []
    ambiguous: list[dict[str, object]] = []
    try:
        for project in projects:
            metadata = project.source_metadata or {}
            columns = metadata.get("columns") or []
            cells = metadata.get("cells") or {}
            if columns and not _project_title(columns, cells):
                ambiguous.append({"id": project.id, "title": project.title, "reason": "No explicit project title column in the original import."})
                continue
            key = (project.academic_cycle_id, normalize_title(project.title), normalize_title(project.normalized_group_name or project.group_name or ""))
            previous = by_key.get(key)
            if previous is None:
                by_key[key] = project
                continue
            _merge_imported_project(previous, project)
            project.is_active = False
            project.archived_at = datetime.utcnow()
            merged.append(project.id)
            _audit(session, actor, previous, "archived_project_repaired_merge", {"merged_project_id": project.id})
        session.commit()
    except Exception as error:
        session.rollback()
        raise _error("archive_repair_failed", "The imported archive repair could not be completed.", status.HTTP_500_INTERNAL_SERVER_ERROR) from error
    return {"merged_project_ids": merged, "merged_count": len(merged), "ambiguous_records": ambiguous, "ambiguous_count": len(ambiguous), "warnings": (["Some imported records were not changed because their project title could not be identified safely."] if ambiguous else [])}


@admin_archive_router.get("/projects/{project_id}")
def admin_archive_project(project_id: int, _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> dict:
    project = session.get(ArchivedProject, project_id)
    if project is None: raise _error("archive_not_found", "Archived project was not found.", status.HTTP_404_NOT_FOUND)
    return _project_out(session, project, include_history=True)


@admin_archive_router.patch("/projects/{project_id}")
def admin_update_archive(project_id: int, payload: ArchiveUpdate, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> dict:
    return update_archive(project_id, payload, request, actor, session)


@admin_archive_router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_archive(project_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> None:
    return delete_archive(project_id, request, actor, session)


@admin_archive_router.get("/import-batches")
def archive_import_batches(page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100), _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> dict[str, object]:
    total = session.scalar(select(func.count()).select_from(ArchiveImportBatch)) or 0
    batches = session.scalars(select(ArchiveImportBatch).order_by(ArchiveImportBatch.uploaded_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{"batch_id": batch.batch_id, "original_file_name": batch.original_file_name, "uploaded_by_id": batch.uploaded_by_id, "uploaded_at": batch.uploaded_at, "total_rows": batch.total_rows, "inserted_rows": batch.inserted_rows, "skipped_rows": batch.skipped_rows, "invalid_rows": batch.invalid_rows, "import_status": batch.import_status} for batch in batches], "page": page, "page_size": page_size, "total": total}


@admin_archive_router.get("/import-batches/{batch_id}")
def archive_import_batch_detail(batch_id: str, _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> dict[str, object]:
    batch = session.get(ArchiveImportBatch, batch_id)
    if batch is None: raise _error("import_batch_not_found", "Import batch was not found.", status.HTTP_404_NOT_FOUND)
    projects = session.scalars(select(ArchivedProject).where(ArchivedProject.source_batch_id == batch_id, ArchivedProject.is_active.is_(True)).order_by(ArchivedProject.source_row_number, ArchivedProject.id)).all()
    return {"batch_id": batch.batch_id, "original_file_name": batch.original_file_name, "uploaded_by_id": batch.uploaded_by_id, "uploaded_at": batch.uploaded_at, "total_rows": batch.total_rows, "inserted_rows": batch.inserted_rows, "skipped_rows": batch.skipped_rows, "invalid_rows": batch.invalid_rows, "import_status": batch.import_status, "projects": [_project_out(session, project, include_history=True) for project in projects]}


@router.post("/admin/{project_id}/visibility")
def set_archive_visibility(project_id: int, request: Request, visible: bool = Form(...), actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    project = session.get(ArchivedProject, project_id)
    if project is None:
        raise _error("archive_not_found", "Archived project was not found.", status.HTTP_404_NOT_FOUND)
    project.is_visible_to_students = visible
    _audit(session, actor, project, "archived_project_visibility_changed", {"is_visible_to_students": visible})
    session.commit(); session.refresh(project)
    return _project_out(session, project, include_history=True)
