"""Rollback-isolated coverage for M1-B administrator account management."""

import asyncio
import json
import unittest
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE_NAME, utc_now
from app.database import engine, get_db
from app.main import app
from app.models import AdminAuditEvent, AuthSession, Team, User, UserRole
from app.security import generate_session_token, hash_password, hash_session_token


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
        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "http", "path": path.split("?", 1)[0], "raw_path": path.split("?", 1)[0].encode(), "query_string": path.partition("?")[2].encode(), "headers": headers, "client": ("127.0.0.1", 0), "server": ("127.0.0.1", 80)}, receive, send)
        return messages

    messages = asyncio.run(invoke())
    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return start["status"], json.loads(body) if body else None


class AdminUserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = engine.connect()
        cls.transaction = cls.connection.begin()
        if cls.connection.execute(text("SELECT current_database()")).scalar_one() != "fyphub_p1":
            raise RuntimeError("Admin user tests require fyphub_p1.")
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
        self.admin = User(full_name="Admin Test", email=f"admin-{suffix}@example.com", registration_number=None, password_hash=hash_password("Test Password!"), role=UserRole.ADMIN)
        self.user = User(full_name="User Test", email=f"user-{suffix}@example.com", registration_number=f"USR{suffix}".upper(), password_hash=hash_password("Test Password!"), role=UserRole.STUDENT)
        self.student = User(full_name="Student Test", email=f"student-{suffix}@example.com", registration_number=f"STU{suffix}".upper(), password_hash=hash_password("Test Password!"), role=UserRole.STUDENT)
        session.add_all([self.admin, self.user, self.student])
        session.flush()
        self.admin_id, self.user_id, self.student_id = self.admin.id, self.user.id, self.student.id
        self.token = generate_session_token()
        session.add(AuthSession(user_id=self.admin_id, token_hash=hash_session_token(self.token), expires_at=utc_now().replace(year=utc_now().year + 1)))
        self.student_token = generate_session_token()
        session.add(AuthSession(user_id=self.student_id, token_hash=hash_session_token(self.student_token), expires_at=utc_now().replace(year=utc_now().year + 1)))
        session.commit()
        session.close()

    def test_listing_authorization_search_and_safe_values(self) -> None:
        self.assertEqual(request("GET", "/api/v1/admin/users")[0], 401)
        self.assertEqual(request("GET", "/api/v1/admin/users", token=self.student_token)[0], 403)
        status, body = request("GET", f"/api/v1/admin/users?search={self.user.email}&role=STUDENT&is_active=true", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 1)
        self.assertNotIn("password_hash", body["items"][0])
        self.assertNotIn("session", body["items"][0])

    def test_pagination_uses_the_requested_page(self) -> None:
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        for index in range(3):
            session.add(User(full_name=f"Page Test {index}", email=f"page-{uuid4().hex}@example.com", registration_number=None, password_hash="test-only-hash", role=UserRole.SUPERVISOR))
        session.commit()
        session.close()
        status, body = request("GET", "/api/v1/admin/users?role=SUPERVISOR&page=2&page_size=1", token=self.token)
        self.assertEqual((status, body["page"], body["page_size"]), (200, 2, 1))
        self.assertEqual(len(body["items"]), 1)

    def test_last_admin_lock_is_exclusive_across_database_connections(self) -> None:
        first = engine.connect()
        second = engine.connect()
        transaction = first.begin()
        try:
            first.execute(text("SELECT pg_advisory_xact_lock(98137241)"))
            self.assertFalse(second.execute(text("SELECT pg_try_advisory_xact_lock(98137241)")).scalar_one())
        finally:
            transaction.rollback()
            first.close()
        try:
            self.assertTrue(second.execute(text("SELECT pg_try_advisory_xact_lock(98137241)")).scalar_one())
            second.rollback()
        finally:
            second.close()

    def test_creation_duplicate_and_atomic_audit(self) -> None:
        payload = {"full_name": "New Supervisor", "email": " NEW-SUPERVISOR@example.com ", "password": "ValidPass123!", "role": "SUPERVISOR"}
        status, body = request("POST", "/api/v1/admin/users", payload, token=self.token)
        self.assertEqual(status, 201)
        self.assertEqual(body["email"], "new-supervisor@example.com")
        audit = self.connection.execute(text("SELECT action, changed_values FROM admin_audit_events WHERE affected_user_id = :id"), {"id": body["id"]}).one()
        self.assertEqual(audit.action, "account_created")
        self.assertNotIn("password", audit.changed_values)
        self.assertEqual(request("POST", "/api/v1/admin/users", payload, token=self.token)[0], 409)
        self.assertEqual(request("POST", "/api/v1/admin/users", {**payload, "email": "student-required@example.com", "role": "STUDENT"}, token=self.token)[0], 422)

    def test_creation_rejects_malformed_email(self) -> None:
        for malformed in ("missing-domain@", "missing-dot@example", "has space@example.com", "double..dot@example.com", "two@@example.com"):
            with self.subTest(malformed=malformed):
                status, _ = request(
                    "POST",
                    "/api/v1/admin/users",
                    {
                        "full_name": "Invalid Email User",
                        "email": malformed,
                        "password": "ValidPass123!",
                        "role": "SUPERVISOR",
                    },
                    token=self.token,
                )
                self.assertEqual(status, 422)

    def test_admin_can_create_each_fixed_non_public_role(self) -> None:
        for role in ("SUPERVISOR", "COORDINATOR", "PANEL_MEMBER", "ADMIN"):
            with self.subTest(role=role):
                status, body = request(
                    "POST",
                    "/api/v1/admin/users",
                    {
                        "full_name": f"Created {role}",
                        "email": f"created-{role.lower()}-{uuid4().hex}@example.com",
                        "password": "ValidPass123!",
                        "role": role,
                    },
                    token=self.token,
                )
                self.assertEqual(status, 201)
                self.assertEqual(body["role"], role)
                self.assertNotIn("password", body)
                self.assertNotIn("password_hash", body)

    def test_role_status_session_revocation_and_last_admin_protection(self) -> None:
        user_token = generate_session_token()
        self.connection.execute(text("INSERT INTO auth_sessions (user_id, token_hash, expires_at) VALUES (:id, :token, :expires)"), {"id": self.user_id, "token": hash_session_token(user_token), "expires": utc_now().replace(year=utc_now().year + 1)})
        status, body = request("PATCH", f"/api/v1/admin/users/{self.user_id}/role", {"role": "SUPERVISOR"}, token=self.token)
        self.assertEqual((status, body["detail"]["code"]), (409, "assigned_role_locked"))
        self.assertIsNone(self.connection.execute(text("SELECT revoked_at FROM auth_sessions WHERE token_hash = :token"), {"token": hash_session_token(user_token)}).scalar_one())
        status, body = request("PATCH", f"/api/v1/admin/users/{self.user_id}/status", {"is_active": False}, token=self.token)
        self.assertEqual((status, body["is_active"]), (200, False))
        self.connection.execute(text("UPDATE users SET is_active = false WHERE role = CAST('ADMIN' AS user_role) AND id != :id"), {"id": self.admin_id})
        self.assertEqual(request("PATCH", f"/api/v1/admin/users/{self.admin_id}/status", {"is_active": False}, token=self.token)[0], 409)
        self.assertEqual(request("PATCH", f"/api/v1/admin/users/{self.admin_id}/role", {"role": "COORDINATOR"}, token=self.token)[0], 409)

    def test_shared_team_protection_and_append_only_database_trigger(self) -> None:
        cycle_id = self.connection.execute(text("SELECT id FROM academic_cycles ORDER BY id LIMIT 1")).scalar_one()
        self.connection.execute(text("INSERT INTO teams (academic_cycle_id, shared_user_id) VALUES (:cycle_id, :user_id)"), {"cycle_id": cycle_id, "user_id": self.student_id})
        status, body = request("PATCH", f"/api/v1/admin/users/{self.student_id}/role", {"role": "SUPERVISOR"}, token=self.token)
        self.assertEqual((status, body["detail"]["code"]), (409, "assigned_role_locked"))
        self.assertEqual(request("PATCH", f"/api/v1/admin/users/{self.student_id}/status", {"is_active": False}, token=self.token)[0], 409)
        event = AdminAuditEvent(actor_id=self.admin_id, affected_user_id=self.user_id, target_type="USER", target_id=self.user_id, action="test", changed_values={"safe": True})
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        session.add(event)
        session.commit()
        nested = self.connection.begin_nested()
        try:
            with self.assertRaises(DBAPIError):
                self.connection.execute(text("UPDATE admin_audit_events SET action = 'changed' WHERE id = :id"), {"id": event.id})
        finally:
            nested.rollback()
        nested = self.connection.begin_nested()
        try:
            with self.assertRaises(DBAPIError):
                self.connection.execute(text("DELETE FROM admin_audit_events WHERE id = :id"), {"id": event.id})
        finally:
            nested.rollback()
        session.close()

    def test_cycle_policy_management_and_audit_target(self) -> None:
        status, cycle = request("POST", "/api/v1/admin/academic-cycles", {"academic_year": 2031, "session": "Fall"}, token=self.token)
        self.assertEqual((status, cycle["academic_year"], cycle["session"], cycle["registration_open"]), (201, 2031, "FALL", False))
        self.assertEqual(request("PATCH", f"/api/v1/admin/academic-cycles/{cycle['id']}", {"registration_open": True}, token=self.token)[0], 409)
        self.assertEqual(request("PUT", f"/api/v1/admin/academic-cycles/{cycle['id']}/group-policy", {"max_group_size": 0}, token=self.token)[0], 422)
        status, policy = request("PUT", f"/api/v1/admin/academic-cycles/{cycle['id']}/group-policy", {"max_group_size": 3}, token=self.token)
        self.assertEqual((status, policy["max_group_size"]), (200, 3))
        self.assertEqual(request("PATCH", f"/api/v1/admin/academic-cycles/{cycle['id']}", {"registration_open": True}, token=self.token)[0], 200)
        target = self.connection.execute(text("SELECT target_type, affected_user_id FROM admin_audit_events WHERE target_id = :id ORDER BY id DESC LIMIT 1"), {"id": policy["id"]}).one()
        self.assertEqual((target.target_type, target.affected_user_id), ("ACADEMIC_GROUP_POLICY", None))

    def test_academic_cycle_creation_requires_year_and_session(self) -> None:
        for payload in ({"session": "Fall"}, {"academic_year": 2032}):
            with self.subTest(payload=payload):
                status, body = request("POST", "/api/v1/admin/academic-cycles", payload, token=self.token)
                self.assertEqual(status, 422)
                self.assertIn("detail", body)

    def test_academic_cycle_creation_persists_year_and_session(self) -> None:
        status, body = request(
            "POST",
            "/api/v1/admin/academic-cycles",
            {"academic_year": 2033, "session": "Spring"},
            token=self.token,
        )
        self.assertEqual(status, 201)
        self.assertEqual((body["academic_year"], body["session"]), (2033, "SPRING"))
        self.assertEqual(
            self.connection.execute(
                text("SELECT academic_year, session FROM academic_cycles WHERE id=:id"),
                {"id": body["id"]},
            ).one(),
            (2033, "SPRING"),
        )
