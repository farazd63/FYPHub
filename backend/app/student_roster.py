"""Admin-only approved XLSX roster preview and atomic import."""
import hashlib
import hmac
import io
import re
import xml.etree.ElementTree as ET
import secrets
import time
import zipfile
from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from openpyxl import load_workbook
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .auth import require_roles, validate_mutating_origin
from .database import get_db
from .models import AcademicCycle, AdminAuditEvent, User, UserRole
from .models.student_roster import ApprovedStudent, RosterImport

router = APIRouter(prefix="/api/v1/admin/student-roster")
KEY = secrets.token_bytes(32)  # Process-local; restart safely invalidates outstanding previews.
MAX_UPLOAD = 2 * 1024 * 1024
MAX_EXPANDED = 20 * 1024 * 1024
MAX_ROWS = 2000
MAX_COLS = 7
TTL = 600
HEADERS = ("name", "registration_number", "university_email", "semester", "academic_cycle", "group_code", "project_topic")

def fail(code, message, status=422):
    raise HTTPException(status_code=status, detail={"code": code, "message": message})

async def body_bytes(request):
    if not request.headers.get("x-file-name", "").lower().endswith(".xlsx"):
        fail("invalid_file", "Select an .xlsx file.")
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_UPLOAD: fail("file_too_large", "Workbook exceeds the upload limit.", 413)
    return bytes(data)

def parse_workbook(data, cycle):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            items = archive.infolist()
            if len(items) > 256 or sum(i.file_size for i in items) > MAX_EXPANDED or any(i.flag_bits & 1 for i in items):
                fail("invalid_workbook", "Workbook is encrypted or exceeds technical limits.")
            if any(i.filename.startswith("xl/externalLinks/") for i in items): fail("invalid_workbook", "External workbook links are not supported.")
            sheets = [i for i in items if re.fullmatch(r"xl/worksheets/sheet[0-9]+\.xml", i.filename)]
            if len(sheets) != 1: fail("invalid_workbook", "Workbook must contain exactly one worksheet.")
            xml = ET.fromstring(archive.read(sheets[0]))
            actual_row, actual_col = 0, 0
            for cell in xml.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)", cell.get("r", ""))
                if not match: fail("invalid_workbook", "Invalid worksheet coordinates.")
                col = 0
                for letter in match.group(1): col = col * 26 + ord(letter) - ord("A") + 1
                actual_col = max(actual_col, col); actual_row = max(actual_row, int(match.group(2)))
                if actual_col > MAX_COLS or actual_row > MAX_ROWS + 1: fail("invalid_workbook", "Workbook dimensions exceed technical limits.")
        book = load_workbook(io.BytesIO(data), read_only=True, data_only=False, keep_links=False)
        if len(book.worksheets) != 1: fail("invalid_workbook", "Workbook must contain exactly one worksheet.")
        sheet = book.worksheets[0]
        if sheet.max_row is None or sheet.max_column is None or sheet.max_row > MAX_ROWS + 1 or sheet.max_column > MAX_COLS or actual_row > sheet.max_row or actual_col > sheet.max_column: fail("invalid_workbook", "Workbook dimensions exceed technical limits or are inconsistent.")
        rows = sheet.iter_rows()
        header = next(rows, None)
        values = [str(c.value).strip().lower() if isinstance(c.value, str) else "" for c in (header or [])]
        required = set(HEADERS[:-1])
        if len(values) != len(set(values)) or not required.issubset(values) or any(v not in HEADERS for v in values): fail("invalid_headers", "Use the documented roster headers.")
        mapping = {name: values.index(name) for name in values}
        clean, errors, seen_reg, seen_email = [], [], set(), set()
        for number, cells in enumerate(rows, 2):
            if number > MAX_ROWS + 1 or len(cells) > MAX_COLS: fail("invalid_workbook", "Workbook dimensions exceed technical limits.")
            if all(c.value is None for c in cells): continue
            record = {}; row_errors = []
            def error(field, message): row_errors.append({"row": number, "field": field, "message": message})
            for field, idx in mapping.items():
                cell = cells[idx]; value = cell.value
                if cell.data_type == "f": error(field, "Formula cells are not allowed."); continue
                if field == "semester":
                    if type(value) is int and value in (7, 8): record[field] = value
                    elif isinstance(value, str) and value.strip() in ("7", "8"): record[field] = int(value.strip())
                    else: error(field, "Semester must be 7 or 8.")
                elif field == "project_topic" and value is None: record[field] = None
                elif not isinstance(value, str) or not value.strip(): error(field, "Enter text in this field.")
                elif field == "registration_number" and value != value.strip(): error(field, "Registration number must not have surrounding whitespace.")
                else: record[field] = value if field == "registration_number" else value.strip()
            for field, limit in (("name",255), ("registration_number",100), ("university_email",320), ("group_code",100), ("project_topic",4000)):
                if record.get(field) and len(record[field]) > limit: error(field, "Value is too long.")
            if "university_email" in record:
                try: record["university_email"] = validate_email(record["university_email"], check_deliverability=False).normalized.lower()
                except EmailNotValidError: error("university_email", "Enter a valid university email.")
            if record.get("academic_cycle", "").upper() != cycle.code: error("academic_cycle", "Cycle must match the selected cycle code.")
            for field, seen in (("registration_number",seen_reg),("university_email",seen_email)):
                value = record.get(field)
                if value:
                    value = value.lower()
                    if value in seen: error(field, "Duplicate identifier in workbook.")
                    seen.add(value)
            errors.extend(row_errors)
            record["row"] = number; record.setdefault("project_topic", None); clean.append(record)
        book.close()
        if not clean: fail("empty_workbook", "Workbook contains no student rows.")
        return clean, errors
    except HTTPException: raise
    except Exception: fail("invalid_workbook", "Workbook could not be read. Use an unencrypted valid .xlsx file.")

def conflict_errors(session, cycle_id, rows):
    regs = [r.get("registration_number") for r in rows if r.get("registration_number")]
    emails = [r.get("university_email") for r in rows if r.get("university_email")]
    existing = session.execute(select(ApprovedStudent.registration_number, ApprovedStudent.university_email).where(ApprovedStudent.academic_cycle_id == cycle_id, (func.lower(ApprovedStudent.registration_number).in_([value.lower() for value in regs])) | (ApprovedStudent.university_email.in_(emails)))).all()
    registrations, addresses = {x[0].lower() for x in existing}, {x[1].lower() for x in existing}
    return [{"row": row["row"], "field": field, "message": "Identifier already exists in this cycle."} for row in rows for field, found in (("registration_number", registrations), ("university_email", addresses)) if (row.get(field) or "").lower() in found]

def sign(actor, cycle, data, timestamp=None, nonce=None):
    ts = int(time.time()) if timestamp is None else timestamp
    nonce = nonce or secrets.token_hex(16)
    digest = hashlib.sha256(data).hexdigest()
    payload = f"{actor}:{cycle}:{ts}:{nonce}:{digest}"
    return f"{ts}.{nonce}.{hmac.new(KEY, payload.encode(), hashlib.sha256).hexdigest()}"

def verify(token, actor, cycle, data):
    try:
        timestamp, nonce, mac = token.split(".")
        ts = int(timestamp)
        if ts > int(time.time()) or int(time.time()) - ts > TTL or len(nonce) != 32: raise ValueError()
        expected = sign(actor, cycle, data, ts, nonce)
        if not hmac.compare_digest(token, expected): raise ValueError()
    except (ValueError, TypeError): fail("invalid_confirmation", "Preview expired or does not match this upload, cycle, or account.", 409)
    return hashlib.sha256(token.encode()).hexdigest()

@router.post("/preview")
async def preview(request: Request, academic_cycle_id: int = Query(gt=0), actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    cycle = session.get(AcademicCycle, academic_cycle_id)
    if not cycle: fail("cycle_not_found", "Academic cycle was not found.", 404)
    data = await body_bytes(request)
    rows, errors = parse_workbook(data, cycle); errors.extend(conflict_errors(session, cycle.id, rows))
    invalid = {e["row"] for e in errors}
    return {"rows": rows, "errors": errors, "valid_count": len(rows)-len(invalid), "invalid_count": len(invalid), "confirmation_token": sign(actor.id, cycle.id, data) if not errors else None, "expires_in_seconds": TTL}

@router.post("/confirm")
async def confirm(request: Request, academic_cycle_id: int = Query(gt=0), actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    data = await body_bytes(request)
    token_hash = verify(request.headers.get("x-preview-token", ""), actor.id, academic_cycle_id, data)
    try:
        cycle = session.execute(select(AcademicCycle).where(AcademicCycle.id == academic_cycle_id).with_for_update()).scalar_one_or_none()
        if not cycle: fail("cycle_not_found", "Academic cycle was not found.", 404)
        if session.execute(select(RosterImport.id).where(RosterImport.confirmation_hash == token_hash)).first(): fail("confirmation_used", "This preview has already been imported.", 409)
        rows, errors = parse_workbook(data, cycle); errors.extend(conflict_errors(session, cycle.id, rows))
        if errors: fail("roster_changed", "The preview is no longer valid; upload and preview again.", 409)
        batch = RosterImport(academic_cycle_id=cycle.id, imported_by_id=actor.id, confirmation_hash=token_hash); session.add(batch); session.flush()
        for row in rows:
            session.add(ApprovedStudent(academic_cycle_id=cycle.id, import_id=batch.id, name=row["name"], registration_number=row["registration_number"], university_email=row["university_email"], semester=row["semester"], group_code=row["group_code"], project_topic=row["project_topic"]))
        session.add(AdminAuditEvent(actor_id=actor.id, affected_user_id=None, target_type="ROSTER_IMPORT", target_id=batch.id, action="student_roster_imported", changed_values={"academic_cycle_id": cycle.id, "record_count": len(rows)}))
        session.commit()
        return {"import_id": batch.id, "record_count": len(rows)}
    except HTTPException: session.rollback(); raise
    except IntegrityError: session.rollback(); fail("roster_conflict", "Roster conflicts with existing records; preview again.", 409)
    except Exception: session.rollback(); fail("import_failed", "Roster import could not be completed.", 500)

@router.get("")
def list_students(academic_cycle_id: int = Query(gt=0), page: int = Query(1, ge=1, le=1000000), page_size: int = Query(20, ge=1, le=100), _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    if not session.get(AcademicCycle, academic_cycle_id): fail("cycle_not_found", "Academic cycle was not found.", 404)
    where = ApprovedStudent.academic_cycle_id == academic_cycle_id
    total = session.execute(select(func.count()).select_from(ApprovedStudent).where(where)).scalar_one()
    rows = session.execute(select(ApprovedStudent).where(where).order_by(ApprovedStudent.id).offset((page-1)*page_size).limit(page_size)).scalars().all()
    return {"items": [{"id": x.id, "name": x.name, "registration_number": x.registration_number, "university_email": x.university_email, "semester": x.semester, "group_code": x.group_code, "project_topic": x.project_topic, "import_id": x.import_id} for x in rows], "page": page, "page_size": page_size, "total": total}
