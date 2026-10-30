"""Focused coverage for persisted progress, scheduling, and evaluation workflows."""

import unittest
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import utc_now
from app.database import engine, get_db
from app.main import app
from app.models import AcademicCycle, AuthSession, SupervisorAssignment, Team, TeamMember, User, UserRole
from app.security import generate_session_token, hash_session_token
from tests.test_supervisor_capacity import request


class ProjectWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = engine.connect(); cls.transaction = cls.connection.begin()
        if cls.connection.execute(text("SELECT current_database()")).scalar_one() != "fyphub_p1": raise RuntimeError("Project workflow tests require fyphub_p1.")
        app.dependency_overrides[get_db] = cls.get_test_db

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.pop(get_db, None); cls.transaction.rollback(); cls.connection.close()

    @classmethod
    def get_test_db(cls):
        session = Session(bind=cls.connection, autoflush=False, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try: yield session
        finally: session.close()

    def setUp(self) -> None:
        suffix = uuid4().hex[:10]
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        self.coordinator = User(full_name="Workflow Coordinator", email=f"workflow-coordinator-{suffix}@example.com", password_hash="test", role=UserRole.COORDINATOR)
        self.supervisor = User(full_name="Workflow Supervisor", email=f"workflow-supervisor-{suffix}@example.com", password_hash="test", role=UserRole.SUPERVISOR)
        self.evaluator_one = User(full_name="Workflow Evaluator One", email=f"workflow-evaluator-one-{suffix}@example.com", password_hash="test", role=UserRole.PANEL_MEMBER)
        self.evaluator_two = User(full_name="Workflow Evaluator Two", email=f"workflow-evaluator-two-{suffix}@example.com", password_hash="test", role=UserRole.PANEL_MEMBER)
        self.student = User(full_name="Workflow Student", email=f"workflow-student-{suffix}@example.com", registration_number=f"WF{suffix}".upper(), password_hash="test", role=UserRole.STUDENT)
        self.cycle = AcademicCycle(code=f"WF-{suffix}", display_name="Workflow cycle")
        session.add_all([self.coordinator, self.supervisor, self.evaluator_one, self.evaluator_two, self.student, self.cycle]); session.flush()
        self.team = Team(academic_cycle_id=self.cycle.id, shared_user_id=self.student.id)
        session.add(self.team); session.flush()
        session.add(TeamMember(team_id=self.team.id, academic_cycle_id=self.cycle.id, full_name=self.student.full_name, registration_number=self.student.registration_number, university_email=self.student.email, is_creator=True))
        session.add(SupervisorAssignment(team_id=self.team.id, academic_cycle_id=self.cycle.id, supervisor_id=self.supervisor.id, assigned_by_id=self.coordinator.id))
        self.tokens = {}
        for label, user in (("coordinator", self.coordinator), ("supervisor", self.supervisor), ("evaluator_one", self.evaluator_one), ("evaluator_two", self.evaluator_two), ("student", self.student)):
            token = generate_session_token(); self.tokens[label] = token; session.add(AuthSession(user_id=user.id, token_hash=hash_session_token(token), expires_at=utc_now() + timedelta(hours=2)))
        session.commit(); session.close()

    def test_progress_milestones_tasks_meetings_and_health(self) -> None:
        status, milestone = request("POST", f"/api/v1/project-progress/{self.team.id}/milestones", {"title": "Research plan", "completion_percent": 20, "due_at": "2026-10-20T00:00:00Z"}, token=self.tokens["student"])
        self.assertEqual((status, milestone["title"]), (201, "Research plan"))
        status, task = request("POST", f"/api/v1/project-progress/{self.team.id}/tasks", {"title": "Collect sources", "completion_percent": 0, "due_at": "2026-10-20T00:00:00Z"}, token=self.tokens["student"])
        self.assertEqual((status, task["overdue"]), (201, True))
        status, meeting = request("POST", f"/api/v1/project-progress/{self.team.id}/meetings", {"held_at": "2026-01-01T12:00:00Z", "minutes": "Discussed research scope.", "action_items": []}, token=self.tokens["student"])
        self.assertEqual((status, meeting["supervisor_id"]), (201, self.supervisor.id))
        status, body = request("GET", f"/api/v1/project-progress/{self.team.id}", token=self.tokens["student"])
        self.assertEqual(status, 200); self.assertEqual(body["health"], "Attention Required"); self.assertEqual(len(body["meetings"]), 1)

    def test_progress_cross_team_denial(self) -> None:
        status, body = request("GET", f"/api/v1/project-progress/{self.team.id}", token=self.tokens["evaluator_one"])
        self.assertEqual((status, body["detail"]), (403, "You are not authorized to access this team."))

    def test_schedule_assignment_conflict_and_reschedule(self) -> None:
        payload = {"team_id": self.team.id, "academic_cycle_id": self.cycle.id, "start_at": "2027-01-01T10:00:00Z", "end_at": "2027-01-01T11:00:00Z", "room": "Room 1", "panel_member_ids": [self.evaluator_one.id, self.evaluator_two.id]}
        status, schedule = request("POST", "/api/v1/panel-schedules", payload, token=self.tokens["coordinator"])
        self.assertEqual((status, len(schedule["panel_members"])), (201, 2))
        conflict = {**payload, "start_at": "2027-01-01T10:30:00Z", "end_at": "2027-01-01T11:30:00Z"}
        status, body = request("POST", "/api/v1/panel-schedules", conflict, token=self.tokens["coordinator"])
        self.assertEqual((status, body["detail"]["code"]), (409, "student_conflict"))
        status, changed = request("PATCH", f"/api/v1/panel-schedules/{schedule['id']}", {"start_at": "2027-01-01T12:00:00Z", "end_at": "2027-01-01T13:00:00Z", "room": "Room 2"}, token=self.tokens["coordinator"])
        self.assertEqual((status, changed["status"]), (200, "RESCHEDULED"))

    def test_panel_evaluation_submission_disagreement_and_resolution(self) -> None:
        payload = {"team_id": self.team.id, "academic_cycle_id": self.cycle.id, "start_at": "2027-02-01T10:00:00Z", "end_at": "2027-02-01T11:00:00Z", "room": "Room 3", "panel_member_ids": [self.evaluator_one.id, self.evaluator_two.id]}
        _, schedule = request("POST", "/api/v1/panel-schedules", payload, token=self.tokens["coordinator"])
        evaluation = {"schedule_id": schedule["id"], "scores": [{"criterion_key": "Originality", "score": 90, "max_score": 100, "feedback": "Strong."}], "overall_score": 90, "overall_feedback": "Ready.", "decision": "PASS", "submit": True}
        status, first = request("POST", "/api/v1/panel-evaluations", evaluation, token=self.tokens["evaluator_one"])
        self.assertEqual((status, first["status"]), (201, "SUBMITTED"))
        evaluation["overall_score"] = 50; evaluation["scores"][0]["score"] = 50; evaluation["decision"] = "REVISIONS_REQUIRED"
        status, second = request("POST", "/api/v1/panel-evaluations", evaluation, token=self.tokens["evaluator_two"])
        self.assertEqual((status, second["status"]), (201, "SUBMITTED"))
        status, rows = request("GET", f"/api/v1/panel-evaluations/schedule/{schedule['id']}", token=self.tokens["coordinator"])
        self.assertEqual((status, all(row["disagreement_detected"] for row in rows)), (200, True))
        status, resolved = request("POST", f"/api/v1/panel-evaluations/{first['id']}/resolution", {"status": "RESOLVED", "note": "Coordinator reviewed the evidence."}, token=self.tokens["coordinator"])
        self.assertEqual((status, resolved["status"]), (200, "RESOLVED"))


if __name__ == "__main__": unittest.main()
