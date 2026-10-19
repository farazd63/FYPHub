"""Rollback-isolated coverage for M1-E.1 supervisor capacity configuration."""

import asyncio
import json
import unittest
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE_NAME, utc_now
from app.database import engine, get_db
from app.main import app
from app.models import AcademicCycle, AuthSession, User, UserRole
from app.security import generate_session_token, hash_session_token


def request(method: str, path: str, payload: dict[str, Any] | None = None, *, token: str | None = None) -> tuple[int, Any]:
    async def invoke() -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        body = json.dumps(payload).encode() if payload is not None else b""
        received = False
        async def receive() -> dict[str, Any]:
            nonlocal received
            if not received:
                received = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}
        headers = [(b"content-type", b"application/json")]
        if token:
            headers.append((b"cookie", f"{SESSION_COOKIE_NAME}={token}".encode()))
        async def send(message: dict[str, Any]) -> None: messages.append(message)
        await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"", "headers": headers, "client": ("127.0.0.1", 0), "server": ("127.0.0.1", 80)}, receive, send)
        return messages
    messages = asyncio.run(invoke())
    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return start["status"], json.loads(body) if body else None


class SupervisorCapacityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = engine.connect()
        cls.transaction = cls.connection.begin()
        if cls.connection.execute(text("SELECT current_database()")).scalar_one() != "fyphub_p1": raise RuntimeError("Capacity tests require fyphub_p1.")
        app.dependency_overrides[get_db] = cls.get_test_db

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.pop(get_db, None); cls.transaction.rollback(); cls.connection.close()

    @classmethod
    def get_test_db(cls) -> Iterator[Session]:
        session = Session(bind=cls.connection, autoflush=False, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try: yield session
        finally: session.close()

    def setUp(self) -> None:
        suffix = uuid4().hex[:10]
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        self.admin = User(full_name="Capacity Admin", email=f"capacity-admin-{suffix}@example.com", registration_number=None, password_hash="test", role=UserRole.ADMIN)
        self.supervisor = User(full_name="Capacity Supervisor", email=f"capacity-supervisor-{suffix}@example.com", registration_number=None, password_hash="test", role=UserRole.SUPERVISOR)
        self.student = User(full_name="Capacity Student", email=f"capacity-student-{suffix}@example.com", registration_number=f"CAP{suffix}".upper(), password_hash="test", role=UserRole.STUDENT)
        self.inactive = User(full_name="Inactive Supervisor", email=f"capacity-inactive-{suffix}@example.com", registration_number=None, password_hash="test", role=UserRole.SUPERVISOR, is_active=False)
        self.cycle = AcademicCycle(code=f"CAP-{suffix}", display_name="Capacity test cycle")
        session.add_all([self.admin, self.supervisor, self.student, self.inactive, self.cycle]); session.flush()
        self.token, self.student_token = generate_session_token(), generate_session_token()
        session.add_all([AuthSession(user_id=self.admin.id, token_hash=hash_session_token(self.token), expires_at=utc_now().replace(year=utc_now().year + 1)), AuthSession(user_id=self.student.id, token_hash=hash_session_token(self.student_token), expires_at=utc_now().replace(year=utc_now().year + 1))]); session.commit(); session.close()

    def payload(self, **values: Any) -> dict[str, Any]:
        return {"supervisor_id": self.supervisor.id, "academic_cycle_id": self.cycle.id, "max_group_capacity": 3, **values}

    def test_00_capacity_advisory_lock_is_exclusive_across_connections(self) -> None:
        """Exercise the production lock before rollback-isolated API writes acquire it."""
        first, second = engine.connect(), engine.connect()
        transaction = first.begin()
        try:
            first.execute(text("SELECT pg_advisory_xact_lock(98137243)"))
            self.assertFalse(second.execute(text("SELECT pg_try_advisory_xact_lock(98137243)")).scalar_one())
        finally:
            transaction.rollback(); first.close()
        self.assertTrue(second.execute(text("SELECT pg_try_advisory_xact_lock(98137243)")).scalar_one())
        second.rollback(); second.close()

    def test_authorization_validation_eligibility_and_duplicate(self) -> None:
        self.assertEqual(request("GET", "/api/v1/admin/supervisor-capacities")[0], 401)
        self.assertEqual(request("GET", "/api/v1/admin/supervisor-capacities", token=self.student_token)[0], 403)
        self.assertEqual(request("POST", "/api/v1/admin/supervisor-capacities", self.payload(max_group_capacity=0), token=self.token)[0], 422)
        self.assertEqual(request("POST", "/api/v1/admin/supervisor-capacities", self.payload(max_group_capacity=1.5), token=self.token)[0], 422)
        status, body = request("POST", "/api/v1/admin/supervisor-capacities", self.payload(supervisor_id=self.student.id), token=self.token)
        self.assertEqual((status, body["detail"]["code"]), (409, "supervisor_ineligible"))
        status, body = request("POST", "/api/v1/admin/supervisor-capacities", self.payload(supervisor_id=self.inactive.id), token=self.token)
        self.assertEqual((status, body["detail"]["code"]), (409, "supervisor_ineligible"))
        status, created = request("POST", "/api/v1/admin/supervisor-capacities", self.payload(), token=self.token)
        self.assertEqual((status, created["max_group_capacity"]), (201, 3))
        status, body = request("POST", "/api/v1/admin/supervisor-capacities", self.payload(), token=self.token)
        self.assertEqual((status, body["detail"]["code"]), (409, "duplicate_capacity_policy"))

    def test_update_historical_listing_and_capacity_lock(self) -> None:
        _, created = request("POST", "/api/v1/admin/supervisor-capacities", self.payload(), token=self.token)
        status, updated = request("PUT", f"/api/v1/admin/supervisor-capacities/{created['id']}", self.payload(max_group_capacity=5), token=self.token)
        self.assertEqual((status, updated["max_group_capacity"]), (200, 5))
        self.connection.execute(text("UPDATE users SET is_active = false WHERE id = :id"), {"id": self.supervisor.id})
        self.assertFalse(self.connection.execute(text("SELECT is_active FROM users WHERE id = :id"), {"id": self.supervisor.id}).scalar_one())
        status, policies = request("GET", "/api/v1/admin/supervisor-capacities", token=self.token)
        self.assertEqual(status, 200)
        returned = next(policy for policy in policies if policy["id"] == created["id"])
        self.assertEqual((returned["supervisor_id"], returned["supervisor_is_eligible"]), (self.supervisor.id, False))

    def test_audit_failure_rolls_back_capacity(self) -> None:
        from unittest.mock import patch
        with patch("app.main.add_admin_audit_event", side_effect=SQLAlchemyError("audit failure")):
            status, body = request("POST", "/api/v1/admin/supervisor-capacities", self.payload(), token=self.token)
        self.assertEqual((status, body["detail"]["code"]), (500, "capacity_save_failed"))
        count = self.connection.execute(text("SELECT count(*) FROM supervisor_capacity_policies WHERE supervisor_id = :id AND academic_cycle_id = :cycle"), {"id": self.supervisor.id, "cycle": self.cycle.id}).scalar_one()
        self.assertEqual(count, 0)
