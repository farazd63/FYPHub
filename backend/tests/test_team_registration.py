"""Rollback-isolated API tests for shared-team registration."""

from __future__ import annotations

import asyncio
import json
import os
import unittest
from collections.abc import Iterator
from typing import Any
from uuid import uuid4
from unittest.mock import patch

from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app
from app.models import TeamMember
from app.security import verify_password


def request_json(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Call the endpoint in process, without starting a server or adding a client library."""

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

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/api/v1/team-registration",
                "raw_path": b"/api/v1/team-registration",
                "query_string": b"",
                "headers": [(b"content-type", b"application/json")],
                "client": ("127.0.0.1", 0),
                "server": ("testserver", 80),
            },
            receive,
            send,
        )
        return messages

    messages = asyncio.run(invoke())
    start = next(message for message in messages if message["type"] == "http.response.start")
    body = next(message for message in messages if message["type"] == "http.response.body")["body"]
    return start["status"], json.loads(body)


def cors_preflight(origin: str) -> tuple[int, dict[str, str]]:
    """Exercise CORS without a running HTTP server."""

    async def invoke() -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "OPTIONS",
                "scheme": "http",
                "path": "/api/v1/team-registration",
                "raw_path": b"/api/v1/team-registration",
                "query_string": b"",
                "headers": [
                    (b"origin", origin.encode()),
                    (b"access-control-request-method", b"POST"),
                    (b"access-control-request-headers", b"content-type"),
                ],
                "client": ("127.0.0.1", 0),
                "server": ("testserver", 80),
            },
            receive,
            send,
        )
        return messages

    messages = asyncio.run(invoke())
    start = next(message for message in messages if message["type"] == "http.response.start")
    headers = {key.decode(): value.decode() for key, value in start["headers"]}
    return start["status"], headers


class TeamRegistrationApiTests(unittest.TestCase):
    """API writes share an outer transaction and never retain fixture data."""

    connection: Any
    transaction: Any

    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = engine.connect()
        cls.transaction = cls.connection.begin()
        database_name = cls.connection.execute(text("SELECT current_database()")).scalar_one()
        if database_name != "fyphub_p1":
            cls.transaction.rollback()
            cls.connection.close()
            raise RuntimeError("Team-registration integration tests require fyphub_p1.")
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

    def setUp(self) -> None:
        self.prefix = f"tr_{uuid4().hex[:12]}"
        self.cycle_index = 0

    def email(self, suffix: str) -> str:
        return f"{self.prefix}_{suffix}@example.com"

    def registration(self, suffix: str) -> str:
        return f"{self.prefix}_{suffix}".upper()

    def create_cycle(self, *, open_for_registration: bool, with_policy: bool = True, max_size: int = 3, seed_roster: bool = True) -> int:
        self.cycle_index += 1
        cycle_id = self.connection.execute(
            text(
                """
                INSERT INTO academic_cycles (code, display_name, registration_open)
                VALUES (:code, :display_name, :registration_open)
                RETURNING id
                """
            ),
            {
                "code": self.registration(f"cycle-{self.cycle_index}"),
                "display_name": f"Team registration {self.prefix} {self.cycle_index}",
                "registration_open": open_for_registration,
            },
        ).scalar_one()
        if with_policy:
            self.connection.execute(
                text(
                    """
                    INSERT INTO academic_group_policies (academic_cycle_id, max_group_size)
                    VALUES (:cycle_id, :max_size)
                    """
                ),
                {"cycle_id": cycle_id, "max_size": max_size},
            )
        if seed_roster:
            self.seed_roster(cycle_id, [
                (self.registration("creator"), self.email("creator-contact")),
                (self.registration("member"), self.email("member-contact")),
            ])
        return cycle_id

    def seed_roster(self, cycle_id: int, entries: list[tuple[str, str]]) -> None:
        actor = self.connection.execute(text("""
            INSERT INTO users (full_name, email, password_hash, role, is_active)
            VALUES ('Roster fixture', :email, 'test-hash', CAST('ADMIN' AS user_role), true)
            RETURNING id
        """), {"email": self.email(f"roster-admin-{uuid4().hex}")}).scalar_one()
        batch = self.connection.execute(text("""
            INSERT INTO roster_imports (academic_cycle_id, imported_by_id, confirmation_hash)
            VALUES (:cycle, :actor, :hash) RETURNING id
        """), {"cycle": cycle_id, "actor": actor, "hash": uuid4().hex}).scalar_one()
        for number, email in entries:
            self.connection.execute(text("""
                INSERT INTO approved_students (academic_cycle_id, import_id, name, registration_number, university_email, semester, group_code)
                VALUES (:cycle, :batch, 'Fixture student', :number, :email, 7, 'fixture')
            """), {"cycle": cycle_id, "batch": batch, "number": number, "email": email.lower()})

    def payload(self, cycle_id: int, **overrides: Any) -> dict[str, Any]:
        data: dict[str, Any] = {
            "academic_cycle_id": cycle_id,
            "creator": {
                "full_name": "Creator Student",
                "registration_number": self.registration("creator"),
                "university_email": self.email("creator-contact"),
            },
            "shared_login_email": self.email("shared-login"),
            "password": "CaseSensitivePassword1!",
            "members": [
                {
                    "full_name": "Member Student",
                    "registration_number": self.registration("member"),
                    "university_email": self.email("member-contact"),
                }
            ],
        }
        data.update(overrides)
        return data

    def detail_code(self, response: dict[str, Any]) -> str:
        return response["detail"]["code"]

    def test_successful_team_registration_creates_one_user_and_one_creator(self) -> None:
        cycle_id = self.create_cycle(open_for_registration=True, max_size=3)
        password = "CaseSensitivePassword1!"
        status_code, response = request_json(self.payload(cycle_id))

        self.assertEqual(status_code, 201)
        self.assertEqual(response["account"]["role"], "STUDENT")
        self.assertEqual(response["team"]["academic_cycle_id"], cycle_id)
        self.assertEqual(len(response["members"]), 2)
        self.assertEqual(sum(member["is_creator"] for member in response["members"]), 1)
        self.assertNotIn("password", response)
        self.assertNotIn("password_hash", response)

        account_id = response["account"]["id"]
        user_count = self.connection.execute(
            text("SELECT count(*) FROM users WHERE id = :id"), {"id": account_id}
        ).scalar_one()
        member_count = self.connection.execute(
            text("SELECT count(*) FROM team_members WHERE team_id = :team_id"),
            {"team_id": response["team"]["id"]},
        ).scalar_one()
        password_hash = self.connection.execute(
            text("SELECT password_hash FROM users WHERE id = :id"), {"id": account_id}
        ).scalar_one()
        self.assertEqual(user_count, 1)
        self.assertEqual(member_count, 2)
        self.assertNotEqual(password_hash, password)
        self.assertTrue(verify_password(password, password_hash))

    def test_cors_allows_only_the_configured_frontend_origin(self) -> None:
        for origin in ("http://127.0.0.1:5173", "http://localhost:5173"):
            allowed_status, allowed_headers = cors_preflight(origin)
            self.assertEqual(allowed_status, 200)
            self.assertEqual(allowed_headers.get("access-control-allow-origin"), origin)
            self.assertEqual(allowed_headers.get("access-control-allow-credentials"), "true")

        denied_status, denied_headers = cors_preflight("http://127.0.0.1:5174")
        self.assertEqual(denied_status, 400)
        self.assertNotIn("access-control-allow-origin", denied_headers)

    def test_unknown_closed_and_missing_policy_cycles_return_safe_errors(self) -> None:
        unknown_status, unknown_response = request_json(self.payload(999999999))
        self.assertEqual(unknown_status, 404)
        self.assertEqual(self.detail_code(unknown_response), "academic_cycle_not_found")

        closed_cycle = self.create_cycle(open_for_registration=False)
        closed_status, closed_response = request_json(self.payload(closed_cycle))
        self.assertEqual(closed_status, 409)
        self.assertEqual(self.detail_code(closed_response), "academic_cycle_closed")

        no_policy_cycle = self.create_cycle(open_for_registration=True, with_policy=False)
        policy_status, policy_response = request_json(self.payload(no_policy_cycle))
        self.assertEqual(policy_status, 409)
        self.assertEqual(self.detail_code(policy_response), "academic_group_policy_missing")

    def test_configured_maximum_boundary_and_excess_members(self) -> None:
        boundary_cycle = self.create_cycle(open_for_registration=True, max_size=2)
        self.assertEqual(request_json(self.payload(boundary_cycle))[0], 201)

        excess_cycle = self.create_cycle(open_for_registration=True, max_size=1)
        status_code, response = request_json(self.payload(excess_cycle))
        self.assertEqual(status_code, 422)
        self.assertEqual(self.detail_code(response), "group_size_exceeded")
        self.assertEqual(response["detail"]["field"], "members")

    def test_request_and_existing_record_duplicate_conflicts(self) -> None:
        cycle_id = self.create_cycle(open_for_registration=True)
        duplicate_request = self.payload(cycle_id)
        duplicate_request["members"][0]["registration_number"] = duplicate_request["creator"]["registration_number"].lower()
        status_code, response = request_json(duplicate_request)
        self.assertEqual(status_code, 422)
        self.assertEqual(self.detail_code(response), "duplicate_request_registration_number")

        existing = self.payload(cycle_id)
        self.assertEqual(request_json(existing)[0], 201)
        conflicting = self.payload(
            cycle_id,
            shared_login_email=self.email("other-login"),
            creator={
                "full_name": "Another Creator",
                "registration_number": self.registration("other-creator"),
                "university_email": self.email("other-creator-contact"),
            },
            members=[
                {
                    "full_name": "Conflicting member",
                    "registration_number": self.registration("member"),
                    "university_email": self.email("other-member-contact"),
                }
            ],
        )
        status_code, response = request_json(conflicting)
        self.assertEqual(status_code, 409)
        self.assertEqual(self.detail_code(response), "member_registration_exists")

    def test_creator_registration_used_by_individual_account_is_rejected(self) -> None:
        cycle_id = self.create_cycle(open_for_registration=True)
        registration = self.registration("individual")
        self.connection.execute(
            text(
                """
                INSERT INTO users (full_name, email, registration_number, password_hash, role, is_active)
                VALUES ('Individual Student', :email, :registration, 'test-hash', CAST('STUDENT' AS user_role), true)
                """
            ),
            {"email": self.email("individual"), "registration": registration},
        )
        request = self.payload(
            cycle_id,
            creator={
                "full_name": "Creator Student",
                "registration_number": registration,
                "university_email": self.email("creator-contact"),
            },
        )
        status_code, response = request_json(request)
        self.assertEqual(status_code, 409)
        self.assertEqual(self.detail_code(response), "creator_registration_exists")
        self.assertEqual(response["detail"]["field"], "creator.registration_number")

    def test_invalid_and_privileged_fields_are_rejected(self) -> None:
        cycle_id = self.create_cycle(open_for_registration=True)
        invalid = self.payload(cycle_id, password="short")
        status_code, response = request_json(invalid)
        self.assertEqual(status_code, 422)
        self.assertEqual(self.detail_code(response), "invalid_password_length")

        privileged = self.payload(cycle_id, role="ADMIN")
        status_code, response = request_json(privileged)
        self.assertEqual(status_code, 422)
        self.assertEqual(self.detail_code(response), "invalid_request")
        self.assertEqual(response["detail"]["fields"][0]["path"], "role")
        self.assertNotIn("password", response)

    def test_late_member_insert_failure_rolls_back_all_new_records(self) -> None:
        cycle_id = self.create_cycle(open_for_registration=True)
        request = self.payload(cycle_id)

        def fail_member_insert(*_: Any) -> None:
            raise IntegrityError("forced team-member insert failure", {}, Exception("forced"))

        event.listen(TeamMember, "before_insert", fail_member_insert)
        try:
            status_code, response = request_json(request)
        finally:
            event.remove(TeamMember, "before_insert", fail_member_insert)

        self.assertEqual(status_code, 409)
        self.assertEqual(self.detail_code(response), "duplicate_conflict")
        self.assertEqual(
            self.connection.execute(
                text("SELECT count(*) FROM users WHERE email = :email"),
                {"email": request["shared_login_email"]},
            ).scalar_one(),
            0,
        )
        self.assertEqual(
            self.connection.execute(
                text("SELECT count(*) FROM teams WHERE academic_cycle_id = :cycle_id"),
                {"cycle_id": cycle_id},
            ).scalar_one(),
            0,
        )

    def test_safe_error_for_existing_shared_login_email(self) -> None:
        cycle_id = self.create_cycle(open_for_registration=True)
        request = self.payload(cycle_id)
        self.assertEqual(request_json(request)[0], 201)
        conflict = self.payload(
            cycle_id,
            creator={
                "full_name": "Other Creator",
                "registration_number": self.registration("other-creator"),
                "university_email": self.email("other-creator-contact"),
            },
            members=[],
        )
        status_code, response = request_json(conflict)
        self.assertEqual(status_code, 409)
        self.assertEqual(self.detail_code(response), "shared_login_email_exists")
        self.assertNotIn("password", response)
        self.assertNotIn("password_hash", response)


class TeamEligibilityTests(TeamRegistrationApiTests):
    """Roster enforcement uses the selected cycle and each member's contact email."""

    def assert_no_registration(self, cycle_id: int, payload: dict[str, Any]) -> None:
        self.assertEqual(self.connection.execute(text("SELECT count(*) FROM users WHERE email=:email"), {"email": payload["shared_login_email"]}).scalar_one(), 0)
        self.assertEqual(self.connection.execute(text("SELECT count(*) FROM teams WHERE academic_cycle_id=:id"), {"id": cycle_id}).scalar_one(), 0)
        self.assertEqual(self.connection.execute(text("SELECT count(*) FROM team_members WHERE academic_cycle_id=:id"), {"id": cycle_id}).scalar_one(), 0)

    def test_missing_creator_and_member_are_field_specific_and_atomic(self) -> None:
        for missing in ("creator", "member"):
            with self.subTest(missing=missing):
                cycle = self.create_cycle(open_for_registration=True, seed_roster=False)
                payload = self.payload(cycle)
                selected = payload["members"][0] if missing == "creator" else payload["creator"]
                self.seed_roster(cycle, [(selected["registration_number"], selected["university_email"])])
                status, response = request_json(payload)
                self.assertEqual(status, 422)
                self.assertEqual(response["detail"]["code"], "student_not_eligible")
                self.assertEqual(response["detail"]["field"], "creator.registration_number" if missing == "creator" else "members.0.registration_number")
                self.assertNotIn(selected["university_email"], str(response))
                self.assert_no_registration(cycle, payload)

    def test_wrong_cycle_and_mismatched_pair_are_rejected(self) -> None:
        other = self.create_cycle(open_for_registration=True)
        cycle = self.create_cycle(open_for_registration=True, seed_roster=False)
        payload = self.payload(cycle)
        status, _ = request_json(payload)
        self.assertEqual(status, 422)
        self.assert_no_registration(cycle, payload)
        self.seed_roster(cycle, [(payload["creator"]["registration_number"], payload["members"][0]["university_email"]), (payload["members"][0]["registration_number"], payload["creator"]["university_email"])])
        status, response = request_json(payload)
        self.assertEqual(status, 422)
        self.assertEqual(response["detail"]["field"], "creator.registration_number")
        self.assert_no_registration(cycle, payload)
        self.assertNotEqual(other, cycle)

    def test_normalization_and_shared_login_is_not_contact_email(self) -> None:
        cycle = self.create_cycle(open_for_registration=True, seed_roster=False)
        payload = self.payload(cycle)
        self.seed_roster(cycle, [("001abc", payload["creator"]["university_email"]), ("002abc", payload["members"][0]["university_email"])])
        payload["creator"]["registration_number"] = " 001ABC "
        payload["members"][0]["registration_number"] = "002AbC"
        payload["creator"]["university_email"] = payload["creator"]["university_email"].upper()
        self.assertNotEqual(payload["shared_login_email"], payload["creator"]["university_email"].lower())
        self.assertEqual(request_json(payload)[0], 201)

    def test_invalid_semester_is_rejected_by_roster_constraint(self) -> None:
        from sqlalchemy.exc import IntegrityError
        cycle = self.create_cycle(open_for_registration=True)
        payload = self.payload(cycle)
        savepoint = self.connection.begin_nested()
        try:
            with self.assertRaises(IntegrityError):
                self.connection.execute(text("UPDATE approved_students SET semester=6 WHERE academic_cycle_id=:id"), {"id": cycle})
        finally:
            savepoint.rollback()
        self.assertEqual(request_json(payload)[0], 201)

    def test_demo_mode_allows_unlisted_one_two_and_three_member_teams(self) -> None:
        with patch.dict(os.environ, {"REGISTRATION_MODE": "demo"}):
            one_cycle = self.create_cycle(open_for_registration=True, max_size=1, seed_roster=False)
            one = self.payload(one_cycle, members=[])
            self.assertEqual(request_json(one)[0], 201)

            two_cycle = self.create_cycle(open_for_registration=True, max_size=2, seed_roster=False)
            two = self.payload(two_cycle)
            two["creator"]["registration_number"] = self.registration("creator-two")
            two["creator"]["university_email"] = self.email("creator-two-contact")
            two["shared_login_email"] = self.email("shared-login-two")
            two["members"][0]["registration_number"] = self.registration("member-two")
            two["members"][0]["university_email"] = self.email("member-two-contact")
            self.assertEqual(request_json(two)[0], 201)

            three_cycle = self.create_cycle(open_for_registration=True, max_size=3, seed_roster=False)
            three = self.payload(three_cycle, members=[
                {"full_name": "Second Student", "registration_number": self.registration("member-three"), "university_email": self.email("member-three-contact")},
                {"full_name": "Third Student", "registration_number": self.registration("third"), "university_email": self.email("third-contact")},
            ])
            three["creator"]["registration_number"] = self.registration("creator-three")
            three["creator"]["university_email"] = self.email("creator-three-contact")
            three["shared_login_email"] = self.email("shared-login-three")
            self.assertEqual(request_json(three)[0], 201)

    def test_restricted_mode_and_invalid_mode_keep_roster_validation(self) -> None:
        cycle = self.create_cycle(open_for_registration=True, seed_roster=False)
        payload = self.payload(cycle, members=[])
        for configured in ("restricted", "invalid", None):
            environment = {} if configured is None else {"REGISTRATION_MODE": configured}
            with self.subTest(configured=configured), patch.dict(os.environ, environment, clear=configured is None):
                status_code, response = request_json(payload)
                self.assertEqual(status_code, 422)
                self.assertEqual(self.detail_code(response), "student_not_eligible")

    def test_demo_mode_records_audit_metadata_without_changing_security_validation(self) -> None:
        cycle = self.create_cycle(open_for_registration=True, seed_roster=False)
        payload = self.payload(cycle, members=[])
        with patch.dict(os.environ, {"REGISTRATION_MODE": "demo"}):
            status_code, response = request_json(payload)
        self.assertEqual(status_code, 201)
        mode = self.connection.execute(text(
            "SELECT changed_values->>'registration_mode' FROM admin_audit_events WHERE affected_user_id=:id AND action='team_registration_created'"
        ), {"id": response["account"]["id"]}).scalar_one()
        self.assertEqual(mode, "demo")

    def test_demo_mode_still_enforces_group_limit(self) -> None:
        cycle = self.create_cycle(open_for_registration=True, max_size=2, seed_roster=False)
        payload = self.payload(cycle, members=[
            self.payload(cycle)["members"][0],
            {"full_name": "Third Student", "registration_number": self.registration("third-limit"), "university_email": self.email("third-limit")},
        ])
        with patch.dict(os.environ, {"REGISTRATION_MODE": "demo"}):
            status_code, response = request_json(payload)
        self.assertEqual(status_code, 422)
        self.assertEqual(self.detail_code(response), "group_size_exceeded")
