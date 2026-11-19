import unittest
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.auth import utc_now
from app.database import engine, get_db
from app import main
from app.models import (
    AcademicCycle,
    CollaborationChannel,
    CollaborationMessage,
    DocumentSubmission,
    DocumentRequirementSection,
    DocumentUploadRequirement,
    EvaluationRecord,
    GroupMessage,
    ProjectMilestone,
    ProjectTask,
    ProposalComplianceSubmission,
    SupervisorAssignment,
    SupervisorRequest,
    SupervisionMeeting,
    Team,
    TeamMember,
    User,
    UserRole,
)


class StudentGroupDeleteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.connection = engine.connect()
        cls.transaction = cls.connection.begin()
        cls.original_db = main.get_db
        main.app.dependency_overrides[get_db] = cls.db

    @classmethod
    def tearDownClass(cls):
        main.app.dependency_overrides.pop(get_db, None)
        cls.transaction.rollback()
        cls.connection.close()

    @classmethod
    def db(cls):
        session = Session(bind=cls.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()

    def setUp(self):
        self.session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        self.admin = self.session.scalar(select(User).where(User.role == UserRole.ADMIN).order_by(User.id).limit(1))
        self.cycle = self.session.scalar(select(AcademicCycle).order_by(AcademicCycle.id).limit(1))
        self.section = self.session.scalar(select(DocumentRequirementSection).where(DocumentRequirementSection.academic_cycle_id == self.cycle.id).order_by(DocumentRequirementSection.id).limit(1))
        if self.section is None:
            self.section = DocumentRequirementSection(academic_cycle_id=self.cycle.id, code=f"DELETE-{uuid4().hex[:8]}", name="Delete smoke", display_order=999)
            self.session.add(self.section)
            self.session.flush()
        suffix = uuid4().hex[:12]
        account = User(
            full_name="Delete Smoke Group",
            email=f"delete-smoke-{suffix}@example.com",
            registration_number=f"D{suffix[:9]}".upper(),
            password_hash="test",
            role=UserRole.STUDENT,
        )
        self.session.add(account)
        self.session.flush()
        group = Team(academic_cycle_id=self.cycle.id, shared_user_id=account.id, status="forming")
        self.session.add(group)
        self.session.flush()
        self.group = group
        self.account = account
        self.session.add(TeamMember(
            team_id=group.id,
            academic_cycle_id=self.cycle.id,
            full_name="Delete Smoke Group",
            registration_number=account.registration_number,
            university_email=account.email,
            is_creator=True,
        ))
        assignment = SupervisorAssignment(
            team_id=group.id,
            academic_cycle_id=self.cycle.id,
            supervisor_id=self.admin.id,
            assigned_by_id=self.admin.id,
            academic_year=self.cycle.academic_year,
            session=self.cycle.session,
        )
        self.session.add(assignment)
        self.session.flush()
        request = SupervisorRequest(
            academic_cycle_id=self.cycle.id,
            requester_user_id=account.id,
            team_id=group.id,
            supervisor_id=self.admin.id,
            assignment_id=assignment.id,
            proposal_type="SHORT",
            title="Delete smoke request",
            status="DRAFT",
        )
        self.session.add(request)
        self.session.add(ProjectMilestone(team_id=group.id, created_by_id=self.admin.id, title="Delete milestone"))
        self.session.add(ProjectTask(team_id=group.id, created_by_id=self.admin.id, title="Delete task"))
        self.session.add(SupervisionMeeting(team_id=group.id, supervisor_id=self.admin.id, created_by_id=self.admin.id, held_at=utc_now(), minutes="Delete meeting"))
        self.session.add(GroupMessage(team_id=group.id, author_id=account.id, author_kind="STUDENT", channel="General", body="Delete message"))
        channel = CollaborationChannel(team_id=group.id, supervisor_id=self.admin.id, academic_year=self.cycle.academic_year or 2027, session=self.cycle.session or "SPRING", assignment_id=assignment.id)
        self.session.add(channel)
        self.session.flush()
        self.session.add(CollaborationMessage(channel_id=channel.id, sender_user_id=account.id, message_text="Delete collaboration message"))
        self.session.add(ProposalComplianceSubmission(
            proposal_key=f"delete-smoke-{suffix}",
            owner_user_id=account.id,
            team_id=group.id,
            proposal_type="SHORT",
            title="Delete smoke proposal",
            version=1,
            status="SUBMITTED",
            processing_status="COMPLETED",
            filename="delete-smoke.pdf",
            content_type="application/pdf",
            file_size=1,
            sha256="0" * 64,
            page_count=1,
            storage_key="delete-smoke.pdf",
            extracted_text="Delete smoke",
            extracted_fields={},
        ))
        self.session.add(EvaluationRecord(
            group_id=group.id,
            evaluator_id=self.admin.id,
            evaluator_role="ADMIN",
            evaluation_category="PROPOSAL",
            maximum_marks=10,
            status="DRAFT",
        ))
        requirement = DocumentUploadRequirement(
            title="Delete smoke requirement",
            description="Delete smoke",
            academic_cycle_id=self.cycle.id,
            section_id=self.section.id,
            module="Delete smoke",
            assigned_group_id=group.id,
            due_at=utc_now() + timedelta(days=1),
            created_by_id=self.admin.id,
        )
        self.session.add(requirement)
        self.session.flush()
        self.session.add(DocumentSubmission(
            requirement_id=requirement.id,
            student_id=account.id,
            group_id=group.id,
            academic_cycle_id=self.cycle.id,
            uploaded_by_id=account.id,
            status="UPLOADED",
        ))
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_group_detail_uses_the_selected_group_project_and_supervisor(self):
        detail = main.student_group_detail(self.session, self.group)
        self.assertEqual(detail["project"]["title"], "Delete smoke request")
        self.assertEqual(detail["project"]["status"], "DRAFT")
        self.assertEqual(detail["supervisor"]["id"], self.admin.id)

        suffix = uuid4().hex[:12]
        other_account = User(
            full_name="Other Group",
            email=f"other-group-{suffix}@example.com",
            registration_number=f"O{suffix[:9]}".upper(),
            password_hash="test",
            role=UserRole.STUDENT,
        )
        self.session.add(other_account)
        self.session.flush()
        other_group = Team(academic_cycle_id=self.cycle.id, shared_user_id=other_account.id, status="forming")
        self.session.add(other_group)
        self.session.flush()
        self.session.add(TeamMember(
            team_id=other_group.id,
            academic_cycle_id=self.cycle.id,
            full_name="Other Group",
            registration_number=other_account.registration_number,
            university_email=other_account.email,
            is_creator=True,
        ))
        other_assignment = SupervisorAssignment(
            team_id=other_group.id,
            academic_cycle_id=self.cycle.id,
            supervisor_id=self.admin.id,
            assigned_by_id=self.admin.id,
            academic_year=self.cycle.academic_year,
            session=self.cycle.session,
        )
        self.session.add(other_assignment)
        self.session.flush()
        self.session.add(SupervisorRequest(
            academic_cycle_id=self.cycle.id,
            requester_user_id=other_account.id,
            team_id=other_group.id,
            supervisor_id=self.admin.id,
            assignment_id=other_assignment.id,
            proposal_type="SHORT",
            title="Other group request",
            status="DRAFT",
        ))
        self.session.flush()
        other_detail = main.student_group_detail(self.session, other_group)
        self.assertEqual(other_detail["project"]["title"], "Other group request")
        self.assertNotEqual(detail["project"]["title"], other_detail["project"]["title"])

    def test_admin_group_list_is_scoped_to_the_selected_cycle(self):
        suffix = uuid4().hex[:12]
        other_cycle = AcademicCycle(code=f"SCOPE-{suffix[:6].upper()}", display_name=f"Scope cycle {suffix}")
        other_account = User(
            full_name="Other Cycle Group",
            email=f"other-cycle-{suffix}@example.com",
            registration_number=f"C{suffix[:9]}".upper(),
            password_hash="test",
            role=UserRole.STUDENT,
        )
        self.session.add_all([other_cycle, other_account])
        self.session.flush()
        other_group = Team(academic_cycle_id=other_cycle.id, shared_user_id=other_account.id, status="forming")
        self.session.add(other_group)
        self.session.commit()

        result = main.list_student_groups(cycle_id=self.cycle.id, search=None, is_active=None, _=self.admin, session=self.session)
        result_ids = {item["id"] for item in result["items"]}
        self.assertIn(self.group.id, result_ids)
        self.assertNotIn(other_group.id, result_ids)

    def test_permanent_delete_removes_group_owned_records(self):
        response = main.delete_student_group(
            self.group.id,
            Request({"type": "http", "method": "DELETE", "headers": []}),
            self.admin,
            self.session,
        )
        self.assertEqual(response.status_code, 204)
        self.assertIsNone(self.session.get(Team, self.group.id))
        self.assertIsNone(self.session.get(User, self.account.id))
        self.assertEqual(self.session.execute(select(TeamMember).where(TeamMember.team_id == self.group.id)).scalars().all(), [])
