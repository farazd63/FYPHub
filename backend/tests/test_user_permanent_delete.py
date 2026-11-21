"""Coverage for the explicitly confirmed permanent account deletion action."""

from datetime import timedelta, timezone, datetime
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE_NAME, utc_now
from app.database import engine
from app.main import app
from app.models import AcademicCycle, AdminAuditEvent, AuthSession, InstitutionMembership, Team, User, UserRole
from app.security import generate_session_token, hash_password, hash_session_token


class PermanentUserDeletionTests(TestCase):
    def setUp(self) -> None:
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        self.addCleanup(self.db.close)
        self.addCleanup(self.transaction.rollback)
        self.addCleanup(self.connection.close)

        institution_id = self.connection.execute(
            select(InstitutionMembership.institution_id)
            .where(InstitutionMembership.institution_id.is_not(None))
            .limit(1)
        ).scalar_one()
        suffix = uuid4().hex[:12]
        now = datetime.now(timezone.utc)
        self.admin = User(
            full_name="Deletion Admin",
            email=f"deletion-admin-{suffix}@szabist-isb.pk",
            password_hash=hash_password("Deletion Admin Password!"),
            role=UserRole.ADMIN,
            institution_id=institution_id,
            email_verified_at=now,
            access_approved_at=now,
            is_active=True,
        )
        self.target = User(
            full_name="Deletable Supervisor",
            email=f"deletable-{suffix}@szabist-isb.pk",
            password_hash=hash_password("Deletable Password!"),
            role=UserRole.SUPERVISOR,
            institution_id=institution_id,
            email_verified_at=now,
            access_approved_at=now,
            is_active=True,
        )
        self.db.add_all([self.admin, self.target])
        self.db.flush()
        self.db.add_all([
            InstitutionMembership(
                institution_id=institution_id,
                user_id=self.admin.id,
                membership_role="INSTITUTION_ADMIN",
                status="ACTIVE",
                approved_at=now,
            ),
            InstitutionMembership(
                institution_id=institution_id,
                user_id=self.target.id,
                membership_role="MEMBER",
                status="ACTIVE",
                approved_at=now,
            ),
        ])
        self.admin_token = generate_session_token()
        self.db.add(AuthSession(
            user_id=self.admin.id,
            token_hash=hash_session_token(self.admin_token),
            expires_at=utc_now() + timedelta(hours=1),
        ))
        self.db.commit()
        factory = patch(
            "app.database.SessionLocal",
            side_effect=lambda: Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint"),
        )
        factory.start()
        self.addCleanup(factory.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def call(self, method: str, path: str, **kwargs):
        headers = {"Cookie": f"{SESSION_COOKIE_NAME}={self.admin_token}", "Origin": "http://localhost:5173"}
        return self.client.request(method, path, headers=headers, **kwargs)

    def test_unlinked_account_is_removed_and_deletion_is_audited(self) -> None:
        target_id = self.target.id
        response = self.call("DELETE", f"/api/v1/admin/users/{target_id}/permanent")
        self.assertEqual(response.status_code, 204, response.text)
        self.db.expire_all()
        self.assertIsNone(self.db.get(User, target_id))
        event = self.db.scalar(
            select(AdminAuditEvent).where(
                AdminAuditEvent.action == "account_deleted",
                AdminAuditEvent.target_id == target_id,
            )
        )
        self.assertIsNotNone(event)
        self.assertIsNone(event.affected_user_id)

    def test_group_account_cannot_be_permanently_deleted(self) -> None:
        cycle = self.db.scalar(select(AcademicCycle).order_by(AcademicCycle.id))
        self.db.add(Team(academic_cycle_id=cycle.id, shared_user_id=self.target.id, status="locked", institution_id=self.target.institution_id))
        self.db.commit()
        response = self.call("DELETE", f"/api/v1/admin/users/{self.target.id}/permanent")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "account_has_group")
        self.db.expire_all()
        self.assertIsNotNone(self.db.get(User, self.target.id))

    def test_admin_cannot_permanently_delete_their_own_account(self) -> None:
        response = self.call("DELETE", f"/api/v1/admin/users/{self.admin.id}/permanent")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "cannot_delete_self")


if __name__ == "__main__":
    import unittest

    unittest.main()
