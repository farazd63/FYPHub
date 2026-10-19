"""Rollback-isolated coverage for internal evaluation-rubric drafts."""

import threading
import unittest
from collections.abc import Iterator
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app import main
from app.auth import SESSION_COOKIE_NAME, utc_now
from app.database import SessionLocal, engine, get_db
from app.main import app, create_evaluation_rubric_version
from app.models import AuthSession, EvaluationRubric, EvaluationRubricCriterion, EvaluationRubricVersion, User, UserRole
from app.schemas.evaluation_rubrics import RubricVersionWrite
from app.security import generate_session_token, hash_session_token
from tests.test_auth_sessions import request


class EvaluationRubricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = engine.connect()
        cls.transaction = cls.connection.begin()
        if cls.connection.execute(text("select current_database()" )).scalar_one() != "fyphub_p1":
            raise RuntimeError("Evaluation-rubric tests require fyphub_p1.")
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
        admin = User(full_name="Rubric Admin", email=f"rubric-{uuid4().hex}@example.com", password_hash="test", role=UserRole.ADMIN)
        student = User(full_name="Rubric Student", email=f"rubric-student-{uuid4().hex}@example.com", registration_number=f"R{uuid4().hex[:10]}", password_hash="test", role=UserRole.STUDENT)
        session.add_all([admin, student])
        session.flush()
        self.admin_id = admin.id
        self.admin_token = generate_session_token()
        self.student_token = generate_session_token()
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

    @staticmethod
    def payload(name: str = "Internal review draft") -> dict[str, object]:
        return {
            "name": name,
            "description": "Configuration draft only",
            "criteria": [
                {"name": "Second criterion", "description": None, "order": 2},
                {"name": "First criterion", "description": "First in display order", "order": 1},
            ],
        }

    def test_authorization_origin_and_missing_record(self) -> None:
        self.assertEqual(request("GET", "/api/v1/admin/evaluation-rubrics")[0], 401)
        self.assertEqual(request("GET", "/api/v1/admin/evaluation-rubrics", headers=self.headers(self.student_token))[0], 403)
        self.assertEqual(request("POST", "/api/v1/admin/evaluation-rubrics", self.payload(), headers=self.headers(self.admin_token, "http://evil.example"))[0], 403)
        status_code, _, body = request("GET", "/api/v1/admin/evaluation-rubrics/999999", headers=self.headers(self.admin_token))
        self.assertEqual(status_code, 404)
        self.assertEqual(body["detail"]["code"], "rubric_not_found")

    def test_validation_rejects_blank_duplicate_order_and_extra_fields(self) -> None:
        invalid = [
            {**self.payload(), "name": "   "},
            {**self.payload(), "criteria": [{"name": "One", "order": 1}, {"name": "Two", "order": 1}]},
            {**self.payload(), "criteria": [{"name": "   ", "order": 1}]},
            {**self.payload(), "criteria": []},
            {**self.payload(), "unexpected": True},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertEqual(request("POST", "/api/v1/admin/evaluation-rubrics", payload, headers=self.headers(self.admin_token))[0], 422)

    def test_ordered_history_preserves_prior_version(self) -> None:
        status_code, _, initial = request("POST", "/api/v1/admin/evaluation-rubrics", self.payload(), headers=self.headers(self.admin_token))
        self.assertEqual(status_code, 201)
        rubric_id = initial["id"]
        second = {
            "name": "Revised internal draft",
            "criteria": [
                {"name": "New last", "order": 3},
                {"name": "New first", "order": 1},
                {"name": "New middle", "order": 2},
            ],
        }
        self.assertEqual(request("POST", f"/api/v1/admin/evaluation-rubrics/{rubric_id}/versions", second, headers=self.headers(self.admin_token))[0], 201)
        status_code, _, history = request("GET", f"/api/v1/admin/evaluation-rubrics/{rubric_id}", headers=self.headers(self.admin_token))
        self.assertEqual(status_code, 200)
        self.assertEqual([version["version_number"] for version in history["versions"]], [1, 2])
        self.assertEqual([item["name"] for item in history["versions"][0]["criteria"]], ["First criterion", "Second criterion"])
        self.assertEqual([item["name"] for item in history["versions"][1]["criteria"]], ["New first", "New middle", "New last"])
        self.assertEqual(history["versions"][0]["name"], "Internal review draft")

    def test_audit_failure_rolls_back_complete_version(self) -> None:
        status_code, _, initial = request("POST", "/api/v1/admin/evaluation-rubrics", self.payload(), headers=self.headers(self.admin_token))
        self.assertEqual(status_code, 201)
        rubric_id = initial["id"]
        original = main.add_admin_audit_event
        main.add_admin_audit_event = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("audit failure"))
        try:
            status_code, _, body = request("POST", f"/api/v1/admin/evaluation-rubrics/{rubric_id}/versions", self.payload("Must roll back"), headers=self.headers(self.admin_token))
        finally:
            main.add_admin_audit_event = original
        self.assertEqual(status_code, 500)
        self.assertEqual(body["detail"]["code"], "rubric_save_failed")
        self.assertEqual(self.connection.execute(text("select count(*) from evaluation_rubric_versions where rubric_id=:id"), {"id": rubric_id}).scalar_one(), 1)
        self.assertEqual(self.connection.execute(text("select count(*) from evaluation_rubric_criteria where rubric_version_id=:id"), {"id": initial["versions"][0]["id"]}).scalar_one(), 2)

    def test_concurrent_version_numbers_are_distinct(self) -> None:
        suffix = uuid4().hex[:12]
        admin_id = rubric_id = None
        original = main.add_admin_audit_event
        try:
            setup = SessionLocal()
            admin = User(full_name="Rubric race admin", email=f"rubric-race-{suffix}@example.com", password_hash="test", role=UserRole.ADMIN)
            rubric = EvaluationRubric()
            setup.add_all([admin, rubric])
            setup.flush()
            setup.add(EvaluationRubricVersion(rubric_id=rubric.id, version_number=1, name="Baseline", description=None, created_by_id=admin.id))
            setup.commit()
            admin_id, rubric_id = admin.id, rubric.id
            setup.close()
            main.add_admin_audit_event = lambda *_args, **_kwargs: None
            gate = threading.Barrier(2)
            results: list[int] = []
            failures: list[Exception] = []

            def create(label: str) -> None:
                session = SessionLocal()
                try:
                    actor = session.get(User, admin_id)
                    gate.wait()
                    payload = RubricVersionWrite(name=f"Concurrent {label}", criteria=[{"name": "Criterion", "order": 1}])
                    version = create_evaluation_rubric_version(rubric_id, payload, type("Request", (), {"headers": {}})(), actor, session)
                    results.append(version["version_number"])
                except Exception as error:  # pragma: no cover - asserted below
                    failures.append(error)
                finally:
                    session.close()

            threads = [threading.Thread(target=create, args=(label,)) for label in ("A", "B")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(failures, [])
            self.assertEqual(sorted(results), [2, 3])
            verify = SessionLocal()
            self.assertEqual([item.version_number for item in verify.query(EvaluationRubricVersion).filter_by(rubric_id=rubric_id).order_by(EvaluationRubricVersion.version_number)], [1, 2, 3])
            verify.close()
        finally:
            main.add_admin_audit_event = original
            if rubric_id is not None:
                cleanup = SessionLocal()
                cleanup.execute(text("delete from evaluation_rubric_criteria where rubric_version_id in (select id from evaluation_rubric_versions where rubric_id=:id)"), {"id": rubric_id})
                cleanup.execute(text("delete from evaluation_rubric_versions where rubric_id=:id"), {"id": rubric_id})
                cleanup.execute(text("delete from evaluation_rubrics where id=:id"), {"id": rubric_id})
                if admin_id is not None:
                    cleanup.execute(text("delete from users where id=:id"), {"id": admin_id})
                cleanup.commit()
                cleanup.close()
