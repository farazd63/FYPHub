"""Authorized, read-only academic-cycle dashboard aggregation."""

from collections import defaultdict
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import require_roles
from .database import get_db
from .models import (
    AcademicCycle,
    DocumentSubmission,
    DocumentSubmissionVersion,
    DocumentUploadRequirement,
    SupervisorAssignment,
    SupervisorCapacityPolicy,
    SupervisorRequest,
    Team,
    TeamMember,
    User,
    UserRole,
)

router = APIRouter(prefix="/api/v1/academic-cycles", tags=["academic-cycles"])
COORDINATOR_ROLES = (UserRole.ADMIN, UserRole.COORDINATOR)
logger = logging.getLogger("fyphub.academic_cycle_overview")


def _user(user: User | None) -> dict | None:
    if user is None:
        return None
    return {"id": user.id, "name": user.full_name, "full_name": user.full_name, "email": user.email, "registration_number": user.registration_number}


@router.get("/{cycle_id}/overview")
def cycle_overview(cycle_id: int, _: User = Depends(require_roles(*COORDINATOR_ROLES)), db: Session = Depends(get_db)) -> dict:
    cycle = db.get(AcademicCycle, cycle_id)
    if cycle is None:
        logger.info("academic_cycle_overview cycle_id=%s lookup_status=missing response_status=404", cycle_id)
        raise HTTPException(status_code=404, detail="Academic cycle not found.")

    users = {user.id: user for user in db.scalars(select(User)).all()}
    teams = db.scalars(select(Team).where(Team.academic_cycle_id == cycle_id).order_by(Team.id)).all()
    team_ids = [team.id for team in teams]
    members = db.scalars(select(TeamMember).where(TeamMember.academic_cycle_id == cycle_id, TeamMember.is_active.is_(True)).order_by(TeamMember.team_id, TeamMember.id)).all()
    assignments = db.scalars(select(SupervisorAssignment).where(SupervisorAssignment.academic_cycle_id == cycle_id, SupervisorAssignment.ended_at.is_(None)).order_by(SupervisorAssignment.id)).all()
    requests = db.scalars(select(SupervisorRequest).where(SupervisorRequest.academic_cycle_id == cycle_id).order_by(SupervisorRequest.updated_at.desc(), SupervisorRequest.id.desc())).all()
    policies = {row.supervisor_id: row for row in db.scalars(select(SupervisorCapacityPolicy).where(SupervisorCapacityPolicy.academic_year == cycle.academic_year if cycle.academic_year is not None else SupervisorCapacityPolicy.academic_cycle_id == cycle_id)).all()}
    requirements = db.scalars(select(DocumentUploadRequirement).where(DocumentUploadRequirement.academic_cycle_id == cycle_id).order_by(DocumentUploadRequirement.due_at, DocumentUploadRequirement.id)).all()
    requirement_ids = [item.id for item in requirements]
    submissions = db.scalars(select(DocumentSubmission).where(DocumentSubmission.requirement_id.in_(requirement_ids))).all() if requirement_ids else []
    submission_ids = [item.id for item in submissions]
    version_counts = {}
    if submission_ids:
        version_counts = dict(db.execute(select(DocumentSubmissionVersion.submission_id, func.count(DocumentSubmissionVersion.id)).where(DocumentSubmissionVersion.submission_id.in_(submission_ids)).group_by(DocumentSubmissionVersion.submission_id)).all())

    members_by_team: dict[int, list[TeamMember]] = defaultdict(list)
    for member in members:
        members_by_team[member.team_id].append(member)
    requests_by_team: dict[int, list[SupervisorRequest]] = defaultdict(list)
    for item in requests:
        if item.team_id is not None:
            requests_by_team[item.team_id].append(item)
    assignment_by_team = {item.team_id: item for item in assignments}
    submission_by_requirement: dict[int, list[DocumentSubmission]] = defaultdict(list)
    for item in submissions:
        submission_by_requirement[item.requirement_id].append(item)

    supervisor_ids = {item.supervisor_id for item in assignments}
    supervisor_ids.update(item.supervisor_id for item in requests)
    supervisor_ids.update(policies)
    supervisor_rows = []
    for supervisor_id in sorted(supervisor_ids):
        supervisor = users.get(supervisor_id)
        if supervisor is None:
            continue
        assigned_groups = [item for item in assignments if item.supervisor_id == supervisor_id]
        accepted_requests = [item for item in requests if item.supervisor_id == supervisor_id and item.status == "ACCEPTED"]
        used = len(assigned_groups) + len([item for item in accepted_requests if item.assignment_id is None])
        capacity = policies.get(supervisor_id)
        supervisor_rows.append({**(_user(supervisor) or {}), "department": None, "assigned_students": len({member.id for item in assigned_groups for member in members_by_team.get(item.team_id, [])}), "assigned_groups": len(assigned_groups), "active_projects": len([item for item in requests if item.supervisor_id == supervisor_id and item.status not in {"REJECTED", "WITHDRAWN"}]), "capacity": capacity.max_group_capacity if capacity else None, "capacity_used": used, "available_capacity": max(capacity.max_group_capacity - used, 0) if capacity else None, "assignment_status": "ASSIGNED" if assigned_groups else "AVAILABLE"})

    project_rows = []
    for item in requests:
        team = next((row for row in teams if row.id == item.team_id), None)
        requester = users.get(item.requester_user_id)
        supervisor = users.get(item.supervisor_id)
        project_rows.append({"id": item.id, "title": item.title or f"Proposal {item.id}", "student_or_group": team.id if team else (requester.full_name if requester else "Unassigned"), "team_id": team.id if team else None, "supervisor": _user(supervisor), "proposal_type": item.proposal_type, "proposal_status": item.status, "project_stage": item.status, "submission_date": item.submitted_at, "last_updated": item.updated_at, "review_status": item.status, "related_documents_count": 1 if item.document_id else 0, "requester": _user(requester)})

    group_rows = []
    for team in teams:
        assignment = assignment_by_team.get(team.id)
        project = requests_by_team.get(team.id, [None])[0]
        group_rows.append({"id": team.id, "group_id": team.id, "name": f"Group {team.id}", "leader": _user(users.get(team.shared_user_id)), "members": [{"id": member.id, "name": member.full_name, "registration_number": member.registration_number, "email": member.university_email} for member in members_by_team.get(team.id, [])], "assigned_supervisor": _user(users.get(assignment.supervisor_id)) if assignment else None, "project_title": project.title if project else None, "status": "ACTIVE", "created_at": team.created_at})

    active_requirements = [item for item in requirements if item.status != "ARCHIVED"]
    student_rows = []
    for member in members:
        project = requests_by_team.get(member.team_id, [None])[0]
        assignment = assignment_by_team.get(member.team_id)
        student_id = next((user.id for user in users.values() if user.registration_number == member.registration_number or user.email == member.university_email), None)
        student_submissions = [submission for requirement_id in requirement_ids for submission in submission_by_requirement.get(requirement_id, []) if student_id is not None and submission.student_id == student_id]
        complete = len({submission.requirement_id for submission in student_submissions if submission.status in {"UPLOADED", "APPROVED"}})
        student_rows.append({"id": member.id, "name": member.full_name, "registration_number": member.registration_number, "email": member.university_email, "group_id": member.team_id, "project_title": project.title if project else None, "supervisor": _user(users.get(assignment.supervisor_id)) if assignment else None, "proposal_status": project.status if project else None, "completion_stage": project.status if project else None, "required_document_status": "COMPLETE" if active_requirements and complete >= len(active_requirements) else "PENDING" if active_requirements else "NO_REQUIREMENTS", "assignment_status": "ASSIGNED" if assignment else "UNASSIGNED"})

    document_rows = []
    for requirement in requirements:
        document_rows.append({"id": requirement.id, "requirement_id": requirement.id, "title": requirement.title, "status": requirement.status, "due_at": requirement.due_at, "allowed_file_types": requirement.allowed_file_types or [], "submissions": [{"id": submission.id, "student_id": submission.student_id, "status": submission.status, "is_late": submission.is_late, "uploaded_at": submission.uploaded_at, "version_count": version_counts.get(submission.id, 0)} for submission in submission_by_requirement.get(requirement.id, [])]})

    active_projects = [item for item in requests if item.status not in {"REJECTED", "WITHDRAWN"}]
    summary = {"supervisors": len(supervisor_rows), "students": len({member.id for member in members}), "groups": len(teams), "projects": len(project_rows), "active_projects": len(active_projects), "completed_projects": len([item for item in requests if item.status == "ACCEPTED"]), "pending_reviews": len([item for item in requests if item.status in {"SUBMITTED", "CHANGES_REQUESTED"}]), "required_documents": len(active_requirements)}
    logger.info("academic_cycle_overview cycle_id=%s lookup_status=found response_status=200", cycle_id)
    return {"cycle": {"id": cycle.id, "code": cycle.code, "display_name": cycle.display_name, "status": "ACTIVE" if cycle.registration_open else "CLOSED", "registration_open": cycle.registration_open, "start_date": None, "end_date": None, "department": None, "created_at": cycle.created_at, "updated_at": cycle.updated_at}, "summary": summary, "supervisors": supervisor_rows, "projects": project_rows, "groups": group_rows, "students": student_rows, "documents": document_rows}
