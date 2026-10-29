"""Integration tests for public student registration."""

import asyncio
import json
import unittest
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app
from app.models import User
from app.security import hash_password, verify_password


def request_json(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Make an in-process ASGI request without requiring a test HTTP client package."""

    async def invoke() -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        body = json.dumps(payload).encode()
        received = False

        async def receive() -> dict[str, Any]:
            nonlocal received
            if not received:
                received = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/auth/register",
            "raw_path": b"/api/v1/auth/register",
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
            "client": ("127.0.0.1", 0),
            "server": ("testserver", 80),
        }
        await app(scope, receive, send)
        return messages

    messages = asyncio.run(invoke())
    start = next(message for message in messages if message["type"] == "http.response.start")
    body = next(message for message in messages if message["type"] == "http.response.body")["body"]
    return start["status"], json.loads(body)


class RegistrationIntegrationTests(unittest.TestCase):
    """Registration tests whose database writes are rolled back as one outer transaction."""

    connection: Any
    transaction: Any

    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = engine.connect()
        cls.transaction = cls.connection.begin()
        database_name = cls.connection.execute(text("SELECT current_database()")).scalar_one()
        if database_name != "fyphub_p1":
            raise RuntimeError("Registration integration tests require fyphub_p1.")
        app.dependency_overrides[get_db] = cls.get_test_db

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.pop(get_db, None)
        cls.transaction.rollback()
        cls.connection.close()

    @classmethod
    def get_test_db(cls) -> Iterator[Session]:
        session = Session(
            bind=cls.connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            session.close()

    @staticmethod
    def payload(**overrides: Any) -> dict[str, Any]:
        data: dict[str, Any] = {
            "full_name": "Test Student",
            "email": "student@example.com",
            "registration_number": "fyp-001",
            "password": "ValidPass123!",
        }
        data.update(overrides)
        return data

    def test_password_hashing_and_verification(self) -> None:
        password = "Case Sensitive Password!"
        password_hash = hash_password(password)
        self.assertNotEqual(password_hash, password)
        self.assertTrue(verify_password(password, password_hash))
        self.assertFalse(verify_password("Case Sensitive Password?", password_hash))

    def test_successful_student_registration_stores_only_hash(self) -> None:
        password = "ValidPass123!"
        status_code, response = request_json(
            self.payload(email="Student@Example.com", registration_number=" fyp-101 ")
        )

        self.assertEqual(status_code, 201)
        self.assertEqual(response["email"], "student@example.com")
        self.assertEqual(response["registration_number"], "FYP-101")
        self.assertEqual(response["role"], "STUDENT")
        self.assertNotIn("password", response)
        self.assertNotIn("password_hash", response)

        user = self.connection.execute(
            text("SELECT password_hash FROM users WHERE email = :email"),
            {"email": "student@example.com"},
        ).scalar_one()
        self.assertNotEqual(user, password)
        self.assertTrue(verify_password(password, user))

    def test_demo_mode_allows_unlisted_student_and_records_mode(self) -> None:
        with patch.dict("os.environ", {"REGISTRATION_MODE": "demo"}):
            status_code, response = request_json(
                self.payload(email="demo-unlisted@example.com", registration_number="DEMO-UNLISTED")
            )
        self.assertEqual(status_code, 201)
        mode = self.connection.execute(
            text("SELECT changed_values->>'registration_mode' FROM admin_audit_events WHERE affected_user_id=:id AND action='student_registration_created'"),
            {"id": response["id"]},
        ).scalar_one()
        self.assertEqual(mode, "demo")

    def test_duplicate_normalized_email_returns_conflict(self) -> None:
        self.assertEqual(
            request_json(self.payload(email="duplicate-email@example.com", registration_number="FYP-201"))[0],
            201,
        )
        status_code, response = request_json(
            self.payload(email="DUPLICATE-EMAIL@EXAMPLE.COM", registration_number="FYP-202")
        )
        self.assertEqual(status_code, 409)
        self.assertNotIn("password", response)
        self.assertNotIn("password_hash", response)

    def test_common_consumer_and_institutional_domains_are_accepted(self) -> None:
        for index, address in enumerate(
            ("person@gmail.com", "person@outlook.com", "person@yahoo.com", "person@szabist-isb.pk"),
            start=1,
        ):
            with self.subTest(address=address):
                status_code, response = request_json(
                    self.payload(email=address, registration_number=f"FYP-COMMON-{index}")
                )
                self.assertEqual(status_code, 201)
                self.assertEqual(response["email"], address)

    def test_duplicate_normalized_registration_number_returns_conflict(self) -> None:
        self.assertEqual(
            request_json(self.payload(email="registration-one@example.com", registration_number="fyp-301"))[0],
            201,
        )
        status_code, response = request_json(
            self.payload(email="registration-two@example.com", registration_number=" FYP-301 ")
        )
        self.assertEqual(status_code, 409)
        self.assertNotIn("password", response)
        self.assertNotIn("password_hash", response)

    def test_invalid_email_missing_fields_and_password_lengths_are_rejected(self) -> None:
        for invalid_email in (
            "not-an-email",
            "missing-domain@",
            "missing-dot@example",
            "has space@example.com",
            "double..dot@example.com",
            ".leading@example.com",
            "trailing.@example.com",
            "user@.example.com",
            "user@example.com.",
            "two@@example.com",
        ):
            with self.subTest(invalid_email=invalid_email):
                self.assertEqual(request_json(self.payload(email=invalid_email))[0], 422)
        status_code, response = request_json(
            self.payload(email=" Student@Szabist-Isb.Pk ", registration_number="FYP-150")
        )
        self.assertEqual(status_code, 201)
        self.assertEqual(response["email"], "student@szabist-isb.pk")
        incomplete = self.payload()
        incomplete.pop("full_name")
        self.assertEqual(request_json(incomplete)[0], 422)
        self.assertEqual(request_json(self.payload(full_name="   "))[0], 422)
        self.assertEqual(request_json(self.payload(registration_number="   "))[0], 422)
        self.assertEqual(request_json(self.payload(email="short@example.com", password="short"))[0], 422)
        self.assertEqual(
            request_json(self.payload(email="long@example.com", password="x" * 129))[0], 422
        )

    def test_privileged_request_fields_are_rejected(self) -> None:
        self.assertEqual(
            request_json(self.payload(email="role@example.com", role="ADMIN"))[0], 422
        )
        self.assertEqual(
            request_json(self.payload(email="active@example.com", is_active=False))[0], 422
        )
