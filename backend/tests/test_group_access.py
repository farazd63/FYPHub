import unittest
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from app.database import engine
from app.main import account_response, login
from app.models import AcademicCycle, Team, User, UserRole
from app.schemas.auth import LoginRequest
from app.security import hash_password


def request_scope() -> Request:
    return Request({
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/auth/login",
        "raw_path": b"/api/v1/auth/login",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 0),
        "server": ("127.0.0.1", 80),
    })


class GroupAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = engine.connect()
        cls.transaction = cls.connection.begin()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.transaction.rollback()
        cls.connection.close()

    def setUp(self) -> None:
        self.session = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        suffix = uuid4().hex
        cycle = AcademicCycle(code=f"GROUP-{suffix[:8]}", display_name=f"Group {suffix[:8]}", registration_open=True)
        user = User(
            full_name="Group leader",
            email=f"group-{suffix}@example.com",
            registration_number=f"LEADER{suffix[:8]}",
            password_hash=hash_password("SafeGroupPassword123!"),
            role=UserRole.STUDENT,
        )
        self.session.add_all([cycle, user])
        self.session.flush()
        self.team = Team(academic_cycle_id=cycle.id, shared_user_id=user.id)
        self.session.add(self.team)
        self.session.commit()
        self.email = user.email
        self.registration = user.registration_number

    def tearDown(self) -> None:
        self.session.close()

    def test_group_login_returns_saved_role_and_group_context(self) -> None:
        result = login(
            LoginRequest(email=self.email, password="SafeGroupPassword123!"),
            request_scope(),
            Response(),
            self.session,
        )
        self.assertEqual(result["role"], UserRole.STUDENT)
        self.assertEqual(result["group_id"], self.team.id)
        self.assertEqual(result["group_email"], self.email)

    def test_registration_number_login_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            login(
                LoginRequest(registration_number=self.registration, password="SafeGroupPassword123!"),
                request_scope(),
                Response(),
                self.session,
            )
        self.assertEqual(raised.exception.status_code, 401)

    def test_dissolved_group_cannot_login(self) -> None:
        self.team.status = "dissolved"
        self.session.commit()
        with self.assertRaises(HTTPException) as raised:
            login(
                LoginRequest(email=self.email, password="SafeGroupPassword123!"),
                request_scope(),
                Response(),
                self.session,
            )
        self.assertEqual(raised.exception.status_code, 401)
