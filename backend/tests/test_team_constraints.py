"""Database integration tests for the applied team/member constraints.

All writes run inside one outer transaction against ``fyphub_p1`` and are
rolled back after the class completes. Expected database failures use nested
savepoints so later assertions can continue in the same test transaction.
"""

from __future__ import annotations

import unittest
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import engine


class TeamConstraintTests(unittest.TestCase):
    """Exercise constraints supplied by Alembic revision ``ce964120f177``."""

    connection: Any
    transaction: Any

    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = engine.connect()
        cls.transaction = cls.connection.begin()
        database_name = cls.connection.execute(
            text("SELECT current_database()")
        ).scalar_one()
        if database_name != "fyphub_p1":
            cls.transaction.rollback()
            cls.connection.close()
            raise RuntimeError("Team constraint tests require fyphub_p1.")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.transaction.rollback()
        cls.connection.close()

    def setUp(self) -> None:
        self.prefix = f"tc_{uuid4().hex[:12]}"

    def value(self, suffix: str) -> str:
        return f"{self.prefix}_{suffix}"

    def create_cycle(self, suffix: str) -> int:
        return self.connection.execute(
            text(
                """
                INSERT INTO academic_cycles (code, display_name, registration_open)
                VALUES (:code, :display_name, false)
                RETURNING id
                """
            ),
            {
                "code": self.value(suffix).upper(),
                "display_name": f"Constraint test {suffix}",
            },
        ).scalar_one()

    def create_user(self, suffix: str) -> int:
        return self.connection.execute(
            text(
                """
                INSERT INTO users (
                    full_name, email, registration_number, password_hash, role, is_active
                )
                VALUES (
                    :full_name, :email, :registration_number, :password_hash,
                    CAST('STUDENT' AS user_role), true
                )
                RETURNING id
                """
            ),
            {
                "full_name": f"Shared user {suffix}",
                "email": f"{self.value(suffix).lower()}@example.test",
                "registration_number": self.value(f"user_{suffix}").upper(),
                "password_hash": "test-only-not-a-real-password-hash",
            },
        ).scalar_one()

    def create_team(self, cycle_id: int, user_id: int) -> int:
        return self.connection.execute(
            text(
                """
                INSERT INTO teams (academic_cycle_id, shared_user_id)
                VALUES (:cycle_id, :user_id)
                RETURNING id
                """
            ),
            {"cycle_id": cycle_id, "user_id": user_id},
        ).scalar_one()

    def create_member(
        self,
        team_id: int,
        cycle_id: int,
        suffix: str,
        *,
        full_name: str | None = None,
        registration_number: str | None = None,
        university_email: str | None = None,
        is_creator: bool = False,
    ) -> int:
        return self.connection.execute(
            text(
                """
                INSERT INTO team_members (
                    team_id, academic_cycle_id, full_name, registration_number,
                    university_email, is_creator, is_active
                )
                VALUES (
                    :team_id, :cycle_id, :full_name, :registration_number,
                    :university_email, :is_creator, true
                )
                RETURNING id
                """
            ),
            {
                "team_id": team_id,
                "cycle_id": cycle_id,
                "full_name": full_name or f"Student {suffix}",
                "registration_number": registration_number
                or self.value(f"reg_{suffix}").upper(),
                "university_email": university_email
                or f"{self.value(suffix)}@contact.test",
                "is_creator": is_creator,
            },
        ).scalar_one()

    def assert_constraint_rejected(self, statement: str, params: dict[str, Any]) -> None:
        """Assert one failing statement rolls back only its nested savepoint."""

        savepoint = self.connection.begin_nested()
        try:
            with self.assertRaises(IntegrityError):
                self.connection.execute(text(statement), params)
        finally:
            savepoint.rollback()

    def test_duplicate_registration_within_one_team_is_rejected(self) -> None:
        cycle_id = self.create_cycle("ONE")
        team_id = self.create_team(cycle_id, self.create_user("ONE"))
        registration = self.value("SAME-REG").upper()
        self.create_member(team_id, cycle_id, "one", registration_number=registration)

        self.assert_constraint_rejected(
            """
            INSERT INTO team_members (
                team_id, academic_cycle_id, full_name, registration_number,
                university_email, is_creator, is_active
            ) VALUES (:team_id, :cycle_id, 'Another student', :registration, :email, false, true)
            """,
            {
                "team_id": team_id,
                "cycle_id": cycle_id,
                "registration": registration,
                "email": f"{self.value('another')}@contact.test",
            },
        )

    def test_duplicate_active_registration_across_teams_in_one_cycle_is_rejected(self) -> None:
        cycle_id = self.create_cycle("REG-CYCLE")
        first_team = self.create_team(cycle_id, self.create_user("REG-ONE"))
        second_team = self.create_team(cycle_id, self.create_user("REG-TWO"))
        registration = self.value("CYCLE-REG").upper()
        self.create_member(first_team, cycle_id, "reg-one", registration_number=registration)

        self.assert_constraint_rejected(
            """
            INSERT INTO team_members (
                team_id, academic_cycle_id, full_name, registration_number,
                university_email, is_creator, is_active
            ) VALUES (:team_id, :cycle_id, 'Different team', :registration, :email, false, true)
            """,
            {
                "team_id": second_team,
                "cycle_id": cycle_id,
                "registration": registration,
                "email": f"{self.value('reg-two')}@contact.test",
            },
        )

    def test_duplicate_active_contact_email_in_one_cycle_is_rejected(self) -> None:
        cycle_id = self.create_cycle("EMAIL-CYCLE")
        first_team = self.create_team(cycle_id, self.create_user("EMAIL-ONE"))
        second_team = self.create_team(cycle_id, self.create_user("EMAIL-TWO"))
        contact_email = f"{self.value('contact')}@contact.test"
        self.create_member(first_team, cycle_id, "email-one", university_email=contact_email)

        self.assert_constraint_rejected(
            """
            INSERT INTO team_members (
                team_id, academic_cycle_id, full_name, registration_number,
                university_email, is_creator, is_active
            ) VALUES (:team_id, :cycle_id, 'Different team', :registration, :email, false, true)
            """,
            {
                "team_id": second_team,
                "cycle_id": cycle_id,
                "registration": self.value("email-two-reg").upper(),
                "email": contact_email,
            },
        )

    def test_noncanonical_registration_and_email_values_are_rejected(self) -> None:
        cycle_id = self.create_cycle("CANONICAL")
        team_id = self.create_team(cycle_id, self.create_user("CANONICAL"))

        self.assert_constraint_rejected(
            """
            INSERT INTO team_members (
                team_id, academic_cycle_id, full_name, registration_number,
                university_email, is_creator, is_active
            ) VALUES (:team_id, :cycle_id, 'Student', ' lower-reg ', :email, false, true)
            """,
            {
                "team_id": team_id,
                "cycle_id": cycle_id,
                "email": f"{self.value('canonical-reg')}@contact.test",
            },
        )
        self.assert_constraint_rejected(
            """
            INSERT INTO team_members (
                team_id, academic_cycle_id, full_name, registration_number,
                university_email, is_creator, is_active
            ) VALUES (:team_id, :cycle_id, 'Student', :registration, 'Mixed@Contact.Test', false, true)
            """,
            {
                "team_id": team_id,
                "cycle_id": cycle_id,
                "registration": self.value("canonical-email-reg").upper(),
            },
        )

    def test_same_name_students_with_distinct_identifiers_are_allowed(self) -> None:
        cycle_id = self.create_cycle("NAMES")
        team_id = self.create_team(cycle_id, self.create_user("NAMES"))
        self.create_member(team_id, cycle_id, "name-one", full_name="Alex Khan")
        self.create_member(team_id, cycle_id, "name-two", full_name="Alex Khan")

        count = self.connection.execute(
            text("SELECT count(*) FROM team_members WHERE team_id = :team_id"),
            {"team_id": team_id},
        ).scalar_one()
        self.assertEqual(count, 2)

    def test_member_team_cycle_mismatch_is_rejected(self) -> None:
        team_cycle = self.create_cycle("TEAM-CYCLE")
        member_cycle = self.create_cycle("MEMBER-CYCLE")
        team_id = self.create_team(team_cycle, self.create_user("MISMATCH"))

        self.assert_constraint_rejected(
            """
            INSERT INTO team_members (
                team_id, academic_cycle_id, full_name, registration_number,
                university_email, is_creator, is_active
            ) VALUES (:team_id, :cycle_id, 'Student', :registration, :email, false, true)
            """,
            {
                "team_id": team_id,
                "cycle_id": member_cycle,
                "registration": self.value("mismatch-reg").upper(),
                "email": f"{self.value('mismatch')}@contact.test",
            },
        )

    def test_second_creator_is_rejected(self) -> None:
        cycle_id = self.create_cycle("CREATOR")
        team_id = self.create_team(cycle_id, self.create_user("CREATOR"))
        self.create_member(team_id, cycle_id, "creator-one", is_creator=True)

        self.assert_constraint_rejected(
            """
            INSERT INTO team_members (
                team_id, academic_cycle_id, full_name, registration_number,
                university_email, is_creator, is_active
            ) VALUES (:team_id, :cycle_id, 'Second creator', :registration, :email, true, true)
            """,
            {
                "team_id": team_id,
                "cycle_id": cycle_id,
                "registration": self.value("creator-two-reg").upper(),
                "email": f"{self.value('creator-two')}@contact.test",
            },
        )

    def test_shared_user_cannot_link_to_two_teams(self) -> None:
        first_cycle = self.create_cycle("USER-ONE")
        second_cycle = self.create_cycle("USER-TWO")
        user_id = self.create_user("SHARED")
        self.create_team(first_cycle, user_id)

        self.assert_constraint_rejected(
            """
            INSERT INTO teams (academic_cycle_id, shared_user_id)
            VALUES (:cycle_id, :user_id)
            """,
            {"cycle_id": second_cycle, "user_id": user_id},
        )

    def test_member_identifiers_can_recur_in_different_academic_cycles(self) -> None:
        first_cycle = self.create_cycle("RECUR-ONE")
        second_cycle = self.create_cycle("RECUR-TWO")
        first_team = self.create_team(first_cycle, self.create_user("RECUR-ONE"))
        second_team = self.create_team(second_cycle, self.create_user("RECUR-TWO"))
        registration = self.value("RECURRING-REG").upper()
        email = f"{self.value('recurring')}@contact.test"

        self.create_member(
            first_team,
            first_cycle,
            "recur-one",
            registration_number=registration,
            university_email=email,
        )
        self.create_member(
            second_team,
            second_cycle,
            "recur-two",
            registration_number=registration,
            university_email=email,
        )

        count = self.connection.execute(
            text(
                """
                SELECT count(*) FROM team_members
                WHERE registration_number = :registration
                  AND university_email = :email
                """
            ),
            {"registration": registration, "email": email},
        ).scalar_one()
        self.assertEqual(count, 2)
