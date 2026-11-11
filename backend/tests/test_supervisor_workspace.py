"""Transactional integration checks for the supervisor group workspace."""
from datetime import timedelta
import unittest
import asyncio
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from starlette.datastructures import Headers, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import utc_now
from app.models import (TeamMember, SupervisorRequest, SupervisorAssignment,
                        DocumentUploadRequirement, DocumentSubmission, DocumentSubmissionVersion,
                        ProjectMilestone, ProjectTask, SupervisorCapacityPolicy, Team)
from tests import test_supervisor_requests as request_tests


class SupervisorWorkspaceTests(unittest.TestCase):
    setUpClass = classmethod(request_tests.SupervisorRequestTests.setUpClass.__func__)
    tearDownClass = classmethod(request_tests.SupervisorRequestTests.tearDownClass.__func__)
    get_test_db = classmethod(request_tests.SupervisorRequestTests.get_test_db.__func__)
    call = request_tests.SupervisorRequestTests.call
    proposal_pdf = staticmethod(request_tests.SupervisorRequestTests.proposal_pdf)
    multipart_call = request_tests.SupervisorRequestTests.multipart_call
    create_draft = request_tests.SupervisorRequestTests.create_draft
    confirm = request_tests.SupervisorRequestTests.confirm
    submit = request_tests.SupervisorRequestTests.submit

    def setUp(self):
        request_tests.SupervisorRequestTests.setUp(self)
        db = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        from app.models import AcademicCycle
        used = set(db.scalars(select(AcademicCycle.academic_year).where(AcademicCycle.session == "SPRING")).all())
        self.cycle.academic_year = next(year for year in range(2099, 2000, -1) if year not in used)
        self.cycle.session = "SPRING"
        db.merge(self.cycle)
        db.add(TeamMember(team_id=self.team.id, academic_cycle_id=self.cycle.id, full_name="Student Leader", registration_number=self.team_user.registration_number, university_email=self.team_user.email, is_creator=True))
        db.add(TeamMember(team_id=self.team.id, academic_cycle_id=self.cycle.id, full_name="Student Member", registration_number=f"MEM{self.team.id}", university_email=f"member{self.team.id}@example.com"))
        self.req = SupervisorRequest(team_id=self.team.id, academic_cycle_id=self.cycle.id, requester_user_id=self.team_user.id, supervisor_id=self.supervisor.id, title="Accessible research workspace", summary="A shared research project", objectives="Collect evidence", scope="Campus research", status="SUBMITTED", submitted_at=utc_now())
        db.add(self.req)
        self.document_req = DocumentUploadRequirement(title="Research report", academic_cycle_id=self.cycle.id, module="General", created_by_id=self.admin.id, visible_to_roles=["STUDENT"], allowed_file_types=["pdf"], due_at=utc_now()+timedelta(days=1), status="PUBLISHED")
        db.add(self.document_req); db.flush()
        self.submission = DocumentSubmission(requirement_id=self.document_req.id, student_id=self.team_user.id, group_id=self.team.id, status="UPLOADED", is_late=False)
        db.add(self.submission); db.flush()
        db.add(DocumentSubmissionVersion(submission_id=self.submission.id, version_number=1, original_filename="research.pdf", stored_filename=f"research-{self.team.id}.pdf", mime_type="application/pdf", file_size=15, storage_reference="test/missing.pdf", uploaded_by_id=self.team_user.id))
        db.add(ProjectMilestone(team_id=self.team.id, created_by_id=self.team_user.id, title="Research", completion_percent=40))
        db.add(ProjectTask(team_id=self.team.id, created_by_id=self.team_user.id, title="Gather evidence", completion_percent=60))
        db.commit(); db.close()

    def accept_workspace(self):
        status, body = self.call("POST", f"/api/v1/supervisor/requests/{self.req.id}/accept", {"revision": 1}, self.tokens["supervisor"])
        self.assertEqual(status, 200, body)
        return body

    def test_workspace_request_and_acceptance(self):
        status, request = self.call("GET", f"/api/v1/supervisor/requests/{self.req.id}", token=self.tokens["supervisor"])
        self.assertEqual(status, 200)
        self.assertEqual(len(request["workspace"]["members"]), 2)
        self.assertEqual(request["workspace"]["proposal"]["objectives"], "Collect evidence")
        self.assertEqual(request["workspace"]["documents"][0]["submissions"][0]["versions"][0]["original_filename"], "research.pdf")
        accepted = self.accept_workspace()
        status, groups = self.call("GET", "/api/v1/supervisor/assigned-groups", token=self.tokens["supervisor"])
        self.assertEqual(status, 200)
        group = next(g for g in groups if g["group"]["id"] == self.team.id)
        self.assertEqual(group["group"]["name"], "Student Leader's Group")
        self.assertEqual(group["group"]["academic_cycle"]["year"], self.cycle.academic_year)
        self.assertEqual(group["assignment"]["request_id"], self.req.id)
        self.assertEqual(group["project"]["completion_percentage"], 60)
        self.assertEqual(group["progress"]["milestones"][0]["title"], "Research")
        self.assertEqual(group["conversation"]["assignment_id"], group["assignment"]["id"])
        self.assertEqual(accepted["status"], "ACCEPTED")

    def test_workspace_ownership_and_download_denial(self):
        self.accept_workspace()
        for suffix in ("", "/members", "/proposal", "/project", "/documents", "/progress", "/conversation"):
            self.assertEqual(self.call("GET", f"/api/v1/supervisor/groups/{self.team.id}{suffix}", token=self.tokens["other"])[0], 404)
        self.assertEqual(self.call("GET", f"/api/v1/supervisor/requests/{self.req.id}", token=self.tokens["other"])[0], 404)
        _, data = self.call("GET", f"/api/v1/supervisor/groups/{self.team.id}", token=self.tokens["supervisor"])
        url = data["documents"][0]["submissions"][0]["versions"][0]["download_url"]
        self.assertEqual(self.call("GET", url, token=self.tokens["other"])[0], 403)
        self.assertEqual(self.call("GET", url, token=self.tokens["supervisor"])[0], 410)

    def test_workspace_decision_comments(self):
        status, body = self.call("POST", f"/api/v1/supervisor/requests/{self.req.id}/request-changes", {"revision": 1, "comment": "Clarify scope"}, self.tokens["supervisor"])
        self.assertEqual((status, body["status"]), (200, "CHANGES_REQUESTED"))
        status, body = self.call("POST", f"/api/v1/supervisor/requests/{self.req.id}/reject", {"revision": body["revision"], "comment": "Scope outside expertise"}, self.tokens["supervisor"])
        self.assertEqual((status, body["status"]), (200, "REJECTED"))
        self.assertEqual(body["status_history"][-1]["comment"], "Scope outside expertise")
        _, groups = self.call("GET", "/api/v1/supervisor/assigned-groups", token=self.tokens["supervisor"])
        self.assertFalse(any(g["group"]["id"] == self.team.id for g in groups))

    def test_workspace_capacity_enforced(self):
        db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        policy = db.scalar(select(SupervisorCapacityPolicy).where(SupervisorCapacityPolicy.supervisor_id == self.supervisor.id))
        policy.max_group_capacity = 1
        db.add(SupervisorAssignment(team_id=self.team.id, academic_cycle_id=self.cycle.id, supervisor_id=self.supervisor.id, assigned_by_id=self.admin.id))
        db.commit(); db.close()
        status, body = self.call("POST", f"/api/v1/supervisor/requests/{self.req.id}/accept", {"revision": 1}, self.tokens["supervisor"])
        self.assertEqual(status, 409)
        self.assertEqual(body["detail"]["code"], "capacity_full")

    def test_workspace_conversation_and_empty_states(self):
        self.accept_workspace()
        status, body = self.call("POST", f"/api/v1/supervisor/groups/{self.team.id}/conversation", {"message_text": "Please share your sources"}, self.tokens["supervisor"])
        self.assertEqual(status, 201, body)
        status, body = self.call("GET", f"/api/v1/supervisor/groups/{self.team.id}/conversation", token=self.tokens["supervisor"])
        self.assertEqual((status, body["group_id"]), (200, self.team.id))
        self.assertEqual(body["messages"][-1]["message_text"], "Please share your sources")
        channel_id = body["channel_id"]
        status, student_messages = self.call("GET", f"/api/v1/student/collaboration/channels/{channel_id}/messages", token=self.tokens["team"])
        self.assertEqual(status, 200, student_messages)
        self.assertEqual(student_messages[-1]["message_text"], "Please share your sources")

    def test_workspace_empty_group(self):
        db = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        other_group = Team(academic_cycle_id=self.cycle.id, shared_user_id=self.student.id)
        db.add(other_group); db.flush()
        db.add(SupervisorAssignment(team_id=other_group.id, academic_cycle_id=self.cycle.id, supervisor_id=self.supervisor.id, assigned_by_id=self.admin.id))
        db.commit(); db.close()
        status, body = self.call("GET", f"/api/v1/supervisor/groups/{other_group.id}", token=self.tokens["supervisor"])
        self.assertEqual(status, 200)
        self.assertIsNone(body["proposal"])
        self.assertIsNone(body["project"])
        self.assertFalse(body["members"])
        self.assertFalse(body["progress"]["milestones"])
        self.assertFalse(body["documents"][0]["submissions"])

    def test_workspace_real_upload_download_and_refresh(self):
        from app.document_requirements import upload, download
        db = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        content = b"%PDF-1.4\nActual student submission\n%%EOF"
        with TemporaryDirectory() as directory, patch("app.document_requirements._stored_path", side_effect=lambda reference: Path(directory) / reference):
            uploaded = asyncio.run(upload(self.document_req.id, UploadFile(filename="updated-report.pdf", file=BytesIO(content), headers=Headers({"content-type": "application/pdf"})), None, self.team_user, db))
            latest = uploaded.versions[-1]
            response = download(uploaded.id, latest.id, self.supervisor, db)
            self.assertEqual(Path(response.path).read_bytes(), content)
            self.assertEqual(response.filename, "updated-report.pdf")
            status, body = self.call("GET", f"/api/v1/supervisor/requests/{self.req.id}", token=self.tokens["supervisor"])
            self.assertEqual(status, 200)
            self.assertEqual(body["workspace"]["documents"][0]["submissions"][0]["versions"][-1]["original_filename"], "updated-report.pdf")
        db.close()

    def test_student_submission_to_supervisor_assignment_flow(self):
        db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        existing = db.get(SupervisorRequest, self.req.id)
        existing.status = "REJECTED"
        db.commit(); db.close()
        status, draft = self.create_draft(self.tokens["team"], submission_note="Please supervise our research.")
        self.assertEqual(status, 201, draft)
        status, submitted = self.submit(draft, self.tokens["team"])
        self.assertEqual(status, 200, submitted)
        status, request = self.call("GET", f"/api/v1/supervisor/requests/{draft['id']}", token=self.tokens["supervisor"])
        self.assertEqual(status, 200)
        self.assertEqual(len(request["workspace"]["members"]), 2)
        self.assertEqual(request["workspace"]["proposal"]["title"], "Campus Safety Study")
        status, accepted = self.call("POST", f"/api/v1/supervisor/requests/{draft['id']}/accept", {"revision": submitted["revision"]}, self.tokens["supervisor"])
        self.assertEqual((status, accepted["status"]), (200, "ACCEPTED"))
        status, workspace = self.call("GET", f"/api/v1/supervisor/groups/{self.team.id}", token=self.tokens["supervisor"])
        self.assertEqual(status, 200)
        self.assertEqual(workspace["proposal"]["title"], "Campus Safety Study")
        self.assertTrue(workspace["proposal"]["document"]["document_url"])
        self.assertTrue(workspace["conversation"])
