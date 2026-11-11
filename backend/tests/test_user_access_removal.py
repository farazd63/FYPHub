"""Access removal preserves linked records; all fixture writes are rolled back."""
from datetime import timedelta
from uuid import uuid4
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import utc_now
from app.database import engine
from app.main import app
from app.models import AcademicCycle, AdminAuditEvent, AuthSession, PasswordResetToken, ProjectMilestone, Team, User, UserRole
from app.security import generate_session_token, hash_password, hash_session_token


class UserAccessRemovalTests(TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.addCleanup(self.connection.close)
        self.addCleanup(self.transaction.rollback)
        self.db = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        self.addCleanup(self.db.close)
        suffix = uuid4().hex
        self.password = "StrongTestPassword!39"
        self.users, self.tokens = {}, {}
        for label, role in (("admin", UserRole.ADMIN), ("supervisor", UserRole.SUPERVISOR), ("student", UserRole.STUDENT)):
            user = User(full_name=f"Access test {label}", email=f"{label}-{suffix}@example.com", registration_number=f"ACCESS-{suffix}" if role == UserRole.STUDENT else None, role=role, password_hash=hash_password(self.password), is_active=True)
            self.db.add(user); self.db.flush()
            self.users[label] = user
            token = generate_session_token(); self.tokens[label] = token
            self.db.add(AuthSession(user_id=user.id, token_hash=hash_session_token(token), expires_at=utc_now()+timedelta(hours=1)))
            self.db.add(AdminAuditEvent(actor_id=self.users["admin"].id, affected_user_id=user.id, target_type="USER", target_id=user.id, action="historical_test_event", changed_values={"original": True}))
        cycle = self.db.scalar(select(AcademicCycle).order_by(AcademicCycle.id))
        self.team = Team(academic_cycle_id=cycle.id, shared_user_id=self.users["student"].id, status="locked")
        self.db.add(self.team); self.db.flush()
        self.milestone = ProjectMilestone(team_id=self.team.id, created_by_id=self.users["supervisor"].id, title="Historical project work", completion_percent=79)
        self.reset = PasswordResetToken(user_id=self.users["student"].id, token_hash=hash_session_token(generate_session_token()), expires_at=utc_now()+timedelta(hours=1))
        self.db.add_all([self.milestone, self.reset]); self.db.commit()
        factory = patch("app.database.SessionLocal", side_effect=lambda: Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint"))
        factory.start(); self.addCleanup(factory.stop)
        self.client = TestClient(app); self.addCleanup(self.client.close)

    def call(self, method, path, label="admin", **kwargs):
        return self.client.request(method, path, headers={"Cookie": f"fyphub_session={self.tokens[label]}", "Origin": "http://localhost:5173"}, **kwargs)

    def test_removal_preserves_user_audit_group_and_project_history(self):
        for label in ("supervisor", "student"):
            user = self.users[label]
            self.assertEqual(self.call("GET", "/api/v1/auth/me", label).status_code, 200)
            response = self.call("DELETE", f"/api/v1/admin/users/{user.id}")
            self.assertEqual(response.status_code, 204, response.text)
            self.db.expire_all()
            self.assertFalse(self.db.get(User, user.id).is_active)
            self.assertIsNotNone(self.db.scalar(select(AdminAuditEvent).where(AdminAuditEvent.affected_user_id==user.id, AdminAuditEvent.action=="historical_test_event")))
            self.assertEqual(self.call("GET", "/api/v1/auth/me", label).status_code, 401)
            login = self.client.post("/api/v1/auth/login", json={"email": user.email, "password": self.password})
            self.assertEqual(login.status_code, 401, login.text)
        self.assertEqual(self.db.get(Team, self.team.id).status, "locked")
        self.assertEqual(self.db.get(ProjectMilestone, self.milestone.id).completion_percent, 79)
        self.assertIsNotNone(self.db.get(PasswordResetToken, self.reset.id).used_at)

    def test_removal_is_idempotent_and_reactivation_does_not_restore_old_session(self):
        user = self.users["student"]
        for _ in range(2):
            self.assertEqual(self.call("DELETE", f"/api/v1/admin/users/{user.id}").status_code, 204)
        response = self.call("PATCH", f"/api/v1/admin/users/{user.id}/status", json={"is_active": True})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.call("GET", "/api/v1/auth/me", "student").status_code, 401)

    def test_only_authorized_admin_can_remove_access_and_self_removal_is_blocked(self):
        path = f"/api/v1/admin/users/{self.users['student'].id}"
        self.assertEqual(self.client.delete(path).status_code, 401)
        self.assertEqual(self.call("DELETE", path, "supervisor").status_code, 403)
        self.assertEqual(self.call("DELETE", f"/api/v1/admin/users/{self.users['admin'].id}").status_code, 409)
        self.db.expire_all()
        self.assertTrue(self.db.get(User, self.users["student"].id).is_active)
