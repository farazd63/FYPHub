"""Authorized academic-cycle overview coverage for Admin and Coordinator portals."""

from __future__ import annotations

import asyncio
import json
import unittest
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE_NAME, utc_now
from app.database import engine, get_db
from app.main import app
from app.models import AcademicCycle, AuthSession, User, UserRole
from app.security import generate_session_token, hash_password, hash_session_token


def request(method: str, path: str, *, token: str | None = None) -> tuple[int, Any]:
    async def invoke() -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        received = False

        async def receive() -> dict[str, Any]:
            nonlocal received
            if not received:
                received = True
                return {"type": "http.request", "body": b"", "more_body": False}
            return {"type": "http.disconnect"}

        headers = []
        if token:
            headers.append((b"cookie", f"{SESSION_COOKIE_NAME}={token}".encode()))

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": headers,
                "client": ("127.0.0.1", 0),
                "server": ("127.0.0.1", 8010),
            },
            receive,
            send,
        )
        return messages

    messages = asyncio.run(invoke())
    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return start["status"], json.loads(body) if body else None


class AcademicCycleOverviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = engine.connect()
        cls.transaction = cls.connection.begin()
        if cls.connection.execute(text("SELECT current_database()")).scalar_one() != "fyphub_p1":
            raise RuntimeError("Academic cycle overview tests require fyphub_p1.")
        app.dependency_overrides[get_db] = cls.get_test_db

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.pop(get_db, None)
        cls.transaction.rollback()
        cls.connection.close()

    @classmethod
    def get_test_db(cls) -> Iterator[Session]:
        session = Session(bind=cls.connection, autoflush=False, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()

    def setUp(self) -> None:
        suffix = uuid4().hex[:10]
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        self.admin = User(full_name="Cycle Admin", email=f"cycle-admin-{suffix}@example.com", password_hash=hash_password("Test Password!"), role=UserRole.ADMIN)
        self.coordinator = User(full_name="Cycle Coordinator", email=f"cycle-coordinator-{suffix}@example.com", password_hash=hash_password("Test Password!"), role=UserRole.COORDINATOR)
        self.student = User(full_name="Cycle Student", email=f"cycle-student-{suffix}@example.com", registration_number=f"CYCLE{suffix}".upper(), password_hash=hash_password("Test Password!"), role=UserRole.STUDENT)
        self.cycle = AcademicCycle(code=f"OVERVIEW-{suffix}".upper(), display_name="Overview test cycle", registration_open=True)
        session.add_all([self.admin, self.coordinator, self.student, self.cycle])
        session.flush()
        self.admin_token = generate_session_token()
        self.coordinator_token = generate_session_token()
        self.student_token = generate_session_token()
        expiry = utc_now().replace(year=utc_now().year + 1)
        session.add_all([
            AuthSession(user_id=self.admin.id, token_hash=hash_session_token(self.admin_token), expires_at=expiry),
            AuthSession(user_id=self.coordinator.id, token_hash=hash_session_token(self.coordinator_token), expires_at=expiry),
            AuthSession(user_id=self.student.id, token_hash=hash_session_token(self.student_token), expires_at=expiry),
        ])
        session.commit()
        self.cycle_id = self.cycle.id
        session.close()

    def test_admin_and_coordinator_receive_empty_structured_overview(self) -> None:
        for token in (self.admin_token, self.coordinator_token):
            with self.subTest(token=token[:4]):
                status, body = request("GET", f"/api/v1/academic-cycles/{self.cycle_id}/overview", token=token)
                self.assertEqual(status, 200)
                self.assertEqual(body["cycle"]["id"], self.cycle_id)
                self.assertEqual(body["summary"], {"supervisors": 0, "students": 0, "groups": 0, "projects": 0, "active_projects": 0, "completed_projects": 0, "pending_reviews": 0, "required_documents": 0})
                self.assertEqual([body[key] for key in ("supervisors", "projects", "groups", "students", "documents")], [[], [], [], [], []])

    def test_overview_rejects_missing_session_student_and_unknown_cycle(self) -> None:
        self.assertEqual(request("GET", f"/api/v1/academic-cycles/{self.cycle_id}/overview")[0], 401)
        self.assertEqual(request("GET", f"/api/v1/academic-cycles/{self.cycle_id}/overview", token=self.student_token)[0], 403)
        status, body = request("GET", "/api/v1/academic-cycles/999999999/overview", token=self.admin_token)
        self.assertEqual((status, body["detail"]), (404, "Academic cycle not found."))

    def test_overview_route_is_registered_in_openapi(self) -> None:
        path = "/api/v1/academic-cycles/{cycle_id}/overview"
        self.assertIn(path, app.openapi()["paths"])
        self.assertIn("get", app.openapi()["paths"][path])

    def test_fall_2027_list_id_resolves_for_admin_and_coordinator(self) -> None:
        list_status, rows = request("GET", "/api/v1/academic-cycles")
        self.assertEqual(list_status, 200)
        fall = next((row for row in rows if row["display_name"] == "Fall 2027"), None)
        self.assertIsNotNone(fall)
        self.assertIsInstance(fall["id"], int)
        cycle_id = fall["id"]
        for token in (self.admin_token, self.coordinator_token):
            with self.subTest(token=token[:4]):
                status, body = request("GET", f"/api/v1/academic-cycles/{cycle_id}/overview", token=token)
                self.assertEqual(status, 200)
                self.assertEqual(body["cycle"]["id"], cycle_id)
                self.assertEqual(body["cycle"]["display_name"], "Fall 2027")
                for field in ("supervisors", "projects", "groups", "students", "documents"):
                    self.assertIn(field, body)

