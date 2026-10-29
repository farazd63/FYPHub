"""Rollback-isolated integration tests for cookie-backed authentication."""

import asyncio
import json
import unittest
from collections.abc import Iterator
from datetime import timedelta
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE_NAME, get_current_user, require_roles, utc_now
from app.database import engine, get_db
from app.main import app
from app.models import AuthSession, User, UserRole
from app.security import generate_session_token, hash_password, hash_session_token


def request(method: str, path: str, payload: dict[str, Any] | None = None, *, headers: dict[str, str] | None = None, scheme: str = "http") -> tuple[int, dict[str, str], Any]:
    """Invoke ASGI without adding a test client dependency."""
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

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        raw_headers = [(b"content-type", b"application/json")] if payload is not None else []
        raw_headers.extend((key.lower().encode(), value.encode()) for key, value in (headers or {}).items())
        await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": scheme, "path": path, "raw_path": path.encode(), "query_string": b"", "headers": raw_headers, "client": ("127.0.0.1", 0), "server": ("127.0.0.1", 80)}, receive, send)
        return messages

    messages = asyncio.run(invoke())
    start = next(message for message in messages if message["type"] == "http.response.start")
    response_headers = {key.decode(): value.decode() for key, value in start["headers"]}
    body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    content_type = response_headers.get("content-type", "").lower()
    if not body:
        parsed_body: Any = None
    elif "application/json" in content_type:
        parsed_body = json.loads(body)
    elif content_type.startswith("text/"):
        parsed_body = body.decode("utf-8")
    else:
        parsed_body = body
    return start["status"], response_headers, parsed_body


class AuthSessionTests(unittest.TestCase):
    connection: Any
    transaction: Any

    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = engine.connect()
        cls.transaction = cls.connection.begin()
        if cls.connection.execute(text("SELECT current_database()")).scalar_one() != "fyphub_p1":
            raise RuntimeError("Authentication tests require fyphub_p1.")
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
        self.email = f"auth_{uuid4().hex}@example.com"
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        user = User(full_name="Auth Test", email=self.email, registration_number=f"AUTH{uuid4().hex[:12]}", password_hash=hash_password("Correct Password!"), role=UserRole.STUDENT)
        session.add(user)
        session.commit()
        self.user_id = user.id
        self.registration_number = user.registration_number
        session.close()

    def login(self, **headers: str) -> tuple[int, dict[str, str], Any]:
        return request("POST", "/api/v1/auth/login", {"email": self.email.upper(), "password": "Correct Password!"}, headers=headers)

    @staticmethod
    def cookie_value(headers: dict[str, str]) -> str:
        return headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]

    def test_login_safe_cookie_and_me(self) -> None:
        status, headers, body = self.login(Origin="http://127.0.0.1:5174")
        self.assertEqual(status, 200)
        self.assertEqual(body["email"], self.email)
        self.assertNotIn("password", body)
        self.assertNotIn("token", body)
        cookie = headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        self.assertIn("path=/", cookie)
        self.assertNotIn("domain=", cookie)
        self.assertNotIn("secure", cookie)  # explicit 127.0.0.1 HTTP development exception
        secure_status, secure_headers, _ = request("POST", "/api/v1/auth/login", {"email": self.email, "password": "Correct Password!"}, scheme="https")
        self.assertEqual(secure_status, 200)
        self.assertIn("secure", secure_headers["set-cookie"].lower())
        token = self.cookie_value(headers)
        status, _, body = request("GET", "/api/v1/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"})
        self.assertEqual(status, 200)
        self.assertEqual(body["id"], self.user_id)

    def test_bad_unknown_and_inactive_credentials_are_generic(self) -> None:
        for payload in ({"email": self.email, "password": "wrong"}, {"email": "unknown@example.com", "password": "wrong"}):
            status, _, body = request("POST", "/api/v1/auth/login", payload)
            self.assertEqual(status, 401)
            self.assertEqual(body["detail"], "Invalid credentials.")
        self.connection.execute(text("UPDATE users SET is_active = false WHERE id = :id"), {"id": self.user_id})
        status, _, body = self.login()
        self.assertEqual((status, body["detail"]), (401, "Invalid credentials."))

    def test_creator_registration_login_and_selected_role_cannot_escalate(self) -> None:
        status, _, body = request(
            "POST",
            "/api/v1/auth/login",
            {"registration_number": self.registration_number.lower(), "password": "Correct Password!", "requested_role": "STUDENT"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["role"], "STUDENT")
        status, _, body = request(
            "POST",
            "/api/v1/auth/login",
            {"email": self.email, "password": "Correct Password!", "requested_role": "COORDINATOR"},
        )
        self.assertEqual((status, body["detail"]), (401, "Invalid credentials."))

    def test_admin_endpoint_requires_persisted_admin_role(self) -> None:
        _, headers, _ = self.login()
        student_token = self.cookie_value(headers)
        self.assertEqual(
            request("GET", "/api/v1/admin/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={student_token}"})[0],
            403,
        )
        self.connection.execute(
            text("UPDATE users SET role = CAST('ADMIN' AS user_role) WHERE id = :id"),
            {"id": self.user_id},
        )
        status, headers, body = request(
            "POST",
            "/api/v1/auth/login",
            {"email": self.email, "password": "Correct Password!", "requested_role": "ADMIN"},
        )
        self.assertEqual((status, body["role"]), (200, "ADMIN"))
        admin_token = self.cookie_value(headers)
        self.assertEqual(
            request("GET", "/api/v1/admin/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={admin_token}"})[0],
            200,
        )

    def test_missing_tampered_expired_revoked_and_deactivated_sessions(self) -> None:
        status, _, _ = request("GET", "/api/v1/auth/me")
        self.assertEqual(status, 401)
        status, _, _ = request("GET", "/api/v1/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}=tampered"})
        self.assertEqual(status, 401)
        for suffix, expires, revoked in (("expired", utc_now() - timedelta(seconds=1), None), ("revoked", utc_now() + timedelta(hours=1), utc_now())):
            token = f"{suffix}-{uuid4().hex}"
            self.connection.execute(text("INSERT INTO auth_sessions (user_id, token_hash, expires_at, revoked_at) VALUES (:user_id, :token_hash, :expires_at, :revoked_at)"), {"user_id": self.user_id, "token_hash": hash_session_token(token), "expires_at": expires, "revoked_at": revoked})
            self.assertEqual(request("GET", "/api/v1/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"})[0], 401)
        status, headers, _ = self.login()
        self.connection.execute(text("UPDATE users SET is_active = false WHERE id = :id"), {"id": self.user_id})
        self.assertEqual(request("GET", "/api/v1/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={self.cookie_value(headers)}"})[0], 401)

    def test_session_rotation_logout_and_idempotent_logout(self) -> None:
        _, first_headers, _ = self.login()
        first = self.cookie_value(first_headers)
        _, second_headers, _ = self.login(Cookie=f"{SESSION_COOKIE_NAME}={first}")
        second = self.cookie_value(second_headers)
        self.assertNotEqual(first, second)
        self.assertEqual(request("GET", "/api/v1/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={first}"})[0], 401)
        headers = {"Cookie": f"{SESSION_COOKIE_NAME}={second}", "Origin": "http://127.0.0.1:5174"}
        logout_status, logout_headers, logout_body = request("POST", "/api/v1/auth/logout", headers=headers)
        self.assertEqual(logout_status, 204)
        self.assertIsNone(logout_body)
        self.assertIn("max-age=0", logout_headers["set-cookie"].lower())
        self.assertEqual(request("GET", "/api/v1/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={second}"})[0], 401)
        self.assertEqual(request("POST", "/api/v1/auth/logout", headers=headers)[0], 204)

    def test_same_valid_session_supports_concurrent_requests(self) -> None:
        _, headers, _ = self.login()
        token = self.cookie_value(headers)
        cookie = {"Cookie": f"{SESSION_COOKIE_NAME}={token}"}
        self.assertEqual(request("GET", "/api/v1/auth/me", headers=cookie)[0], 200)
        self.assertEqual(request("GET", "/api/v1/auth/me", headers=cookie)[0], 200)

    def test_deactivation_revokes_every_active_session_for_the_user(self) -> None:
        admin = User(
            full_name="Session Admin",
            email=f"admin_{uuid4().hex}@example.com",
            registration_number=None,
            password_hash=hash_password("Admin Password!"),
            role=UserRole.ADMIN,
        )
        target = User(
            full_name="Deactivated User",
            email=f"target_{uuid4().hex}@example.com",
            registration_number=f"TARGET{uuid4().hex[:10]}",
            password_hash=hash_password("Target Password!"),
            role=UserRole.STUDENT,
        )
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        session.add_all([admin, target])
        session.flush()
        first, second = generate_session_token(), generate_session_token()
        session.add_all([
            AuthSession(user_id=target.id, token_hash=hash_session_token(first), expires_at=utc_now() + timedelta(hours=1)),
            AuthSession(user_id=target.id, token_hash=hash_session_token(second), expires_at=utc_now() + timedelta(hours=1)),
        ])
        session.commit()
        target_id = target.id
        session.close()
        status, admin_headers, _ = request(
            "POST", "/api/v1/auth/login",
            {"email": admin.email, "password": "Admin Password!", "requested_role": "ADMIN"},
        )
        self.assertEqual(status, 200)
        admin_cookie = self.cookie_value(admin_headers)
        status, _, _ = request(
            "PATCH",
            f"/api/v1/admin/users/{target_id}/status",
            {"is_active": False},
            headers={"Cookie": f"{SESSION_COOKIE_NAME}={admin_cookie}", "Origin": "http://localhost:5173"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(request("GET", "/api/v1/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={first}"})[0], 401)
        self.assertEqual(request("GET", "/api/v1/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={second}"})[0], 401)
        active_sessions = self.connection.execute(
            text("SELECT count(*) FROM auth_sessions WHERE user_id = :user_id AND revoked_at IS NULL"),
            {"user_id": target_id},
        ).scalar_one()
        self.assertEqual(active_sessions, 0)

    def test_origin_cors_and_role_helpers(self) -> None:
        self.assertEqual(self.login(Origin="https://evil.example")[0], 403)
        self.assertEqual(request("POST", "/api/v1/auth/logout", headers={"Origin": "https://evil.example"})[0], 403)
        status, headers, _ = request("OPTIONS", "/api/v1/auth/login", headers={"Origin": "http://127.0.0.1:5174", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["access-control-allow-origin"], "http://127.0.0.1:5174")
        self.assertEqual(headers["access-control-allow-credentials"], "true")
        origin = "http://localhost:5173"
        status, headers, _ = request("OPTIONS", "/api/v1/auth/login", headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["access-control-allow-origin"], origin)
        self.assertEqual(headers["access-control-allow-credentials"], "true")
        status, headers, _ = self.login(Origin=origin)
        self.assertEqual(status, 200)
        self.assertEqual(headers["access-control-allow-origin"], origin)
        self.assertEqual(headers["access-control-allow-credentials"], "true")
        self.assertNotIn("secure", headers["set-cookie"].lower())
        self.assertEqual(self.login(Origin="http://localhost:5174")[0], 403)
        student_guard = require_roles(UserRole.ADMIN)
        fixture_user = User(full_name="Role Test", email="role@example.com", registration_number="ROLE-TEST", password_hash="test", role=UserRole.STUDENT)
        with self.assertRaises(HTTPException) as denied:
            student_guard(fixture_user)
        self.assertEqual(denied.exception.status_code, 403)
        fixture_user.role = UserRole.ADMIN
        self.assertIs(student_guard(fixture_user), fixture_user)
