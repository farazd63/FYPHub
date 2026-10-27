"""Focused authorization, lifecycle, capacity, and audit tests for supervisor requests."""

import asyncio
import io
import json
import unittest
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.orm import Session
from pypdf import PdfWriter

from app.auth import SESSION_COOKIE_NAME, utc_now
from app.database import engine, get_db
from app.main import app
from app.models import AcademicCycle, AuthSession, SupervisorAssignment, SupervisorCapacityPolicy, SupervisorRequestDocument, Team, User, UserRole
from app.security import generate_session_token, hash_session_token
from tests.test_supervisor_capacity import request


class SupervisorRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = engine.connect()
        cls.transaction = cls.connection.begin()
        if cls.connection.execute(text("SELECT current_database()")).scalar_one() != "fyphub_p1":
            raise RuntimeError("Supervisor request tests require fyphub_p1.")
        app.dependency_overrides[get_db] = cls.get_test_db

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.pop(get_db, None)
        cls.transaction.rollback()
        cls.connection.close()

    @classmethod
    def get_test_db(cls):
        session = Session(bind=cls.connection, autoflush=False, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()

    def setUp(self) -> None:
        suffix = uuid4().hex[:10]
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        self.admin = User(full_name="Request Admin", email=f"request-admin-{suffix}@example.com", password_hash="test", role=UserRole.ADMIN)
        self.coordinator = User(full_name="Request Coordinator", email=f"request-coordinator-{suffix}@example.com", password_hash="test", role=UserRole.COORDINATOR)
        self.supervisor = User(full_name="Request Supervisor", email=f"request-supervisor-{suffix}@example.com", password_hash="test", role=UserRole.SUPERVISOR)
        self.other_supervisor = User(full_name="Other Supervisor", email=f"other-supervisor-{suffix}@example.com", password_hash="test", role=UserRole.SUPERVISOR)
        self.student = User(full_name="Request Student", email=f"request-student-{suffix}@example.com", registration_number=f"REQ{suffix}".upper(), password_hash="test", role=UserRole.STUDENT)
        self.team_user = User(full_name="Team Student", email=f"team-student-{suffix}@example.com", registration_number=f"TEAM{suffix}".upper(), password_hash="test", role=UserRole.STUDENT)
        self.cycle = AcademicCycle(code=f"REQ-{suffix}", display_name="Request cycle", registration_open=True)
        session.add_all([self.admin, self.coordinator, self.supervisor, self.other_supervisor, self.student, self.team_user, self.cycle])
        session.flush()
        self.team = Team(academic_cycle_id=self.cycle.id, shared_user_id=self.team_user.id)
        session.add_all([self.team, SupervisorCapacityPolicy(supervisor_id=self.supervisor.id, academic_cycle_id=self.cycle.id, max_group_capacity=2)])
        session.flush()
        self.tokens = {}
        for label, user in (("admin", self.admin), ("coordinator", self.coordinator), ("supervisor", self.supervisor), ("other", self.other_supervisor), ("student", self.student), ("team", self.team_user)):
            token = generate_session_token()
            self.tokens[label] = token
            session.add(AuthSession(user_id=user.id, token_hash=hash_session_token(token), expires_at=utc_now() + timedelta(hours=1)))
        session.commit()
        session.close()

    def call(self, method: str, path: str, payload=None, token: str | None = None):
        if "?" not in path:
            return request(method, path, payload, token=token)
        parsed = urlsplit(path)
        async def invoke():
            messages = []
            body = json.dumps(payload).encode() if payload is not None else b""
            received = False
            async def receive():
                nonlocal received
                if not received:
                    received = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return {"type": "http.disconnect"}
            headers = [(b"content-type", b"application/json")]
            if token:
                headers.append((b"cookie", f"{SESSION_COOKIE_NAME}={token}".encode()))
            async def send(message):
                messages.append(message)
            await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "http", "path": parsed.path, "raw_path": parsed.path.encode(), "query_string": parsed.query.encode(), "headers": headers, "client": ("127.0.0.1", 0), "server": ("127.0.0.1", 80)}, receive, send)
            return messages
        messages = asyncio.run(invoke())
        start = next(message for message in messages if message["type"] == "http.response.start")
        body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
        return start["status"], json.loads(body) if body else None

    @staticmethod
    def proposal_pdf(title: str = "Campus Safety Study", *, missing_title: bool = False, pages: int = 1) -> bytes:
        page_text = [] if missing_title else ["Proposal Title: Campus Safety Study"]
        page_text += ["Topic: Student safety", "Purpose: Improve campus safety for students.", "Objectives: Map risks and propose controls.", "Methodology: Interviews and observation."]
        objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"]
        content = "BT /F1 11 Tf 72 700 Td " + " ".join(f"({line}) Tj 0 -20 Td" for line in page_text) + " ET"
        content_bytes = content.encode()
        objects.extend([
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
            f"<< /Length {len(content_bytes)} >>\nstream\n".encode() + content_bytes + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ])
        result = b"%PDF-1.4\n"
        offsets = [0]
        for index, obj in enumerate(objects, 1):
            offsets.append(len(result))
            result += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
        xref = len(result)
        result += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
        result += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
        result += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        if pages == 2:
            result += b"\n" + result
        return result

    def multipart_call(self, method: str, path: str, fields: dict[str, str], token: str, filename: str = "proposal.pdf", data: bytes | None = None, content_type: str = "application/pdf"):
        boundary = f"----FYPHub{uuid4().hex}"
        parts = []
        for name, value in fields.items():
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"proposal_file\"; filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n".encode() + (data or self.proposal_pdf()) + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(parts)
        parsed = urlsplit(path)
        async def invoke():
            messages = []
            received = False
            async def receive():
                nonlocal received
                if not received:
                    received = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return {"type": "http.disconnect"}
            headers = [(b"content-type", f"multipart/form-data; boundary={boundary}".encode()), (b"cookie", f"{SESSION_COOKIE_NAME}={token}".encode())]
            async def send(message):
                messages.append(message)
            await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "http", "path": parsed.path, "raw_path": parsed.path.encode(), "query_string": parsed.query.encode(), "headers": headers, "client": ("127.0.0.1", 0), "server": ("127.0.0.1", 80)}, receive, send)
            return messages
        messages = asyncio.run(invoke())
        start = next(message for message in messages if message["type"] == "http.response.start")
        response_body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
        return start["status"], json.loads(response_body) if response_body else None

    def create_draft(self, token: str, supervisor_id: int | None = None, cycle_id: int | None = None, data: bytes | None = None, filename: str = "proposal.pdf", content_type: str = "application/pdf"):
        return self.multipart_call("POST", "/api/v1/supervisor-requests", {"academic_cycle_id": str(cycle_id or self.cycle.id), "supervisor_id": str(supervisor_id or self.supervisor.id)}, token, filename, data, content_type)

    def confirm(self, draft: dict, token: str):
        return self.call("POST", f"/api/v1/supervisor-requests/{draft['id']}/confirm", {"revision": draft["revision"]}, token)

    def submit(self, draft: dict, token: str):
        status, confirmed = self.confirm(draft, token)
        self.assertEqual((status, confirmed["extraction_status"]), (200, "CONFIRMED"))
        return self.call("POST", f"/api/v1/supervisor-requests/{draft['id']}/submit", {"revision": confirmed["revision"]}, token)

    def replace_document(self, draft: dict, token: str, data: bytes | None = None):
        return self.multipart_call("POST", f"/api/v1/supervisor-requests/draft/{draft['id']}/document", {"revision": str(draft["revision"])}, token, data=data)

    def test_eligible_supervisor_list_and_role_isolation(self):
        status, body = self.call("GET", f"/api/v1/supervisor-requests/supervisors?academic_cycle_id={self.cycle.id}", token=self.tokens["student"])
        self.assertEqual(status, 200)
        self.assertEqual([(item["id"], item["available"]) for item in body], [(self.supervisor.id, True)])
        self.assertEqual(self.call("GET", f"/api/v1/supervisor-requests/supervisors?academic_cycle_id={self.cycle.id}", token=self.tokens["supervisor"])[0], 403)

    def test_create_submit_and_student_list(self):
        status, draft = self.create_draft(self.tokens["student"])
        self.assertEqual((status, draft["status"]), (201, "DRAFT"))
        self.assertEqual(draft["extraction_status"], "EXTRACTED")
        status, submitted = self.submit(draft, self.tokens["student"])
        self.assertEqual((status, submitted["status"]), (200, "SUBMITTED"))
        status, mine = self.call("GET", "/api/v1/supervisor-requests/mine", token=self.tokens["student"])
        self.assertEqual(status, 200)
        self.assertEqual(mine[0]["id"], draft["id"])

    def test_duplicate_cross_cycle_and_stale_request_protection(self):
        _, draft = self.create_draft(self.tokens["student"])
        status, body = self.create_draft(self.tokens["student"])
        self.assertEqual((status, body["detail"]["code"]), (409, "duplicate_active_request"))
        status, body = self.multipart_call("POST", f"/api/v1/supervisor-requests/draft/{draft['id']}/document", {"revision": str(draft["revision"] + 1)}, self.tokens["student"])
        self.assertEqual((status, body["detail"]["code"]), (409, "stale_request"))
        other_cycle = AcademicCycle(code=f"OTHER-{uuid4().hex[:8]}", display_name="Other cycle", registration_open=True)
        session = Session(bind=self.connection, join_transaction_mode="create_savepoint"); session.add(other_cycle); session.flush(); other_id = other_cycle.id; session.commit(); session.close()
        self.assertEqual(self.create_draft(self.tokens["team"], cycle_id=other_id)[1]["detail"]["code"], "cycle_mismatch")

    def test_supervisor_only_decision_comment_and_accept_assignment(self):
        _, draft = self.create_draft(self.tokens["team"])
        _, submitted = self.submit(draft, self.tokens["team"])
        status, body = self.call("POST", f"/api/v1/supervisor-requests/{draft['id']}/decision", {"action": "accept", "revision": submitted["revision"]}, self.tokens["other"])
        self.assertEqual((status, body["detail"]["code"]), (403, "request_forbidden"))
        status, body = self.call("POST", f"/api/v1/supervisor-requests/{draft['id']}/decision", {"action": "accept", "revision": submitted["revision"]}, self.tokens["supervisor"])
        self.assertEqual((status, body["status"]), (200, "ACCEPTED"))
        self.assertEqual(self.connection.execute(text("SELECT count(*) FROM supervisor_assignments WHERE team_id=:id AND ended_at IS NULL"), {"id": self.team.id}).scalar_one(), 1)

    def test_reject_changes_resubmit_withdraw_and_history(self):
        _, draft = self.create_draft(self.tokens["student"])
        _, submitted = self.submit(draft, self.tokens["student"])
        status, body = self.call("POST", f"/api/v1/supervisor-requests/{draft['id']}/decision", {"action": "request_changes", "revision": submitted["revision"]}, self.tokens["supervisor"])
        self.assertEqual((status, body["detail"]["code"]), (422, "comment_required"))
        _, changed = self.call("POST", f"/api/v1/supervisor-requests/{draft['id']}/decision", {"action": "request_changes", "comment": "Please clarify the methodology.", "revision": submitted["revision"]}, self.tokens["supervisor"])
        self.assertEqual(changed["status"], "CHANGES_REQUESTED")
        _, edited = self.replace_document(changed, self.tokens["student"])
        _, resubmitted = self.submit(edited, self.tokens["student"])
        self.assertEqual(resubmitted["status"], "SUBMITTED")
        _, rejected = self.call("POST", f"/api/v1/supervisor-requests/{draft['id']}/decision", {"action": "reject", "comment": "Not aligned with the cycle scope.", "revision": resubmitted["revision"]}, self.tokens["supervisor"])
        self.assertEqual(rejected["status"], "REJECTED")
        self.assertGreaterEqual(len(rejected["status_history"]), 5)

    def test_capacity_full_inactive_supervisor_monitoring_and_audit_rollback(self):
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        policy = session.query(SupervisorCapacityPolicy).filter_by(supervisor_id=self.supervisor.id, academic_cycle_id=self.cycle.id).one(); policy.max_group_capacity = 1; session.commit(); session.close()
        _, team_draft = self.create_draft(self.tokens["team"])
        _, team_submitted = self.submit(team_draft, self.tokens["team"])
        _, accepted = self.call("POST", f"/api/v1/supervisor-requests/{team_draft['id']}/decision", {"action": "accept", "revision": team_submitted["revision"]}, self.tokens["supervisor"])
        self.assertEqual(accepted["status"], "ACCEPTED")
        status, body = self.create_draft(self.tokens["student"])
        self.assertEqual((status, body["detail"]["code"]), (409, "capacity_full"))
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint"); session.execute(text("UPDATE users SET is_active=false WHERE id=:id"), {"id": self.other_supervisor.id}); session.commit(); session.close()
        status, body = self.create_draft(self.tokens["student"], supervisor_id=self.other_supervisor.id)
        self.assertEqual((status, body["detail"]["code"]), (409, "supervisor_ineligible"))
        self.assertEqual(self.call("GET", "/api/v1/supervisor-requests/admin/monitor", token=self.tokens["admin"])[0], 200)
        self.assertEqual(self.call("GET", "/api/v1/supervisor-requests/coordinator/monitor", token=self.tokens["coordinator"])[0], 200)
        self.assertEqual(self.call("GET", "/api/v1/supervisor-requests/admin/monitor", token=self.tokens["student"])[0], 403)
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint"); session.execute(text("UPDATE supervisor_capacity_policies SET max_group_capacity=3 WHERE supervisor_id=:id AND academic_cycle_id=:cycle"), {"id": self.supervisor.id, "cycle": self.cycle.id}); session.commit(); session.close()
        with patch("app.main.add_admin_audit_event", side_effect=RuntimeError("audit failure")):
            status, body = self.create_draft(self.tokens["student"], supervisor_id=self.supervisor.id)
        self.assertEqual(status, 500)
        self.assertEqual(self.connection.execute(text("SELECT count(*) FROM supervisor_requests WHERE requester_user_id=:id"), {"id": self.student.id}).scalar_one(), 0)

    def test_pdf_validation_and_missing_required_fields(self):
        self.assertEqual(self.create_draft(self.tokens["student"], filename="proposal.txt")[0], 422)
        self.assertEqual(self.create_draft(self.tokens["student"], content_type="text/plain")[0], 422)
        self.assertEqual(self.create_draft(self.tokens["student"], data=b"%PDF-" + b"x" * (5 * 1024 * 1024 + 1))[0], 422)
        self.assertEqual(self.create_draft(self.tokens["student"], data=b"%PDF-not-readable")[0], 422)
        writer = PdfWriter(); writer.add_blank_page(width=612, height=792); stream = io.BytesIO(); writer.write(stream)
        self.assertEqual(self.create_draft(self.tokens["student"], data=stream.getvalue())[0], 422)
        writer = PdfWriter(); writer.add_blank_page(width=612, height=792); writer.add_blank_page(width=612, height=792); stream = io.BytesIO(); writer.write(stream)
        self.assertEqual(self.create_draft(self.tokens["student"], data=stream.getvalue())[0], 422)
        status, body = self.create_draft(self.tokens["student"], data=self.proposal_pdf(missing_title=True))
        self.assertEqual((status, body["extraction_status"]), (201, "EXTRACTED"))
        self.assertIn("title", body["document"]["extracted_fields"]["missing_required_fields"])
        status, error = self.confirm(body, self.tokens["student"])
        self.assertEqual((status, error["detail"]["code"]), (422, "required_fields_missing"))

    def test_pdf_preview_confirmation_and_authorized_original_document(self):
        status, draft = self.create_draft(self.tokens["student"])
        self.assertEqual(status, 201)
        self.assertEqual(draft["document"]["page_count"], 1)
        self.assertEqual(draft["document"]["extracted_fields"]["title"]["source_page"], 1)
        status, confirmed = self.confirm(draft, self.tokens["student"])
        self.assertEqual((status, confirmed["extraction_status"]), (200, "CONFIRMED"))
        status, document = self.call("GET", f"/api/v1/supervisor-requests/document/{draft['id']}", token=self.tokens["student"])
        self.assertEqual(status, 200)
        status, _ = self.call("GET", f"/api/v1/supervisor-requests/document/{draft['id']}", token=self.tokens["other"])
        self.assertEqual(status, 403)

    def test_concurrent_submission_revision_safety(self):
        _, draft = self.create_draft(self.tokens["student"])
        _, confirmed = self.confirm(draft, self.tokens["student"])
        first_status, first = self.call("POST", f"/api/v1/supervisor-requests/{draft['id']}/submit", {"revision": confirmed["revision"]}, self.tokens["student"])
        self.assertEqual((first_status, first["status"]), (200, "SUBMITTED"))
        second_status, second = self.call("POST", f"/api/v1/supervisor-requests/{draft['id']}/submit", {"revision": confirmed["revision"]}, self.tokens["student"])
        self.assertEqual((second_status, second["detail"]["code"]), (409, "request_not_submittable"))
