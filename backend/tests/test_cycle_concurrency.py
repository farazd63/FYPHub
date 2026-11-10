"""True multi-connection coverage for cycle configuration and team registration.

These tests intentionally do not use the suite's rollback-bound API fixture: a
second connection cannot observe rows held inside that fixture's outer
transaction.  Each test creates uniquely named, committed rows and removes
only those rows in ``finally`` blocks.
"""

from __future__ import annotations

import threading
import unittest
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, event, func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.main import (
    locked_cycle_and_policy,
    register_team,
    set_group_policy,
)
from app.models import (
    AcademicCycle,
    AcademicGroupPolicy,
    AdminAuditEvent,
    AuthSession,
    Team,
    TeamMember,
    User,
    UserRole,
)
from app.schemas.academic import PolicyUpdate
from app.schemas.team_registration import TeamRegistrationRequest


_TIMEOUT_SECONDS = 5


class _RequestWithoutOrigin:
    """The direct endpoint call has the same permitted no-Origin boundary as tests."""

    headers: dict[str, str] = {}


class CycleConcurrencyTests(unittest.TestCase):
    """Exercise the production cycle-then-policy lock order with real sessions."""

    def setUp(self) -> None:
        with engine.connect() as connection:
            if connection.execute(select(func.current_database())).scalar_one() != "fyphub_p1":
                raise RuntimeError("Concurrency tests require fyphub_p1.")
        self.suffix = uuid4().hex[:12]
        self.cycle_id: int | None = None
        self.policy_id: int | None = None
        self.admin_id: int | None = None
        self.created_user_ids: list[int] = []

    def tearDown(self) -> None:
        # Neither successful registration nor rejected policy updates writes an
        # audit event.  Keep this assertion before cleanup so a future change
        # cannot silently leave an audit record that the append-only trigger
        # would correctly prevent this test from deleting.
        if self.cycle_id is not None:
            with SessionLocal() as session:
                self.assertEqual(
                    session.scalar(
                        select(func.count(AdminAuditEvent.id)).where(
                            AdminAuditEvent.target_id.in_(
                                [value for value in (self.cycle_id, self.policy_id) if value is not None]
                            )
                        )
                    ),
                    0,
                )
        self._cleanup()

    def _cleanup(self) -> None:
        if self.cycle_id is None:
            return
        with SessionLocal() as session:
            user_ids = session.scalars(
                select(Team.shared_user_id).where(Team.academic_cycle_id == self.cycle_id)
            ).all()
            session.execute(delete(TeamMember).where(TeamMember.academic_cycle_id == self.cycle_id))
            session.execute(delete(Team).where(Team.academic_cycle_id == self.cycle_id))
            if user_ids:
                session.execute(delete(AuthSession).where(AuthSession.user_id.in_(user_ids)))
                session.execute(delete(User).where(User.id.in_(user_ids)))
            if self.admin_id is not None:
                session.execute(delete(AuthSession).where(AuthSession.user_id == self.admin_id))
                session.execute(delete(User).where(User.id == self.admin_id))
            session.execute(delete(AcademicGroupPolicy).where(AcademicGroupPolicy.academic_cycle_id == self.cycle_id))
            session.execute(delete(AcademicCycle).where(AcademicCycle.id == self.cycle_id))
            session.commit()

    def _create_cycle(self, maximum: int) -> None:
        with SessionLocal() as session:
            cycle = AcademicCycle(
                code=f"RACE-{self.suffix}",
                display_name=f"Race fixture {self.suffix}",
                registration_open=True,
            )
            session.add(cycle)
            session.flush()
            policy = AcademicGroupPolicy(academic_cycle_id=cycle.id, max_group_size=maximum)
            admin = User(
                full_name="Concurrency administrator",
                email=f"race-admin-{self.suffix}@example.com",
                registration_number=None,
                password_hash="test-only-hash",
                role=UserRole.ADMIN,
            )
            session.add_all([policy, admin])
            session.commit()
            self.cycle_id, self.policy_id, self.admin_id = cycle.id, policy.id, admin.id

    def _registration(self, sequence: str) -> TeamRegistrationRequest:
        assert self.cycle_id is not None
        payload = TeamRegistrationRequest.model_validate(
            {
                "academic_cycle_id": self.cycle_id,
                "shared_login_email": f"race-{sequence}-{self.suffix}@example.com",
                "password": "SafeTestPassword123!",
                "creator": {
                    "full_name": f"Creator {sequence}",
                    "registration_number": f"RACE{sequence}{self.suffix}".upper(),
                    "university_email": f"creator-{sequence}-{self.suffix}@example.com",
                },
                "members": [
                    {
                        "full_name": f"Member {sequence}",
                        "registration_number": f"MEM{sequence}{self.suffix}".upper(),
                        "university_email": f"member-{sequence}-{self.suffix}@example.com",
                    }
                ],
            }
        )

        return payload

    def _register_in_thread(
        self,
        payload: TeamRegistrationRequest,
        result: dict[str, object],
    ) -> None:
        session = SessionLocal()
        try:
            result["value"] = register_team(payload, session)
        except Exception as error:  # captured for the owning test thread
            result["error"] = error
        finally:
            session.close()

    def _block_registration_after_locks(self, email: str) -> tuple[threading.Event, threading.Event, object]:
        entered = threading.Event()
        release = threading.Event()

        def pause_before_member_insert(_mapper: object, _connection: object, member: TeamMember) -> None:
            if member.university_email != email or entered.is_set():
                return
            entered.set()
            if not release.wait(_TIMEOUT_SECONDS):
                raise RuntimeError("Timed out waiting to release concurrent team registration.")

        event.listen(TeamMember, "before_insert", pause_before_member_insert)
        return entered, release, pause_before_member_insert

    def test_registration_finishes_before_a_waiting_registration_closure(self) -> None:
        """Closure waits for the in-flight registration's cycle lock, then closes it."""
        self._create_cycle(maximum=2)
        payload = self._registration("close")
        entered, release, listener = self._block_registration_after_locks(payload.creator.university_email)
        registration_result: dict[str, object] = {}
        closure_result: dict[str, object] = {}
        closure_attempted = threading.Event()

        def close_registration() -> None:
            session = SessionLocal()
            try:
                closure_attempted.set()
                cycle, _policy = locked_cycle_and_policy(session, self.cycle_id)  # type: ignore[arg-type]
                cycle.registration_open = False
                session.commit()
                closure_result["committed"] = True
            except Exception as error:
                session.rollback()
                closure_result["error"] = error
            finally:
                session.close()

        registration_thread = threading.Thread(
            target=self._register_in_thread, args=(payload, registration_result), daemon=True
        )
        closure_thread = threading.Thread(target=close_registration, daemon=True)
        try:
            registration_thread.start()
            self.assertTrue(entered.wait(_TIMEOUT_SECONDS), "registration did not reach the held transaction point")
            closure_thread.start()
            self.assertTrue(closure_attempted.wait(_TIMEOUT_SECONDS), "closure thread did not attempt its transaction")
            release.set()
            registration_thread.join(_TIMEOUT_SECONDS)
            closure_thread.join(_TIMEOUT_SECONDS)
            self.assertFalse(registration_thread.is_alive(), "registration thread exceeded timeout")
            self.assertFalse(closure_thread.is_alive(), "closure thread exceeded timeout")
        finally:
            release.set()
            event.remove(TeamMember, "before_insert", listener)

        self.assertNotIn("error", registration_result)
        self.assertNotIn("error", closure_result)
        self.assertTrue(closure_result.get("committed"))
        with SessionLocal() as session:
            self.assertFalse(session.get(AcademicCycle, self.cycle_id).registration_open)  # type: ignore[union-attr]
            self.assertEqual(session.scalar(select(func.count(Team.id)).where(Team.academic_cycle_id == self.cycle_id)), 1)
            self.assertEqual(session.scalar(select(func.count(TeamMember.id)).where(TeamMember.academic_cycle_id == self.cycle_id)), 2)

    def test_policy_reduction_rejects_after_waiting_registration_commits(self) -> None:
        """A reduction sees committed teams after the registration releases its lock."""
        self._create_cycle(maximum=3)
        initial = self._registration("existing")
        with SessionLocal() as session:
            register_team(initial, session)

        payload = self._registration("reduce")
        entered, release, listener = self._block_registration_after_locks(payload.creator.university_email)
        registration_result: dict[str, object] = {}
        reduction_result: dict[str, object] = {}
        reduction_attempted = threading.Event()

        def reduce_policy() -> None:
            session = SessionLocal()
            try:
                actor = session.get(User, self.admin_id)
                reduction_attempted.set()
                set_group_policy(
                    self.cycle_id,  # type: ignore[arg-type]
                    PolicyUpdate(max_group_size=1),
                    _RequestWithoutOrigin(),
                    actor,  # type: ignore[arg-type]
                    session,
                )
                reduction_result["unexpected_success"] = True
            except HTTPException as error:
                session.rollback()
                reduction_result["status"] = error.status_code
                reduction_result["detail"] = error.detail
            except Exception as error:
                session.rollback()
                reduction_result["error"] = error
            finally:
                session.close()

        registration_thread = threading.Thread(
            target=self._register_in_thread, args=(payload, registration_result), daemon=True
        )
        reduction_thread = threading.Thread(target=reduce_policy, daemon=True)
        try:
            registration_thread.start()
            self.assertTrue(entered.wait(_TIMEOUT_SECONDS), "registration did not reach the held transaction point")
            reduction_thread.start()
            self.assertTrue(reduction_attempted.wait(_TIMEOUT_SECONDS), "reduction thread did not attempt its transaction")
            release.set()
            registration_thread.join(_TIMEOUT_SECONDS)
            reduction_thread.join(_TIMEOUT_SECONDS)
            self.assertFalse(registration_thread.is_alive(), "registration thread exceeded timeout")
            self.assertFalse(reduction_thread.is_alive(), "reduction thread exceeded timeout")
        finally:
            release.set()
            event.remove(TeamMember, "before_insert", listener)

        self.assertNotIn("error", registration_result)
        self.assertNotIn("error", reduction_result)
        self.assertEqual(reduction_result.get("status"), 409)
        self.assertEqual(reduction_result.get("detail", {}).get("code"), "existing_team_exceeds_limit")
        with SessionLocal() as session:
            self.assertEqual(session.get(AcademicGroupPolicy, self.policy_id).max_group_size, 3)  # type: ignore[union-attr]
            self.assertEqual(session.scalar(select(func.count(Team.id)).where(Team.academic_cycle_id == self.cycle_id)), 2)
            self.assertEqual(session.scalar(select(func.count(TeamMember.id)).where(TeamMember.academic_cycle_id == self.cycle_id)), 4)

