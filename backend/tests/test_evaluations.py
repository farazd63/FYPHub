"""Integration coverage for role-owned marks and published result aggregation."""

import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import utc_now
from app.database import engine, get_db
from app.main import app
from app.models import AuthSession, AcademicCycle, DefensePanelMember, DefenseSchedule, SupervisorAssignment, Team, TeamMember, User, UserRole
from app.security import generate_session_token, hash_session_token
from tests.test_auth_sessions import request


class EvaluationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = engine.connect()
        cls.transaction = cls.connection.begin()
        if cls.connection.execute(text("SELECT current_database()")).scalar_one() != "fyphub_p1":
            raise RuntimeError("Evaluation tests require fyphub_p1.")
        app.dependency_overrides[get_db] = cls.get_test_db

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.pop(get_db, None)
        cls.transaction.rollback()
        cls.connection.close()

    @classmethod
    def get_test_db(cls):
        session = Session(bind=cls.connection, autoflush=False, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()

    def setUp(self) -> None:
        suffix = uuid4().hex[:10].upper()
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        self.admin = User(full_name="Evaluation Admin", email=f"evaluation-admin-{suffix.lower()}@example.com", password_hash="test", role=UserRole.ADMIN)
        self.coordinator = User(full_name="Evaluation Coordinator", email=f"evaluation-coordinator-{suffix.lower()}@example.com", password_hash="test", role=UserRole.COORDINATOR)
        self.supervisor = User(full_name="Evaluation Supervisor", email=f"evaluation-supervisor-{suffix.lower()}@example.com", password_hash="test", role=UserRole.SUPERVISOR)
        self.panel = User(full_name="Evaluation Panel", email=f"evaluation-panel-{suffix.lower()}@example.com", password_hash="test", role=UserRole.PANEL_MEMBER)
        self.student = User(full_name="Evaluation Student", email=f"evaluation-student-{suffix.lower()}@example.com", registration_number=f"EVAL{suffix}", password_hash="test", role=UserRole.STUDENT)
        self.cycle = AcademicCycle(code=f"EVAL-{suffix}", display_name="Evaluation cycle")
        session.add_all([self.admin, self.coordinator, self.supervisor, self.panel, self.student, self.cycle])
        session.flush()
        self.team = Team(academic_cycle_id=self.cycle.id, shared_user_id=self.student.id)
        session.add(self.team)
        session.flush()
        session.add(TeamMember(team_id=self.team.id, academic_cycle_id=self.cycle.id, full_name=self.student.full_name, registration_number=self.student.registration_number, university_email=self.student.email, is_creator=True))
        session.add(SupervisorAssignment(team_id=self.team.id, academic_cycle_id=self.cycle.id, supervisor_id=self.supervisor.id, assigned_by_id=self.admin.id))
        schedule = DefenseSchedule(team_id=self.team.id, academic_cycle_id=self.cycle.id, created_by_id=self.coordinator.id, start_at=datetime.now(timezone.utc) + timedelta(days=2), end_at=datetime.now(timezone.utc) + timedelta(days=2, hours=1))
        session.add(schedule)
        session.flush()
        session.add(DefensePanelMember(schedule_id=schedule.id, user_id=self.panel.id, assigned_by_id=self.coordinator.id))
        self.tokens = {}
        for key, user in (("admin", self.admin), ("coordinator", self.coordinator), ("supervisor", self.supervisor), ("panel", self.panel), ("student", self.student)):
            token = generate_session_token()
            self.tokens[key] = token
            session.add(AuthSession(user_id=user.id, token_hash=hash_session_token(token), expires_at=utc_now() + timedelta(hours=2)))
        session.commit()
        session.close()

    def call(self, method: str, path: str, payload: dict | None = None, token: str = "admin"):
        return request(method, path, payload, headers={"Cookie": f"fyphub_session={self.tokens[token]}", "Origin": "http://127.0.0.1:5173"})

    def test_role_ownership_and_submission_lock(self) -> None:
        code, _, supervisor = self.call("POST", "/api/v1/evaluations", {"group_id": self.team.id, "evaluation_category": "SUPERVISOR_EVALUATION", "obtained_marks": 8, "feedback": "Good supervision", "submit": True}, "supervisor")
        self.assertEqual((code, supervisor["status"], supervisor["maximum_marks"]), (201, "SUBMITTED", 10))
        code, _, denied = self.call("POST", "/api/v1/evaluations", {"group_id": self.team.id, "evaluation_category": "FINAL_PRESENTATION", "obtained_marks": 25}, "supervisor")
        self.assertEqual((code, denied["detail"]["code"]), (403, "category_not_owned"))
        code, _, locked = self.call("PATCH", f"/api/v1/evaluations/{supervisor['id']}", {"group_id": self.team.id, "evaluation_category": "SUPERVISOR_EVALUATION", "obtained_marks": 9}, "supervisor")
        self.assertEqual((code, locked["detail"]["code"]), (409, "evaluation_locked"))

    def test_panel_records_are_independent_and_admin_can_monitor(self) -> None:
        code, _, first = self.call("POST", "/api/v1/evaluations", {"group_id": self.team.id, "evaluation_category": "FINAL_PRESENTATION", "obtained_marks": 24, "feedback": "Panel one", "submit": True}, "panel")
        self.assertEqual((code, first["status"]), (201, "SUBMITTED"))
        other_panel = User(full_name="Second Panel", email=f"second-panel-{uuid4().hex}@example.com", password_hash="test", role=UserRole.PANEL_MEMBER)
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        session.add(other_panel); session.flush()
        token = generate_session_token(); self.tokens["second_panel"] = token
        session.add(AuthSession(user_id=other_panel.id, token_hash=hash_session_token(token), expires_at=utc_now() + timedelta(hours=2)))
        session.add(DefensePanelMember(schedule_id=session.query(DefenseSchedule).filter_by(team_id=self.team.id).one().id, user_id=other_panel.id, assigned_by_id=self.coordinator.id))
        session.commit(); session.close()
        code, _, second = self.call("POST", "/api/v1/evaluations", {"group_id": self.team.id, "evaluation_category": "FINAL_PRESENTATION", "obtained_marks": 27, "submit": True}, "second_panel")
        self.assertEqual((code, second["status"]), (201, "SUBMITTED"))
        code, _, monitored = self.call("GET", "/api/v1/admin/evaluations", token="admin")
        self.assertEqual(code, 200)
        monitored_ids = {row["evaluator_id"] for row in monitored if row["evaluation_category"] == "FINAL_PRESENTATION"}
        self.assertTrue({self.panel.id, other_panel.id}.issubset(monitored_ids))

    def test_approve_publish_and_student_results(self) -> None:
        records = []
        for category, marks, owner in (("PROJECT_DOCUMENTATION", 18, "admin"), ("PROPOSAL", 9, "coordinator"), ("SUPERVISOR_EVALUATION", 8, "supervisor"), ("FINAL_PRESENTATION", 24, "panel"), ("MID_REVIEW", 25, "panel")):
            code, _, body = self.call("POST", "/api/v1/evaluations", {"group_id": self.team.id, "evaluation_category": category, "obtained_marks": marks, "submit": True}, owner)
            self.assertEqual(code, 201)
            records.append(body["id"])
        code, _, hidden = self.call("GET", "/api/v1/student/results", token="student")
        self.assertEqual((code, hidden["published"]), (200, False))
        for record_id in records:
            code, _, body = self.call("POST", f"/api/v1/evaluations/{record_id}/approve", token="admin")
            self.assertEqual((code, body["status"]), (200, "APPROVED"))
            code, _, body = self.call("POST", f"/api/v1/evaluations/{record_id}/publish", token="admin")
            self.assertEqual((code, body["status"]), (200, "PUBLISHED"))
        code, _, result = self.call("GET", "/api/v1/student/results", token="student")
        self.assertEqual((code, result["published"], result["total_marks"], result["grade"]), (200, True, 84.0, "A-"))
        self.assertEqual([item["category"] for item in result["categories"]], ["PROJECT_DOCUMENTATION", "FINAL_PRESENTATION", "PROPOSAL", "MID_REVIEW", "SUPERVISOR_EVALUATION"])

    def test_report_access_and_unauthorized_student(self) -> None:
        code, _, record = self.call("POST", "/api/v1/evaluations", {"group_id": self.team.id, "evaluation_category": "SUPERVISOR_EVALUATION", "obtained_marks": 7}, "supervisor")
        self.assertEqual(code, 201)
        code, _, report = self.call("GET", f"/api/v1/evaluations/{record['id']}/report", token="supervisor")
        self.assertEqual((code, report["record"]["id"]), (200, record["id"]))
        code, _, denied = self.call("GET", f"/api/v1/evaluations/{record['id']}/report", token="student")
        self.assertEqual((code, denied["detail"]["code"]), (403, "evaluation_access_denied"))

    def test_admin_correction_and_panel_aggregation_are_audited(self) -> None:
        code, _, record = self.call("POST", "/api/v1/evaluations", {"group_id": self.team.id, "evaluation_category": "FINAL_PRESENTATION", "obtained_marks": 24, "submit": True}, "panel")
        self.assertEqual(code, 201)
        code, _, corrected = self.call("POST", f"/api/v1/evaluations/{record['id']}/correct", {"new_marks": 26, "reason": "Verified against the signed panel sheet."}, "admin")
        self.assertEqual((code, corrected["obtained_marks"], corrected["status"]), (200, 26, "APPROVED"))
        code, _, history = self.call("GET", f"/api/v1/evaluations/{record['id']}/audit", token="admin")
        self.assertEqual(code, 200)
        self.assertTrue(any(item["action"] == "authorized_correction" for item in history))
        code, _, aggregation = self.call("PUT", "/api/v1/admin/evaluations/aggregation", {"evaluation_category": "FINAL_PRESENTATION", "method": "MEDIAN"}, "admin")
        self.assertEqual((code, aggregation["method"]), (200, "MEDIAN"))


if __name__ == "__main__":
    unittest.main()
