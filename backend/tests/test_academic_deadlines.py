"""Rollback-isolated coverage for non-operational academic deadlines."""

import threading
import unittest
from collections.abc import Iterator
from uuid import uuid4
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.orm import Session

from app import main
from app.auth import SESSION_COOKIE_NAME, utc_now
from app.database import SessionLocal, engine, get_db
from app.main import app, create_academic_deadline_version
from app.models import AcademicCycle, AcademicDeadline, AcademicDeadlineVersion, AuthSession, User, UserRole
from app.schemas.academic_deadlines import DeadlineWrite
from app.security import generate_session_token, hash_session_token
from tests.test_auth_sessions import request


class AcademicDeadlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = engine.connect()
        cls.transaction = cls.connection.begin()
        if cls.connection.execute(text("select current_database()" )).scalar_one() != "fyphub_p1":
            raise RuntimeError("Academic-deadline tests require fyphub_p1.")
        app.dependency_overrides[get_db] = cls.db

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.pop(get_db, None)
        cls.transaction.rollback()
        cls.connection.close()

    @classmethod
    def db(cls) -> Iterator[Session]:
        session = Session(bind=cls.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()

    def setUp(self) -> None:
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        suffix = uuid4().hex[:10]
        admin = User(full_name="Deadline Admin", email=f"deadline-{suffix}@example.com", password_hash="test", role=UserRole.ADMIN)
        student = User(full_name="Deadline Student", email=f"deadline-student-{suffix}@example.com", registration_number=f"D{suffix}", password_hash="test", role=UserRole.STUDENT)
        cycle = AcademicCycle(code=f"D-{suffix}", display_name=f"Deadline cycle {suffix}")
        session.add_all([admin, student, cycle])
        session.flush()
        self.admin_id, self.cycle_id = admin.id, cycle.id
        self.admin_token, self.student_token = generate_session_token(), generate_session_token()
        session.add_all([
            AuthSession(user_id=admin.id, token_hash=hash_session_token(self.admin_token), expires_at=utc_now().replace(year=utc_now().year + 1)),
            AuthSession(user_id=student.id, token_hash=hash_session_token(self.student_token), expires_at=utc_now().replace(year=utc_now().year + 1)),
        ])
        session.commit()
        session.close()

    def headers(self, token: str | None = None, origin: str | None = None) -> dict[str, str]:
        headers = {} if token is None else {"cookie": f"{SESSION_COOKIE_NAME}={token}"}
        if origin is not None:
            headers["origin"] = origin
        return headers

    def payload(self, name: str = "Administrator supplied deadline") -> dict[str, object]:
        return {
            "academic_cycle_id": self.cycle_id,
            "name": name,
            "description": "Configuration only",
            "local_due_at": "2026-10-19T12:00",
            "time_zone": "Asia/Karachi",
            "utc_offset": "+05:00",
            "due_at_utc": "2026-10-19T07:00:00Z",
        }

    def test_authorization_and_origin_rejection(self) -> None:
        self.assertEqual(request("GET", "/api/v1/admin/academic-deadlines")[0], 401)
        self.assertEqual(request("GET", "/api/v1/admin/academic-deadlines", headers=self.headers(self.student_token))[0], 403)
        self.assertEqual(request("POST", "/api/v1/admin/academic-deadlines/preview", {"local_due_at": "2026-10-19T12:00", "time_zone": "Asia/Karachi"}, headers=self.headers(self.admin_token, "http://evil.example"))[0], 403)
        self.assertEqual(request("POST", "/api/v1/admin/academic-deadlines", self.payload(), headers=self.headers(self.admin_token, "http://evil.example"))[0], 403)

    def test_unknown_cycle_and_strict_validation(self) -> None:
        unknown = {**self.payload(), "academic_cycle_id": 999999}
        status_code, _, body = request("POST", "/api/v1/admin/academic-deadlines", unknown, headers=self.headers(self.admin_token))
        self.assertEqual(status_code, 404)
        self.assertEqual(body["detail"]["code"], "cycle_not_found")
        invalid = [
            {**self.payload(), "name": "   "},
            {**self.payload(), "due_at_utc": "2026-10-19T07:00:00"},
            {**self.payload(), "unexpected": True},
            {**self.payload(), "local_due_at": "not-a-time"},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertEqual(request("POST", "/api/v1/admin/academic-deadlines", payload, headers=self.headers(self.admin_token))[0], 422)

    def test_naive_writes_leave_versions_and_audit_unchanged(self) -> None:
        def counts() -> tuple[int, int, int]:
            return tuple(self.connection.execute(text(query), {"actor": self.admin_id, "cycle": self.cycle_id}).scalar_one() for query in (
                "select count(*) from academic_deadlines where academic_cycle_id = :cycle",
                "select count(*) from academic_deadline_versions where created_by_id = :actor",
                "select count(*) from admin_audit_events where actor_id = :actor",
            ))

        before = counts()
        naive = {**self.payload(), "due_at_utc": "2026-10-19T07:00:00"}
        self.assertEqual(request("POST", "/api/v1/admin/academic-deadlines", naive, headers=self.headers(self.admin_token))[0], 422)
        self.assertEqual(counts(), before)
        status_code, _, initial = request("POST", "/api/v1/admin/academic-deadlines", self.payload(), headers=self.headers(self.admin_token))
        self.assertEqual(status_code, 201)
        before = counts()
        version = {key: value for key, value in naive.items() if key != "academic_cycle_id"}
        self.assertEqual(request("POST", f"/api/v1/admin/academic-deadlines/{initial['id']}/versions", version, headers=self.headers(self.admin_token))[0], 422)
        self.assertEqual(counts(), before)

    def test_missing_timezone_data_returns_service_error(self) -> None:
        with patch.object(main, "ZoneInfo", side_effect=ZoneInfoNotFoundError("unavailable")):
            for method, path, payload in (
                ("GET", "/api/v1/admin/time-zones", None),
                ("POST", "/api/v1/admin/academic-deadlines/preview", {"local_due_at": "2026-10-19T12:00", "time_zone": "Asia/Karachi"}),
            ):
                status_code, _, body = request(method, path, payload, headers=self.headers(self.admin_token))
                self.assertEqual(status_code, 503)
                self.assertEqual(body["detail"]["code"], "timezone_data_unavailable")

    def test_timezone_conversion_mismatch_gap_and_overlap(self) -> None:
        status_code, _, preview = request("POST", "/api/v1/admin/academic-deadlines/preview", {"local_due_at": "2026-10-19T12:00", "time_zone": "Asia/Karachi"}, headers=self.headers(self.admin_token))
        self.assertEqual(status_code, 200)
        self.assertEqual(preview["utc_offset"], "+05:00")
        self.assertEqual(preview["due_at_utc"], "2026-10-19T07:00:00Z")
        cases = [
            ({"local_due_at": "2026-10-19T12:00", "time_zone": "Invalid/Zone"}, 422, "invalid_time_zone"),
            ({"local_due_at": "2026-10-19T12:00", "time_zone": "Asia/Karachi", "utc_offset": "+04:00"}, 422, "offset_timezone_mismatch"),
            ({"local_due_at": "2026-03-08T02:30", "time_zone": "America/New_York"}, 422, "nonexistent_local_time"),
            ({"local_due_at": "2026-11-01T01:30", "time_zone": "America/New_York"}, 409, "ambiguous_local_time"),
        ]
        for payload, expected_status, code in cases:
            with self.subTest(code=code):
                status_code, _, body = request("POST", "/api/v1/admin/academic-deadlines/preview", payload, headers=self.headers(self.admin_token))
                self.assertEqual(status_code, expected_status)
                self.assertEqual(body["detail"]["code"], code)
        status_code, _, overlap = request("POST", "/api/v1/admin/academic-deadlines/preview", {"local_due_at": "2026-11-01T01:30", "time_zone": "America/New_York", "utc_offset": "-05:00"}, headers=self.headers(self.admin_token))
        self.assertEqual(status_code, 200)
        self.assertEqual(overlap["due_at_utc"], "2026-11-01T06:30:00Z")
        mismatch = {**self.payload(), "due_at_utc": "2026-10-19T08:00:00Z"}
        status_code, _, body = request("POST", "/api/v1/admin/academic-deadlines", mismatch, headers=self.headers(self.admin_token))
        self.assertEqual(status_code, 422)
        self.assertEqual(body["detail"]["code"], "deadline_preview_mismatch")

    def test_initial_subsequent_and_ordered_history(self) -> None:
        status_code, _, initial = request("POST", "/api/v1/admin/academic-deadlines", self.payload(), headers=self.headers(self.admin_token))
        self.assertEqual(status_code, 201)
        deadline_id = initial["id"]
        next_payload = {key: value for key, value in self.payload("Revised administrator deadline").items() if key != "academic_cycle_id"}
        next_payload.update({"local_due_at": "2026-10-20T12:00", "due_at_utc": "2026-10-20T07:00:00Z"})
        self.assertEqual(request("POST", f"/api/v1/admin/academic-deadlines/{deadline_id}/versions", next_payload, headers=self.headers(self.admin_token))[0], 201)
        status_code, _, history = request("GET", f"/api/v1/admin/academic-deadlines/{deadline_id}", headers=self.headers(self.admin_token))
        self.assertEqual(status_code, 200)
        self.assertEqual(history["academic_cycle_id"], self.cycle_id)
        self.assertEqual([item["version_number"] for item in history["versions"]], [1, 2])
        self.assertEqual(history["versions"][0]["name"], "Administrator supplied deadline")
        self.assertEqual(history["versions"][0]["due_at_utc"], "2026-10-19T07:00:00Z")

    def test_audit_failure_rolls_back_subsequent_version(self) -> None:
        status_code, _, initial = request("POST", "/api/v1/admin/academic-deadlines", self.payload(), headers=self.headers(self.admin_token))
        self.assertEqual(status_code, 201)
        deadline_id = initial["id"]
        original = main.add_admin_audit_event
        main.add_admin_audit_event = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("audit failure"))
        try:
            payload = {key: value for key, value in self.payload("Must roll back").items() if key != "academic_cycle_id"}
            status_code, _, body = request("POST", f"/api/v1/admin/academic-deadlines/{deadline_id}/versions", payload, headers=self.headers(self.admin_token))
        finally:
            main.add_admin_audit_event = original
        self.assertEqual(status_code, 500)
        self.assertEqual(body["detail"]["code"], "deadline_save_failed")
        self.assertEqual(self.connection.execute(text("select count(*) from academic_deadline_versions where academic_deadline_id=:id"), {"id": deadline_id}).scalar_one(), 1)

    def test_controlled_concurrent_version_allocation(self) -> None:
        suffix = uuid4().hex[:10]
        cycle_id = admin_id = deadline_id = None
        original = main.add_admin_audit_event
        try:
            setup = SessionLocal()
            admin = User(full_name="Deadline race admin", email=f"deadline-race-{suffix}@example.com", password_hash="test", role=UserRole.ADMIN)
            cycle = AcademicCycle(code=f"DR-{suffix}", display_name="Deadline race cycle")
            setup.add_all([admin, cycle]); setup.flush()
            deadline = AcademicDeadline(academic_cycle_id=cycle.id); setup.add(deadline); setup.flush()
            setup.add(AcademicDeadlineVersion(academic_deadline_id=deadline.id, version_number=1, name="Baseline", due_at_utc=utc_now(), time_zone="UTC", created_by_id=admin.id))
            setup.commit(); cycle_id, admin_id, deadline_id = cycle.id, admin.id, deadline.id; setup.close()
            main.add_admin_audit_event = lambda *_args, **_kwargs: None
            gate = threading.Barrier(2)
            results: list[int] = []
            failures: list[Exception] = []

            def create(label: str) -> None:
                session = SessionLocal()
                try:
                    actor = session.get(User, admin_id)
                    gate.wait(timeout=5)
                    payload = DeadlineWrite(name=f"Concurrent {label}", local_due_at="2026-10-19T12:00", time_zone="Asia/Karachi", utc_offset="+05:00", due_at_utc="2026-10-19T07:00:00Z")
                    result = create_academic_deadline_version(deadline_id, payload, type("Request", (), {"headers": {}})(), actor, session)
                    results.append(result["version_number"])
                except Exception as error:  # pragma: no cover - asserted below
                    failures.append(error)
                finally:
                    session.close()

            threads = [threading.Thread(target=create, args=(label,)) for label in ("A", "B")]
            for thread in threads: thread.start()
            for thread in threads: thread.join(timeout=5)
            self.assertFalse(any(thread.is_alive() for thread in threads), "Concurrent deadline writers did not finish within five seconds.")
            self.assertEqual(failures, [])
            self.assertEqual(sorted(results), [2, 3])
        finally:
            main.add_admin_audit_event = original
            if deadline_id is not None:
                cleanup = SessionLocal()
                cleanup.execute(text("delete from academic_deadline_versions where academic_deadline_id=:id"), {"id": deadline_id})
                cleanup.execute(text("delete from academic_deadlines where id=:id"), {"id": deadline_id})
                if cycle_id is not None: cleanup.execute(text("delete from academic_cycles where id=:id"), {"id": cycle_id})
                if admin_id is not None: cleanup.execute(text("delete from users where id=:id"), {"id": admin_id})
                cleanup.commit(); cleanup.close()
