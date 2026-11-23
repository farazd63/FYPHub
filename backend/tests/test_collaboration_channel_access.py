"""Authenticated HTTP coverage for group-scoped private conversations."""
from datetime import timedelta
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE_NAME, utc_now
from app.collaboration_channels import router, ensure_collaboration_channel, _authorize
from app.database import engine
from app.models import AcademicCycle, AuthSession, CollaborationMessage, SupervisorAssignment, SupervisorRequest, Team, TeamMember, User, UserRole
from app.security import generate_session_token, hash_session_token


class CollaborationChannelAccessTests(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        self.addCleanup(self.connection.close)
        self.addCleanup(self.transaction.rollback)
        self.addCleanup(self.db.close)
        suffix = uuid4().hex[:12]
        self.users = {}
        for name, role in (("shared", UserRole.STUDENT), ("leader", UserRole.STUDENT), ("member", UserRole.STUDENT), ("outsider", UserRole.STUDENT), ("supervisor", UserRole.SUPERVISOR), ("other_supervisor", UserRole.SUPERVISOR), ("admin", UserRole.ADMIN)):
            self.users[name] = User(full_name=name.title(), email=f"{name}-{suffix}@example.com", registration_number=f"{name}-{suffix}".upper() if role == UserRole.STUDENT else None, role=role, password_hash="not-used", is_active=True)
        self.db.add_all(self.users.values()); self.db.flush()
        used_years = set(self.db.scalars(select(AcademicCycle.academic_year).where(AcademicCycle.session == "SPRING")))
        year = next(value for value in range(2100, 2201) if value not in used_years)
        cycle = AcademicCycle(code=f"CHAT-{suffix}", display_name=f"Chat Spring {year}", academic_year=year, session="SPRING", registration_open=True)
        self.db.add(cycle); self.db.flush()
        self.team = Team(academic_cycle_id=cycle.id, shared_user_id=self.users["shared"].id)
        self.other_team = Team(academic_cycle_id=cycle.id, shared_user_id=self.users["outsider"].id)
        self.db.add_all([self.team, self.other_team]); self.db.flush()
        self.members = []
        for name in ("leader", "member"):
            user = self.users[name]
            member = TeamMember(team_id=self.team.id, academic_cycle_id=cycle.id, full_name=user.full_name, registration_number=user.registration_number, university_email=user.email, is_creator=name == "leader", is_active=True)
            self.members.append(member)
        self.db.add_all(self.members)
        self.assignment = SupervisorAssignment(team_id=self.team.id, academic_cycle_id=cycle.id, supervisor_id=self.users["supervisor"].id, assigned_by_id=self.users["admin"].id, academic_year=year, session="SPRING")
        other_assignment = SupervisorAssignment(team_id=self.other_team.id, academic_cycle_id=cycle.id, supervisor_id=self.users["other_supervisor"].id, assigned_by_id=self.users["admin"].id, academic_year=year, session="SPRING")
        self.db.add_all([self.assignment, other_assignment]); self.db.flush()
        self.accepted = SupervisorRequest(team_id=self.team.id, academic_cycle_id=cycle.id, requester_user_id=self.users["shared"].id, supervisor_id=self.users["supervisor"].id, assignment_id=self.assignment.id, status="ACCEPTED", revision=1)
        self.db.add_all([self.accepted, SupervisorRequest(team_id=self.other_team.id, academic_cycle_id=cycle.id, requester_user_id=self.users["outsider"].id, supervisor_id=self.users["other_supervisor"].id, assignment_id=other_assignment.id, status="ACCEPTED", revision=1)])
        self.db.flush()
        self.channel = ensure_collaboration_channel(self.db, self.assignment, self.team)
        self.other_channel = ensure_collaboration_channel(self.db, other_assignment, self.other_team)
        self.tokens = {}
        for name, user in self.users.items():
            token = generate_session_token(); self.tokens[name] = token
            self.db.add(AuthSession(user_id=user.id, token_hash=hash_session_token(token), expires_at=utc_now() + timedelta(hours=1)))
        self.db.commit()
        application = FastAPI()
        application.include_router(router)
        from app.notifications import router as notifications_router
        application.include_router(notifications_router)
        from app.supervisor_workspace import router as workspace_router
        application.include_router(workspace_router)
        factory = patch("app.database.SessionLocal", side_effect=lambda: Session(bind=self.connection, autoflush=False, expire_on_commit=False, join_transaction_mode="create_savepoint"))
        factory.start()
        self.addCleanup(factory.stop)
        self.client = TestClient(application)
        self.addCleanup(self.client.close)

    def call(self, method, path, name="shared", **kwargs):
        headers = {"Cookie": f"{SESSION_COOKIE_NAME}={self.tokens[name]}", "Origin": "http://localhost:5173"}
        return self.client.request(method, path, headers=headers, **kwargs)

    def path(self, suffix=""):
        return f"/api/v1/student/collaboration/channels/{self.channel.id}{suffix}"

    def establish_identity(self, member_index=0, password="Member Pass1!"):
        response = self.call("POST", self.path("/member-identity/setup"), json={"member_id": self.members[member_index].id, "password": password, "confirm_password": password})
        self.assertEqual(response.status_code, 200, response.text)
        return response

    def test_all_members_and_shared_group_login_can_access_only_their_channel(self):
        # Portal authentication intentionally uses the existing shared group
        # principal. Membership authorization also supports member identities.
        for name in ("leader", "member"):
            _authorize(self.db, self.channel, self.users[name])
        for name in ("shared",):
            response = self.call("GET", "/api/v1/student/collaboration/channels", name)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual([row["id"] for row in response.json()], [self.channel.id])
            detail = self.call("GET", self.path(), name)
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["assignment_status"], "ACCEPTED")
            self.assertEqual(len(detail.json()["members"]), 2)

    def test_assigned_supervisor_access_and_message_creation(self):
        response = self.call("GET", f"/api/v1/supervisor/collaboration/channels/{self.channel.id}", "supervisor")
        self.assertEqual(response.status_code, 200, response.text)
        response = self.call("POST", self.path("/messages"), "supervisor", json={"message_text": "Please review the proposal."})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["sender_role"], "SUPERVISOR")
        existing_view = self.call("GET", f"/api/v1/supervisor/groups/{self.team.id}/conversation", "supervisor")
        self.assertEqual(existing_view.status_code, 200, existing_view.text)
        self.assertEqual(existing_view.json()["messages"][0]["message_text"], "Please review the proposal.")

    def test_message_owner_can_edit_and_soft_delete(self):
        self.establish_identity()
        created = self.call("POST", self.path("/messages"), json={"message_text": "Draft update", "sender_member_id": self.members[0].id}).json()
        edited = self.call("PATCH", self.path(f"/messages/{created['id']}"), json={"message_text": "Final update"})
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(edited.json()["message_text"], "Final update")

        deleted = self.call("DELETE", self.path(f"/messages/{created['id']}"))
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(deleted.json()["id"], created["id"])
        self.assertEqual(self.call("GET", self.path("/messages")).json(), [])

    def test_message_changes_are_limited_to_the_sender(self):
        self.establish_identity()
        created = self.call("POST", self.path("/messages"), json={"message_text": "Private note", "sender_member_id": self.members[0].id}).json()
        edit = self.call("PATCH", self.path(f"/messages/{created['id']}"), "supervisor", json={"message_text": "Changed by another user"})
        delete = self.call("DELETE", self.path(f"/messages/{created['id']}"), "supervisor")
        self.assertEqual(edit.status_code, 403, edit.text)
        self.assertEqual(delete.status_code, 403, delete.text)

    def test_other_group_supervisor_and_admin_are_rejected(self):
        for name in ("outsider", "other_supervisor", "admin"):
            self.assertEqual(self.call("GET", self.path(), name).status_code, 403)
            self.assertEqual(self.call("GET", self.path("/messages"), name).status_code, 403)
            self.assertEqual(self.call("POST", self.path("/messages"), name, json={"message_text": "Not allowed"}).status_code, 403)
            self.assertEqual(self.call("POST", self.path("/read"), name, json={"message_id": 1}).status_code, 403)

    def test_no_access_before_supervisor_acceptance(self):
        self.accepted.status = "SUBMITTED"; self.db.commit()
        self.assertEqual(self.call("GET", "/api/v1/student/collaboration/channels").json(), [])
        self.assertEqual(self.call("GET", self.path()).status_code, 403)
        self.assertEqual(self.call("POST", self.path("/messages"), json={"message_text": "Not yet"}).status_code, 403)

    def test_ended_assignment_and_removed_member_cannot_access(self):
        self.members[1].is_active = False; self.db.commit()
        with self.assertRaises(HTTPException) as error:
            _authorize(self.db, self.channel, self.users["member"])
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(self.call("GET", self.path()).status_code, 200)
        self.assignment.ended_at = utc_now(); self.db.commit()
        self.assertEqual(self.call("GET", self.path()).status_code, 403)
        self.assertEqual(self.call("GET", self.path(), "supervisor").status_code, 403)

    def test_multiline_code_message_is_preserved_and_returned(self):
        self.establish_identity(member_index=1)
        value = "    function check() {\n        return '<script>plain text</script>';\n    }\n" + "long-line " * 200
        created = self.call("POST", self.path("/messages"), json={"message_text": value, "sender_member_id": self.members[1].id})
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["message_text"], value)
        self.assertEqual(created.json()["sender_member_id"], self.members[1].id)
        self.assertEqual(created.json()["sender_member_name"], self.members[1].full_name)
        response = self.call("GET", self.path("/messages"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["message_text"], value)
        self.assertIn("created_at", response.json()[0])

    def test_empty_overlong_and_spoofed_messages_are_rejected(self):
        for payload in ({"message_text": ""}, {"message_text": " \n\t "}, {"message_text": "x" * 4001}, {"message_text": "Hello", "sender_user_id": self.users["supervisor"].id}, {"message_text": "Hello"}):
            self.assertEqual(self.call("POST", self.path("/messages"), json=payload).status_code, 422)

    def test_read_markers_are_monotonic_and_scoped_to_channel(self):
        first = self.call("POST", self.path("/messages"), "supervisor", json={"message_text": "First"}).json()
        second = self.call("POST", self.path("/messages"), "supervisor", json={"message_text": "Second"}).json()
        self.assertEqual(self.call("GET", self.path()).json()["unread_count"], 2)
        marked = self.call("POST", self.path("/read"), json={"message_id": second["id"]})
        self.assertEqual(marked.status_code, 200, marked.text)
        self.assertEqual(self.call("GET", self.path()).json()["unread_count"], 0)
        self.assertEqual(self.call("POST", self.path("/read"), json={"message_id": first["id"]}).json()["last_read_message_id"], second["id"])
        other = CollaborationMessage(channel_id=self.other_channel.id, sender_user_id=self.users["outsider"].id, message_text="Private")
        self.db.add(other); self.db.commit()
        self.assertEqual(self.call("POST", self.path("/read"), json={"message_id": other.id}).status_code, 404)

    def test_history_pagination_and_authentication(self):
        self.establish_identity()
        first = self.call("POST", self.path("/messages"), json={"message_text": "Earlier", "sender_member_id": self.members[0].id}).json()
        second = self.call("POST", self.path("/messages"), json={"message_text": "Latest", "sender_member_id": self.members[0].id}).json()
        self.assertEqual([row["id"] for row in self.call("GET", self.path("/messages?limit=1")).json()], [second["id"]])
        self.assertEqual([row["id"] for row in self.call("GET", self.path(f"/messages?before_id={second['id']}&limit=1")).json()], [first["id"]])
        self.assertEqual(self.client.get(self.path()).status_code, 401)

    def test_member_password_gates_identity_and_admin_reset(self):
        status = self.call("GET", self.path("/member-identity"))
        self.assertEqual(status.status_code, 200, status.text)
        self.assertFalse(status.json()["members"][0]["password_set"])
        self.assertEqual(self.call("POST", self.path("/messages"), json={"message_text": "Not verified", "sender_member_id": self.members[0].id}).status_code, 403)

        self.establish_identity(member_index=1, password="Member Pass2!")
        wrong = self.call("POST", self.path("/member-identity/verify"), json={"member_id": self.members[1].id, "password": "Wrong Pass2!"})
        self.assertEqual(wrong.status_code, 401, wrong.text)
        created = self.call("POST", self.path("/messages"), json={"message_text": "Verified update", "sender_member_id": self.members[1].id})
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["sender_member_name"], self.members[1].full_name)

        forgot = self.call("POST", self.path("/member-identity/forgot"), json={"member_id": self.members[1].id})
        self.assertEqual(forgot.status_code, 200, forgot.text)
        admin_notifications = self.call("GET", "/api/v1/notifications", "admin")
        self.assertEqual(admin_notifications.status_code, 200, admin_notifications.text)
        reset_notification = next((row for row in admin_notifications.json() if row["kind"] == "COLLABORATION_PASSWORD_RESET_REQUESTED"), None)
        self.assertIsNotNone(reset_notification)
        self.assertEqual(reset_notification["payload"]["member_id"], self.members[1].id)
        credential_list = self.call("GET", "/api/v1/admin/collaboration-credentials", "admin")
        self.assertEqual(credential_list.status_code, 200, credential_list.text)
        listed_group = next(row for row in credential_list.json()["items"] if row["group_id"] == self.team.id)
        listed_member = next(row for row in listed_group["members"] if row["member_id"] == self.members[1].id)
        self.assertTrue(listed_member["reset_requested"])
        admin_view = self.call("GET", f"/api/v1/admin/student-groups/{self.team.id}/collaboration-credentials?cycle_id={self.team.academic_cycle_id}", "admin")
        self.assertEqual(admin_view.status_code, 200, admin_view.text)
        self.assertTrue(next(row for row in admin_view.json()["members"] if row["member_id"] == self.members[1].id)["reset_requested"])
        reset = self.call("POST", f"/api/v1/admin/student-groups/{self.team.id}/collaboration-credentials/{self.members[1].id}/reset?cycle_id={self.team.academic_cycle_id}", "admin")
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertTrue(reset.json()["password_removed"])
        self.assertEqual(self.call("POST", self.path("/messages"), json={"message_text": "Revoked", "sender_member_id": self.members[1].id}).status_code, 403)
        student_notifications = self.call("GET", "/api/v1/notifications")
        self.assertEqual(student_notifications.status_code, 200, student_notifications.text)
        resolved_notification = next((row for row in student_notifications.json() if row["kind"] == "COLLABORATION_PASSWORD_RESET_RESOLVED"), None)
        self.assertIsNotNone(resolved_notification)
        self.assertEqual(resolved_notification["payload"]["member_id"], self.members[1].id)
        status_after_reset = self.call("GET", self.path("/member-identity"))
        reset_member = next(row for row in status_after_reset.json()["members"] if row["member_id"] == self.members[1].id)
        self.assertFalse(reset_member["password_set"])
        self.assertFalse(reset_member["is_verified"])
        recreated = self.establish_identity(member_index=1, password="Member New2!")
        self.assertEqual(recreated.status_code, 200, recreated.text)
        forgot_again = self.call("POST", self.path("/member-identity/forgot"), json={"member_id": self.members[1].id})
        self.assertEqual(forgot_again.status_code, 200, forgot_again.text)
        admin_notifications_after_second_request = self.call("GET", "/api/v1/notifications", "admin")
        requested_notifications = [
            row for row in admin_notifications_after_second_request.json()
            if row["kind"] == "COLLABORATION_PASSWORD_RESET_REQUESTED"
            and row["payload"].get("member_id") == self.members[1].id
        ]
        self.assertGreaterEqual(len(requested_notifications), 2)
