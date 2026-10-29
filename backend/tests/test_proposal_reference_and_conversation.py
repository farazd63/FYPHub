"""Reference-search and request-conversation authorization coverage."""

import unittest
import asyncio
import json
from datetime import timedelta
from uuid import uuid4
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE_NAME, utc_now
from app.database import engine, get_db
from app.main import app
from app.models import AcademicCycle, AuthSession, ProposalReference, ProposalReferenceDocument, SupervisorRequest, User, UserRole
from app.security import generate_session_token, hash_session_token
from tests.test_supervisor_capacity import request


class ProposalReferenceAndConversationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = engine.connect()
        cls.transaction = cls.connection.begin()
        if cls.connection.execute(text("SELECT current_database()")).scalar_one() != "fyphub_p1":
            raise RuntimeError("Reference tests require fyphub_p1.")
        app.dependency_overrides[get_db] = cls.get_test_db

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.pop(get_db, None)
        cls.transaction.rollback()
        cls.connection.close()

    @classmethod
    def get_test_db(cls):
        session = Session(bind=cls.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()

    def setUp(self) -> None:
        suffix = uuid4().hex[:10]
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        self.admin = User(full_name="Reference Admin", email=f"reference-admin-{suffix}@example.com", password_hash="test", role=UserRole.ADMIN)
        self.coordinator = User(full_name="Reference Coordinator", email=f"reference-coordinator-{suffix}@example.com", password_hash="test", role=UserRole.COORDINATOR)
        self.supervisor = User(full_name="Reference Supervisor", email=f"reference-supervisor-{suffix}@example.com", password_hash="test", role=UserRole.SUPERVISOR)
        self.student = User(full_name="Reference Student", email=f"reference-student-{suffix}@example.com", registration_number=f"REF{suffix}", password_hash="test", role=UserRole.STUDENT)
        self.other_student = User(full_name="Other Student", email=f"reference-other-{suffix}@example.com", registration_number=f"OTHER{suffix}", password_hash="test", role=UserRole.STUDENT)
        self.panel = User(full_name="Reference Panel", email=f"reference-panel-{suffix}@example.com", password_hash="test", role=UserRole.PANEL_MEMBER)
        self.cycle = AcademicCycle(code=f"REF-{suffix}", display_name="Reference cycle", registration_open=True)
        session.add_all([self.admin, self.coordinator, self.supervisor, self.student, self.other_student, self.panel, self.cycle])
        session.flush()
        self.request_row = SupervisorRequest(academic_cycle_id=self.cycle.id, requester_user_id=self.student.id, supervisor_id=self.supervisor.id, status="SUBMITTED", revision=1)
        session.add(self.request_row)
        reference = ProposalReference(title="Campus Safety Study", normalized_title="campus safety study", short_summary="A sample safety reference.", academic_year="2026", category_scope="Safety", source_label="SAMPLE_DATA", source_metadata={})
        session.add(reference)
        session.flush()
        session.add(ProposalReferenceDocument(reference_id=reference.id, filename="sample.pdf", content_type="application/pdf", file_size=5, sha256="abc", content=b"%PDF-"))
        self.reference_id = reference.id
        session.flush()
        self.tokens = {}
        for name, user in (("admin", self.admin), ("coordinator", self.coordinator), ("supervisor", self.supervisor), ("student", self.student), ("other", self.other_student), ("panel", self.panel)):
            token = generate_session_token(); self.tokens[name] = token
            session.add(AuthSession(user_id=user.id, token_hash=hash_session_token(token), expires_at=utc_now() + timedelta(hours=1)))
        session.commit()
        session.close()

    def call(self, method: str, path: str, token: str):
        parsed = urlsplit(path)
        async def invoke():
            messages = []
            received = False
            async def receive():
                nonlocal received
                if not received:
                    received = True
                    return {"type": "http.request", "body": b"", "more_body": False}
                return {"type": "http.disconnect"}
            async def send(message): messages.append(message)
            await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "http", "path": parsed.path, "raw_path": parsed.path.encode(), "query_string": parsed.query.encode(), "headers": [(b"cookie", f"{SESSION_COOKIE_NAME}={token}".encode())], "client": ("127.0.0.1", 0), "server": ("127.0.0.1", 80)}, receive, send)
            return messages
        messages = asyncio.run(invoke())
        start = next(message for message in messages if message["type"] == "http.response.start")
        body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
        return start["status"], json.loads(body) if body else None

    def test_title_search_exact_similar_and_no_close(self) -> None:
        status, body = self.call("GET", "/api/v1/proposal-references/search?q=Campus---Safety%20Study", self.tokens["student"])
        self.assertEqual((status, body["match_type"]), (200, "exact_title_match"))
        self.assertEqual(body["results"][0]["title"], "Campus Safety Study")
        self.assertEqual(body["results"][0]["source_label"], "SAMPLE_DATA")
        self.assertTrue(body["results"][0]["pdf_available"])
        self.assertTrue(body["advisory"])
        status, body = self.call("GET", "/api/v1/proposal-references/search?q=Campus%20Safety", self.tokens["supervisor"])
        self.assertEqual((status, body["match_type"]), (200, "possible_similar_title"))
        status, body = self.call("GET", "/api/v1/proposal-references/search?q=Quantum%20Robotics", self.tokens["coordinator"])
        self.assertEqual((status, body["match_type"]), (200, "no_close_match"))

    def test_reference_pdf_and_panel_denial(self) -> None:
        status, body = request("GET", f"/api/v1/proposal-references/{self.reference_id}/document", token=self.tokens["admin"])
        self.assertEqual(status, 200)
        status, _ = self.call("GET", "/api/v1/proposal-references/search?q=Campus", self.tokens["panel"])
        self.assertEqual(status, 403)

    def test_request_conversation_scope_and_panel_denial(self) -> None:
        path = f"/api/v1/supervisor-requests/{self.request_row.id}/conversation"
        status, body = request("POST", path, {"body": "Please clarify the review timeline."}, token=self.tokens["student"])
        self.assertEqual((status, body["request_id"]), (201, self.request_row.id))
        status, body = request("GET", path, token=self.tokens["supervisor"])
        self.assertEqual((status, len(body)), (200, 1))
        self.assertEqual(request("GET", path, token=self.tokens["other"])[0], 403)
        self.assertEqual(request("GET", path, token=self.tokens["panel"])[0], 403)
        self.assertEqual(request("GET", path, token=self.tokens["admin"])[0], 200)
        self.assertEqual(request("GET", path, token=self.tokens["coordinator"])[0], 200)
        self.assertEqual(request("POST", path, {"body": "Coordinator reply is not allowed."}, token=self.tokens["coordinator"])[0], 403)
        self.assertEqual(request("POST", path, {"body": "Admin reply is not allowed."}, token=self.tokens["admin"])[0], 403)


if __name__ == "__main__":
    unittest.main()
