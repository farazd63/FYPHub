"""Cycle-scoped, searchable archive for document requirements and submissions."""

from collections import defaultdict
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .auth import require_roles
from .database import get_db
from .document_requirements import _project_for_group
from .models import (
    AcademicCycle,
    DocumentArchiveReviewQueue,
    DocumentRequirementSection,
    DocumentSubmission,
    DocumentSubmissionReviewEvent,
    DocumentSubmissionVersion,
    DocumentUploadRequirement,
    SupervisorAssignment,
    SupervisorRequest,
    Team,
    TeamMember,
    User,
    UserRole,
)

router = APIRouter(prefix="/api/v1/admin/document-archive", tags=["document-archive"])
ARCHIVE_ROLES = (UserRole.ADMIN, UserRole.COORDINATOR)
ARCHIVE_REQUIREMENT_STATUSES = {"PUBLISHED", "CLOSED", "ARCHIVED", "ACTIVE"}


def _user(user: User | None) -> dict | None:
    if user is None:
        return None
    return {"id": user.id, "name": user.full_name, "email": user.email, "registration_number": user.registration_number}


def _cycle(db: Session, cycle_id: int) -> AcademicCycle:
    cycle = db.get(AcademicCycle, cycle_id)
    if cycle is None:
        raise HTTPException(404, "Academic cycle not found.")
    return cycle


def _group_code(cycle: AcademicCycle, group: Team) -> str:
    return f"{cycle.code}-{group.group_number if group.group_number is not None else 'UNASSIGNED'}"


def _group_name(group: Team, members: list[TeamMember]) -> str:
    return group.group_name or f"Group {group.group_number or '—'}"


def _members(db: Session, group_id: int, cycle_id: int) -> list[TeamMember]:
    return db.scalars(select(TeamMember).where(TeamMember.team_id == group_id, TeamMember.academic_cycle_id == cycle_id, TeamMember.is_active.is_(True)).order_by(TeamMember.is_creator.desc(), TeamMember.id)).all()


def _project(db: Session, group: Team):
    return _project_for_group(db, group.id, group.academic_cycle_id)


def _section(db: Session, requirement: DocumentUploadRequirement) -> dict:
    section = db.get(DocumentRequirementSection, requirement.section_id) if requirement.section_id else None
    return {"id": section.id if section else None, "name": section.name if section else (requirement.module or "Other"), "code": section.code if section else None, "display_order": section.display_order if section else 0}


def _status(requirement: DocumentUploadRequirement, submission: DocumentSubmission | None) -> str:
    if submission is None:
        return "CLOSED" if requirement.status == "CLOSED" else "NOT_SUBMITTED"
    return {
        "DRAFT": "DRAFT",
        "UPLOADED": "SUBMITTED",
        "UNDER_REVIEW": "UNDER_REVIEW",
        "RESUBMISSION_REQUIRED": "CHANGES_REQUESTED",
        "ACCEPTED": "ACCEPTED",
        "REJECTED": "REJECTED",
    }.get(submission.status, submission.status)


def _version_url(submission_id: int, version_id: int, kind: str) -> str:
    return f"/api/v1/document-requirements/submissions/{submission_id}/versions/{version_id}/{kind}"


def _row_matches(row: dict, *, search: str | None, section: str | None, status: str | None, student: str | None, requirement: str | None, date_from: date | None, date_to: date | None) -> bool:
    # The quick search is intentionally limited to the archive identity:
    # group id/code and student registration number. Use the dedicated fields
    # below for requirements, sections, statuses, and dates.
    values = " ".join(str(row.get(key) or "") for key in ("group_id", "group_code", "group_name", "registration_number")).casefold()
    if search and search.casefold() not in values:
        return False
    if section and section.casefold() not in str(row.get("requirement_section") or "").casefold():
        return False
    if status and row.get("current_status") != status.upper():
        return False
    student_value = " ".join(str(row.get(key) or "") for key in ("student_name", "registration_number", "uploader_name")).casefold()
    if student and student.casefold() not in student_value:
        return False
    if requirement and requirement.casefold() not in str(row.get("requirement_name") or "").casefold():
        return False
    submitted_at = row.get("submitted_at")
    if date_from and (submitted_at is None or submitted_at.date() < date_from):
        return False
    if date_to and (submitted_at is None or submitted_at.date() > date_to):
        return False
    return True


def _group_summary(db: Session, cycle: AcademicCycle, group: Team, requirements: list[DocumentUploadRequirement], submissions: list[DocumentSubmission]) -> dict:
    members = _members(db, group.id, cycle.id)
    project = _project(db, group)
    assignment = db.scalar(select(SupervisorAssignment).where(SupervisorAssignment.team_id == group.id, SupervisorAssignment.academic_cycle_id == cycle.id, SupervisorAssignment.ended_at.is_(None)).order_by(SupervisorAssignment.id.desc()).limit(1))
    supervisor = db.get(User, assignment.supervisor_id) if assignment else None
    versions = db.scalars(select(DocumentSubmissionVersion).where(DocumentSubmissionVersion.submission_id.in_([row.id for row in submissions]))).all() if submissions else []
    versions_by_submission: dict[int, list[DocumentSubmissionVersion]] = defaultdict(list)
    for version in versions:
        versions_by_submission[version.submission_id].append(version)
    required = [item for item in requirements if item.is_required and item.status in ARCHIVE_REQUIREMENT_STATUSES]
    submitted_requirement_ids = {row.requirement_id for row in submissions if row.status not in {"DRAFT"}}
    completion = round(len(submitted_requirement_ids & {item.id for item in required}) * 100 / len(required)) if required else 0
    latest_submission = max((version.uploaded_at for version in versions), default=None)
    return {
        "id": group.id,
        "group_id": group.id,
        "group_code": _group_code(cycle, group),
        "group_name": _group_name(group, members),
        "cycle_id": cycle.id,
        "cycle_name": cycle.display_name,
        "project": {"id": project.id, "title": project.title or f"Project {project.id}", "status": project.status, "updated_at": project.updated_at} if project else None,
        "project_id": project.id if project else None,
        "project_title": project.title if project else None,
        "members": [{"id": member.id, "name": member.full_name, "registration_number": member.registration_number, "email": member.university_email, "designation": "Leader" if member.is_creator else "Member"} for member in members],
        "supervisor": _user(supervisor),
        "completion_percentage": completion,
        "last_submission_at": latest_submission,
        "requirement_count": len(requirements),
        "submitted_requirement_count": len(submitted_requirement_ids),
        "status": group.status.upper(),
    }


def _archive_rows(db: Session, cycle: AcademicCycle, group: Team, requirements: list[DocumentUploadRequirement], submissions: list[DocumentSubmission]) -> list[dict]:
    members = _members(db, group.id, cycle.id)
    group_name = _group_name(group, members)
    submission_by_requirement: dict[int, DocumentSubmission] = {}
    for submission in sorted(submissions, key=lambda item: (item.updated_at, item.id), reverse=True):
        submission_by_requirement.setdefault(submission.requirement_id, submission)
    students = {user.id: user for user in db.scalars(select(User).where(User.id.in_([row.student_id for row in submissions] + [row.uploaded_by_id for row in submissions if row.uploaded_by_id]))).all()} if submissions else {}
    versions = db.scalars(select(DocumentSubmissionVersion).where(DocumentSubmissionVersion.submission_id.in_([row.id for row in submissions])).order_by(DocumentSubmissionVersion.version_number)).all() if submissions else []
    versions_by_submission: dict[int, list[DocumentSubmissionVersion]] = defaultdict(list)
    for version in versions:
        versions_by_submission[version.submission_id].append(version)
    review_events = db.scalars(select(DocumentSubmissionReviewEvent).where(DocumentSubmissionReviewEvent.submission_id.in_([row.id for row in submissions])).order_by(DocumentSubmissionReviewEvent.created_at)).all() if submissions else []
    events_by_submission: dict[int, list[DocumentSubmissionReviewEvent]] = defaultdict(list)
    for event in review_events:
        events_by_submission[event.submission_id].append(event)
    reviewer_ids = {event.reviewer_id for event in review_events}
    reviewers = {user.id: user for user in db.scalars(select(User).where(User.id.in_(reviewer_ids))).all()} if reviewer_ids else {}
    reviewers.update({user.id: user for user in db.scalars(select(User).where(User.id.in_([row.reviewed_by_id for row in submissions if row.reviewed_by_id]))).all()} if submissions else {})
    project = _project(db, group)
    project_ids = {submission.project_id for submission in submissions if submission.project_id is not None}
    projects = {item.id: item for item in db.scalars(select(SupervisorRequest).where(SupervisorRequest.id.in_(project_ids))).all()} if project_ids else {}
    rows = []
    for requirement in requirements:
        submission = submission_by_requirement.get(requirement.id)
        submission_versions = versions_by_submission.get(submission.id, []) if submission else []
        latest = submission_versions[-1] if submission_versions else None
        student = students.get(submission.student_id) if submission else None
        uploader = students.get(submission.uploaded_by_id) if submission and submission.uploaded_by_id else None
        reviewer = reviewers.get(submission.reviewed_by_id) if submission and submission.reviewed_by_id else None
        row_project = projects.get(submission.project_id) if submission and submission.project_id is not None else project
        history = [{"id": event.id, "status": _status(requirement, type("ReviewState", (), {"status": event.status})()), "reviewer": _user(reviewers.get(event.reviewer_id)), "reviewed_at": event.created_at, "comment": event.comment, "version_id": event.version_id} for event in events_by_submission.get(submission.id, [])] if submission else []
        rows.append({
            "id": requirement.id,
            "cycle_id": cycle.id,
            "cycle_name": cycle.display_name,
            "group_id": group.id,
            "group_code": _group_code(cycle, group),
            "group_name": group_name,
            "project_id": submission.project_id if submission else (project.id if project else None),
            "project_title": row_project.title if row_project else None,
            "requirement_section_id": requirement.section_id,
            "requirement_section": _section(db, requirement)["name"],
            "requirement_id": requirement.id,
            "requirement_name": requirement.title,
            "student_id": student.id if student else (submission.student_id if submission else None),
            "student_name": student.full_name if student else None,
            "registration_number": student.registration_number if student else None,
            "uploader_id": uploader.id if uploader else (submission.uploaded_by_id if submission else None),
            "uploader_name": uploader.full_name if uploader else None,
            "submission_id": submission.id if submission else None,
            "submitted_file_name": latest.original_filename if latest else None,
            "submitted_at": latest.uploaded_at if latest else None,
            "version_number": latest.version_number if latest else None,
            "current_status": _status(requirement, submission),
            "reviewer": _user(reviewer),
            "reviewer_name": reviewer.full_name if reviewer else None,
            "reviewed_at": submission.reviewed_at if submission else None,
            "reviewer_comments": submission.review_comment if submission else None,
            "latest_version_id": latest.id if latest else None,
            "view_url": _version_url(submission.id, latest.id, "preview") if submission and latest else None,
            "download_url": _version_url(submission.id, latest.id, "download") if submission and latest else None,
            "versions": [{"id": version.id, "version_number": version.version_number, "original_filename": version.original_filename, "mime_type": version.mime_type, "file_size": version.file_size, "uploaded_at": version.uploaded_at, "uploaded_by_id": version.uploaded_by_id, "view_url": _version_url(submission.id, version.id, "preview"), "download_url": _version_url(submission.id, version.id, "download")} for version in submission_versions] if submission else [],
            "review_history": history,
            "requirement_status": requirement.status,
            "is_required": requirement.is_required,
            "due_at": requirement.due_at,
        })
    return rows


def _group_archive(db: Session, cycle: AcademicCycle, group: Team, *, search: str | None = None, section: str | None = None, status: str | None = None, student: str | None = None, requirement: str | None = None, date_from: date | None = None, date_to: date | None = None) -> dict:
    members = _members(db, group.id, cycle.id)
    member_ids = [user.id for user in db.scalars(select(User).where(or_(User.registration_number.in_([member.registration_number for member in members]), User.email.in_([member.university_email for member in members])))).all()] if members else []
    assignment_filter = or_(DocumentUploadRequirement.assigned_user_id.is_(None), DocumentUploadRequirement.assigned_user_id.in_(member_ids)) if member_ids else DocumentUploadRequirement.assigned_user_id.is_(None)
    requirements = db.scalars(select(DocumentUploadRequirement).where(DocumentUploadRequirement.academic_cycle_id == cycle.id, or_(DocumentUploadRequirement.assigned_group_id.is_(None), DocumentUploadRequirement.assigned_group_id == group.id), assignment_filter, DocumentUploadRequirement.status.in_(SECTION_STATUS_FOR_ARCHIVE))).all()
    submissions = db.scalars(select(DocumentSubmission).where(DocumentSubmission.academic_cycle_id == cycle.id, DocumentSubmission.group_id == group.id, DocumentSubmission.project_id.is_not(None), DocumentSubmission.requirement_section_id.is_not(None), DocumentSubmission.requirement_id.in_([item.id for item in requirements]))).all() if requirements else []
    summary = _group_summary(db, cycle, group, requirements, submissions)
    rows = _archive_rows(db, cycle, group, requirements, submissions)
    rows = [row for row in rows if _row_matches(row, search=search, section=section, status=status, student=student, requirement=requirement, date_from=date_from, date_to=date_to)]
    return {**summary, "requirements": rows, "total_requirements": len(requirements), "filtered_requirements": len(rows), "member_user_ids": member_ids}


SECTION_STATUS_FOR_ARCHIVE = {"DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED", "ACTIVE"}


def _group_matches_archive(archive: dict, *, search: str | None, section: str | None, status: str | None, student: str | None, requirement: str | None, date_from: date | None, date_to: date | None) -> bool:
    if not any((search, section, status, student, requirement, date_from, date_to)):
        return True
    if search:
        group_values = " ".join([
            str(archive.get("group_id") or ""),
            str(archive.get("group_code") or ""),
            str(archive.get("group_name") or ""),
            " ".join(str(member.get("registration_number") or "") for member in archive.get("members", [])),
        ]).casefold()
        if search.casefold() in group_values:
            return True
    return bool(archive.get("requirements"))


@router.get("/cycles")
def archive_cycles(_: User = Depends(require_roles(*ARCHIVE_ROLES)), db: Session = Depends(get_db)):
    cycles = db.scalars(select(AcademicCycle).order_by(AcademicCycle.id.desc())).all()
    result = []
    for cycle in cycles:
        result.append({"id": cycle.id, "code": cycle.code, "name": cycle.display_name, "display_name": cycle.display_name, "group_count": len(db.scalars(select(Team.id).where(Team.academic_cycle_id == cycle.id, Team.status != "dissolved")).all()), "requirement_count": len(db.scalars(select(DocumentUploadRequirement.id).where(DocumentUploadRequirement.academic_cycle_id == cycle.id)).all()), "submission_count": len(db.scalars(select(DocumentSubmission.id).where(DocumentSubmission.academic_cycle_id == cycle.id)).all())})
    return result


@router.get("/cycles/{cycle_id}/groups")
def archive_groups(cycle_id: int, search: str | None = Query(default=None), section: str | None = Query(default=None), status: str | None = Query(default=None), student: str | None = Query(default=None), requirement: str | None = Query(default=None), date_from: date | None = Query(default=None), date_to: date | None = Query(default=None), _: User = Depends(require_roles(*ARCHIVE_ROLES)), db: Session = Depends(get_db)):
    cycle = _cycle(db, cycle_id)
    groups = db.scalars(select(Team).where(Team.academic_cycle_id == cycle.id, Team.status != "dissolved").order_by(Team.id)).all()
    archives = [_group_archive(db, cycle, group, search=search, section=section, status=status, student=student, requirement=requirement, date_from=date_from, date_to=date_to) for group in groups]
    archives = [archive for archive in archives if _group_matches_archive(archive, search=search, section=section, status=status, student=student, requirement=requirement, date_from=date_from, date_to=date_to)]
    return {"cycle": {"id": cycle.id, "code": cycle.code, "name": cycle.display_name}, "groups": archives}


@router.get("/cycles/{cycle_id}/groups/{group_id}")
def archive_group(cycle_id: int, group_id: int, search: str | None = Query(default=None), section: str | None = Query(default=None), status: str | None = Query(default=None), student: str | None = Query(default=None), requirement: str | None = Query(default=None), date_from: date | None = Query(default=None), date_to: date | None = Query(default=None), _: User = Depends(require_roles(*ARCHIVE_ROLES)), db: Session = Depends(get_db)):
    cycle = _cycle(db, cycle_id)
    group = db.get(Team, group_id)
    if group is None or group.academic_cycle_id != cycle.id or group.status == "dissolved":
        raise HTTPException(404, "Group was not found in the selected academic cycle.")
    return {"cycle": {"id": cycle.id, "code": cycle.code, "name": cycle.display_name}, "group": _group_archive(db, cycle, group, search=search, section=section, status=status, student=student, requirement=requirement, date_from=date_from, date_to=date_to)}


@router.get("/review-queue")
def archive_review_queue(cycle_id: int | None = Query(default=None), _: User = Depends(require_roles(*ARCHIVE_ROLES)), db: Session = Depends(get_db)):
    rows = db.scalars(select(DocumentArchiveReviewQueue).where(DocumentArchiveReviewQueue.status == "OPEN").order_by(DocumentArchiveReviewQueue.created_at)).all()
    if cycle_id is not None:
        rows = [row for row in rows if (row.snapshot or {}).get("cycle_id") == cycle_id]
    return [{"id": row.id, "submission_id": row.submission_id, "reason": row.reason, "snapshot": row.snapshot, "status": row.status, "created_at": row.created_at} for row in rows]
