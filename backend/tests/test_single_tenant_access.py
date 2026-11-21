"""SZABIST-only domain, activation, and tenant-selection security tests."""

from datetime import datetime, timezone
from uuid import uuid4
import unittest

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import engine
from app.models import InstitutionDomain, InstitutionMembership, User, UserRole
from app.security import hash_password
from app.tenant import (
    PRIMARY_INSTITUTION_DOMAIN,
    approve_membership,
    ensure_access_ready,
    issue_email_verification_token,
    resolve_registration_institution,
    set_tenant_context,
)


class SingleTenantAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = engine.connect()
        cls.transaction = cls.connection.begin()
        cls.primary_id = cls.connection.execute(
            text("SELECT institution_id FROM institution_domains WHERE domain = 'szabist-isb.pk'")
        ).scalar_one()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.transaction.rollback()
        cls.connection.close()

    def session(self) -> Session:
        return Session(
            bind=self.connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

    def test_exact_szabist_domain_is_accepted_and_other_domains_are_rejected(self) -> None:
        session = self.session()
        institution, invitation = resolve_registration_institution(
            session,
            [f"student@{PRIMARY_INSTITUTION_DOMAIN.upper()}"],
        )
        self.assertEqual(institution.id, self.primary_id)
        self.assertIsNone(invitation)
        for email in ("student@uoh.edu.pk", "student@gmail.com", "student@szbaist-isb.pk"):
            with self.subTest(email=email), self.assertRaises(HTTPException):
                resolve_registration_institution(session, [email])
        session.close()

    def test_primary_domain_cannot_be_registered_twice(self) -> None:
        session = self.session()
        session.add(InstitutionDomain(institution_id=self.primary_id, domain=PRIMARY_INSTITUTION_DOMAIN))
        with self.assertRaises(IntegrityError):
            session.flush()
        session.rollback()
        session.close()

    def test_non_szabist_account_is_denied_even_when_active_and_approved(self) -> None:
        session = self.session()
        suffix = uuid4().hex[:10]
        user = User(
            full_name="Outside Domain User",
            email=f"outside-{suffix}@uoh.edu.pk",
            password_hash=hash_password("Outside Password!"),
            role=UserRole.ADMIN,
            institution_id=self.primary_id,
            email_verified_at=datetime.now(timezone.utc),
            access_approved_at=datetime.now(timezone.utc),
            is_active=True,
        )
        session.add(user)
        session.flush()
        session.add(
            InstitutionMembership(
                institution_id=self.primary_id,
                user_id=user.id,
                membership_role="INSTITUTION_ADMIN",
                status="ACTIVE",
            )
        )
        session.flush()
        with self.assertRaises(HTTPException):
            ensure_access_ready(session, user)
        session.close()

    def test_verification_and_approval_are_both_required_for_szabist_accounts(self) -> None:
        session = self.session()
        suffix = uuid4().hex[:10]
        approver = User(
            full_name="SZABIST Approver",
            email=f"approver-{suffix}@{PRIMARY_INSTITUTION_DOMAIN}",
            password_hash=hash_password("Approver Password!"),
            role=UserRole.ADMIN,
            institution_id=self.primary_id,
            email_verified_at=datetime.now(timezone.utc),
            access_approved_at=datetime.now(timezone.utc),
            is_active=True,
        )
        user = User(
            full_name="Pending SZABIST User",
            email=f"pending-{suffix}@{PRIMARY_INSTITUTION_DOMAIN}",
            registration_number=f"PENDING{suffix.upper()}",
            password_hash=hash_password("Pending Password!"),
            role=UserRole.STUDENT,
            institution_id=self.primary_id,
            is_active=False,
        )
        session.add_all([approver, user])
        session.flush()
        membership = InstitutionMembership(
            institution_id=self.primary_id,
            user_id=user.id,
            status="PENDING",
        )
        session.add(membership)
        issue_email_verification_token(session, user, self.primary_id)
        session.flush()
        with self.assertRaises(HTTPException):
            ensure_access_ready(session, user)
        user.email_verified_at = datetime.now(timezone.utc)
        approve_membership(session, membership, approver.id)
        session.flush()
        ensure_access_ready(session, user)
        self.assertTrue(user.is_active)
        session.close()

    def test_platform_admin_cannot_select_a_historical_tenant(self) -> None:
        session = self.session()
        platform = User(
            full_name="Platform Admin",
            email="platform-admin@example.com",
            password_hash=hash_password("Platform Password!"),
            role=UserRole.PLATFORM_ADMIN,
            is_active=True,
        )
        request = Request(
            {
                "type": "http",
                "headers": [(b"x-institution-id", b"999999")],
                "method": "GET",
                "path": "/",
                "query_string": b"",
                "server": ("testserver", 80),
                "scheme": "http",
            }
        )
        with self.assertRaises(HTTPException):
            set_tenant_context(session, platform, request)
        session.close()


if __name__ == "__main__":
    unittest.main()
