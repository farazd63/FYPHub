"""Administrator-controlled supervisor departure and group reassignment workflow."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import require_roles, utc_now, validate_mutating_origin
from .database import get_db
from .models import (
    AcademicCycle,
    AdminAuditEvent,
    CollaborationChannel,
    Module2Notification,
    ProjectMilestone,
    ProjectTask,
    ProposalComplianceSubmission,
    SupervisorAssignment,
    SupervisorAvailability,
    SupervisorCapacityPolicy,
    SupervisorDeparture,
    SupervisorProfile,
    SupervisorReplacementCase,
    Team,
    TeamMember,
    User,
    UserRole,
)
from .schemas.supervisor_replacement import DepartureRestoreWrite, DepartureWrite, ReplacementAssignWrite, ReplacementCompleteWrite
from .supervisor_matching import _ai_rank_candidates, rank_supervisors_for_fields

router = APIRouter(prefix="/api/v1/admin/supervisor-replacements", tags=["supervisor-replacement"])
OPEN_REPLACEMENT_STATUSES = ("UNSUPERVISED", "REPLACEMENT_PENDING", "REASSIGNED")


def _failure(code: str, message: str, status_code: int = 409) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _progress(session: Session, team_id: int) -> dict:
    milestones = session.scalars(select(ProjectMilestone).where(ProjectMilestone.team_id == team_id).order_by(ProjectMilestone.due_at, ProjectMilestone.id)).all()
    tasks = session.scalars(select(ProjectTask).where(ProjectTask.team_id == team_id).order_by(ProjectTask.due_at, ProjectTask.id)).all()
    items = [*milestones, *tasks]
    overdue = sum(1 for item in items if item.due_at and item.due_at < utc_now() and item.completion_percent < 100)
    average = round(sum(item.completion_percent for item in items) / len(items)) if items else 0
    health = "Critical" if overdue >= 3 else "Attention Required" if overdue or any(item.completion_percent < 50 for item in milestones) else "On Track"
    return {"health": health, "average_completion_percent": average, "overdue_items": overdue, "milestones": [{"id": item.id, "title": item.title, "completion_percent": item.completion_percent, "due_at": item.due_at} for item in milestones], "tasks": [{"id": item.id, "title": item.title, "completion_percent": item.completion_percent, "due_at": item.due_at} for item in tasks]}


def _group_members(session: Session, team: Team) -> list[dict]:
    rows = session.scalars(select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.academic_cycle_id == team.academic_cycle_id).order_by(TeamMember.is_creator.desc(), TeamMember.id)).all()
    return [{"id": row.id, "name": row.full_name, "registration_number": row.registration_number, "email": row.university_email, "designation": "LEADER" if row.is_creator else "MEMBER", "is_active": row.is_active} for row in rows]


def _student_recipient_ids(session: Session, team: Team) -> set[int]:
    recipients = {team.shared_user_id}
    members = session.scalars(select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True))).all()
    for member in members:
        user = session.scalar(select(User).where(User.role == UserRole.STUDENT, or_(User.registration_number == member.registration_number, User.email == member.university_email)).limit(1))
        if user is not None:
            recipients.add(user.id)
    return recipients


def _notify(session: Session, recipients: set[int], *, kind: str, payload: dict) -> None:
    for user_id in recipients:
        session.add(Module2Notification(recipient_user_id=user_id, kind=kind, payload=payload))


def _case_detail(session: Session, case: SupervisorReplacementCase) -> dict:
    team = session.get(Team, case.team_id)
    cycle = session.get(AcademicCycle, case.academic_cycle_id)
    previous = session.get(User, case.previous_supervisor_id)
    replacement = session.get(User, case.replacement_supervisor_id) if case.replacement_supervisor_id else None
    members = _group_members(session, team) if team else []
    submission = session.scalar(select(ProposalComplianceSubmission).where(ProposalComplianceSubmission.team_id == case.team_id, ProposalComplianceSubmission.status != "WITHDRAWN").order_by(desc(ProposalComplianceSubmission.version), desc(ProposalComplianceSubmission.id)).limit(1))
    assignment_history = session.scalars(select(SupervisorAssignment).where(SupervisorAssignment.team_id == case.team_id).order_by(SupervisorAssignment.created_at, SupervisorAssignment.id)).all()
    return {
        "id": case.id,
        "status": case.status,
        "reason": case.reason,
        "notes": case.notes,
        "opened_at": case.opened_at,
        "reassigned_at": case.reassigned_at,
        "completed_at": case.completed_at,
        "group": {"id": team.id, "name": f"Group {team.group_number or team.id}", "group_number": team.group_number, "status": team.status, "supervision_status": team.supervision_status, "academic_cycle_id": team.academic_cycle_id, "academic_cycle": cycle.display_name if cycle else None, "academic_cycle_code": cycle.code if cycle else None, "academic_year": cycle.academic_year if cycle else None, "session": cycle.session if cycle else None, "members": members} if team else None,
        "project": {"title": submission.title, "submission_id": submission.id, "version": submission.version, "status": submission.status, "filename": submission.filename, "uploaded_at": submission.created_at, "extracted_fields": submission.extracted_fields or {}} if submission else None,
        "previous_supervisor": {"id": previous.id, "name": previous.full_name, "email": previous.email} if previous else None,
        "replacement_supervisor": {"id": replacement.id, "name": replacement.full_name, "email": replacement.email} if replacement else None,
        "progress": _progress(session, case.team_id),
        "assignment_history": [{"id": row.id, "supervisor_id": row.supervisor_id, "assigned_by_id": row.assigned_by_id, "started_at": row.created_at, "ended_at": row.ended_at, "end_reason": row.end_reason, "end_notes": row.end_notes} for row in assignment_history],
    }


def _case_list_item(session: Session, case: SupervisorReplacementCase) -> dict:
    detail = _case_detail(session, case)
    return {"id": case.id, "status": case.status, "reason": case.reason, "opened_at": case.opened_at, "group": detail["group"], "project_title": detail["project"]["title"] if detail["project"] else None, "previous_supervisor": detail["previous_supervisor"]}


def _ensure_replacement_capacity(session: Session, supervisor: User, cycle: AcademicCycle) -> dict:
    profile = session.scalar(select(SupervisorProfile).where(SupervisorProfile.supervisor_id == supervisor.id).limit(1))
    availability = session.scalar(select(SupervisorAvailability).where(SupervisorAvailability.profile_id == profile.id, SupervisorAvailability.academic_cycle_id == cycle.id).limit(1)) if profile else None
    if availability is not None and not availability.available:
        raise _failure("capacity_unavailable", "The selected supervisor is not accepting new supervision requests.", 409)
    active_groups = session.scalar(select(func.count(SupervisorAssignment.id)).where(SupervisorAssignment.supervisor_id == supervisor.id, SupervisorAssignment.ended_at.is_(None), SupervisorAssignment.academic_year == cycle.academic_year)) or 0
    policy = session.scalar(select(SupervisorCapacityPolicy).where(SupervisorCapacityPolicy.supervisor_id == supervisor.id, or_(SupervisorCapacityPolicy.academic_cycle_id == cycle.id, SupervisorCapacityPolicy.academic_year == cycle.academic_year)).order_by(SupervisorCapacityPolicy.academic_cycle_id.desc().nullslast()).limit(1))
    limit = policy.max_group_capacity if policy else availability.maximum_capacity if availability and availability.maximum_capacity > 0 else None
    if limit is not None and active_groups >= limit:
        raise _failure("capacity_full", "The selected supervisor has no remaining capacity for this cycle.", 409)
    return {"active_groups": active_groups, "capacity_limit": limit, "remaining_capacity": max(limit - active_groups, 0) if limit is not None else None}


@router.get("/supervisors")
def replacement_supervisors(_: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> list[dict]:
    rows = session.scalars(select(User).where(User.role == UserRole.SUPERVISOR).order_by(User.full_name, User.id)).all()
    output = []
    for supervisor in rows:
        groups = session.scalar(select(func.count(SupervisorAssignment.id)).where(SupervisorAssignment.supervisor_id == supervisor.id, SupervisorAssignment.ended_at.is_(None))) or 0
        departure = session.scalar(select(SupervisorDeparture).where(SupervisorDeparture.supervisor_id == supervisor.id, SupervisorDeparture.active.is_(True)).limit(1))
        output.append({"id": supervisor.id, "name": supervisor.full_name, "email": supervisor.email, "is_active": supervisor.is_active, "active_groups": groups, "departure": {"reason": departure.reason, "notes": departure.notes, "marked_at": departure.marked_at} if departure else None})
    return output


@router.post("/supervisors/{supervisor_id}/mark-unavailable")
def mark_unavailable(supervisor_id: int, payload: DepartureWrite, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> dict:
    validate_mutating_origin(request)
    supervisor = session.get(User, supervisor_id)
    if supervisor is None or supervisor.role != UserRole.SUPERVISOR:
        raise _failure("supervisor_not_found", "Supervisor was not found.", 404)
    departure = session.scalar(select(SupervisorDeparture).where(SupervisorDeparture.supervisor_id == supervisor.id, SupervisorDeparture.active.is_(True)).with_for_update().limit(1))
    if departure is None:
        departure = SupervisorDeparture(supervisor_id=supervisor.id, reason=payload.reason, notes=payload.notes, marked_by_id=actor.id)
        session.add(departure)
    else:
        departure.reason, departure.notes, departure.marked_by_id, departure.marked_at = payload.reason, payload.notes, actor.id, utc_now()
    assignments = session.scalars(select(SupervisorAssignment).where(SupervisorAssignment.supervisor_id == supervisor.id, SupervisorAssignment.ended_at.is_(None)).with_for_update()).all()
    created_cases = []
    for assignment in assignments:
        team = session.get(Team, assignment.team_id, with_for_update=True)
        if team is None or team.status == "dissolved":
            continue
        assignment.ended_at, assignment.ended_by_id, assignment.end_reason, assignment.end_notes = utc_now(), actor.id, payload.reason, payload.notes
        team.supervision_status = "UNSUPERVISED"
        for channel in session.scalars(select(CollaborationChannel).where(CollaborationChannel.team_id == team.id, CollaborationChannel.status == "ACTIVE")).all():
            channel.status = "ARCHIVED"
        existing = session.scalar(select(SupervisorReplacementCase).where(SupervisorReplacementCase.team_id == team.id, SupervisorReplacementCase.status.in_(["UNSUPERVISED", "REPLACEMENT_PENDING"])).limit(1))
        if existing is None:
            existing = SupervisorReplacementCase(team_id=team.id, academic_cycle_id=assignment.academic_cycle_id, previous_assignment_id=assignment.id, previous_supervisor_id=supervisor.id, status="UNSUPERVISED", reason=payload.reason, notes=payload.notes, opened_by_id=actor.id)
            session.add(existing)
            session.flush()
            created_cases.append(existing)
        session.add(AdminAuditEvent(actor_id=actor.id, affected_user_id=supervisor.id, target_type="SUPERVISOR_REPLACEMENT", target_id=existing.id, action="supervisor_departure_recorded", changed_values={"team_id": team.id, "reason": payload.reason, "previous_supervisor_id": supervisor.id}))
    session.commit()
    return {"supervisor_id": supervisor.id, "reason": departure.reason, "affected_groups": [_case_list_item(session, case) for case in created_cases], "message": f"{len(created_cases)} group(s) moved to the unsupervised replacement workflow."}


@router.post("/supervisors/{supervisor_id}/restore")
def restore_supervisor(supervisor_id: int, payload: DepartureRestoreWrite, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> dict:
    """Undo an accidental departure without rewriting assignment history."""

    validate_mutating_origin(request)
    supervisor = session.get(User, supervisor_id)
    if supervisor is None or supervisor.role != UserRole.SUPERVISOR:
        raise _failure("supervisor_not_found", "Supervisor was not found.", 404)
    departure = session.scalar(
        select(SupervisorDeparture)
        .where(SupervisorDeparture.supervisor_id == supervisor.id, SupervisorDeparture.active.is_(True))
        .with_for_update()
        .limit(1)
    )
    if departure is None:
        return {"supervisor_id": supervisor.id, "restored": False, "affected_cases": [], "message": "This supervisor is already available."}

    departure.active = False
    departure.resolved_at = utc_now()
    departure.resolved_by_id = actor.id
    if payload.notes:
        departure.notes = f"{departure.notes}\nRestore note: {payload.notes}" if departure.notes else f"Restore note: {payload.notes}"

    cases = session.scalars(
        select(SupervisorReplacementCase)
        .where(
            SupervisorReplacementCase.previous_supervisor_id == supervisor.id,
            SupervisorReplacementCase.status.in_(["UNSUPERVISED", "REPLACEMENT_PENDING"]),
        )
        .order_by(SupervisorReplacementCase.id)
    ).all()
    _notify(
        session,
        {supervisor.id},
        kind="SUPERVISOR_DEPARTURE_RESTORED",
        payload={"supervisor_id": supervisor.id, "path": "/supervisor/assigned-groups", "message": "An administrator restored your supervisor availability."},
    )
    session.add(
        AdminAuditEvent(
            actor_id=actor.id,
            affected_user_id=supervisor.id,
            target_type="SUPERVISOR_REPLACEMENT",
            target_id=departure.id,
            action="supervisor_departure_restored",
            changed_values={"supervisor_id": supervisor.id, "previous_reason": departure.reason, "notes": payload.notes},
        )
    )
    session.commit()
    return {
        "supervisor_id": supervisor.id,
        "restored": True,
        "affected_cases": [{"id": case.id, "team_id": case.team_id, "status": case.status} for case in cases],
        "message": "Supervisor restored. Select the previous supervisor in an affected case to assign them back.",
    }


@router.get("/cases")
def replacement_cases(status_filter: str | None = Query(default=None, alias="status"), _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> list[dict]:
    statement = select(SupervisorReplacementCase).order_by(SupervisorReplacementCase.opened_at.desc(), SupervisorReplacementCase.id.desc())
    if status_filter:
        statement = statement.where(SupervisorReplacementCase.status == status_filter.upper())
    else:
        statement = statement.where(SupervisorReplacementCase.status.in_(OPEN_REPLACEMENT_STATUSES))
    return [_case_list_item(session, case) for case in session.scalars(statement).all()]


@router.get("/cases/{case_id}")
def replacement_case(case_id: int, _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> dict:
    case = session.get(SupervisorReplacementCase, case_id)
    if case is None:
        raise _failure("replacement_case_not_found", "Replacement case was not found.", 404)
    return _case_detail(session, case)


@router.post("/cases/{case_id}/recommendations")
async def replacement_recommendations(case_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> dict:
    validate_mutating_origin(request)
    case = session.get(SupervisorReplacementCase, case_id, with_for_update=True)
    if case is None:
        raise _failure("replacement_case_not_found", "Replacement case was not found.", 404)
    if case.status in {"REASSIGNED", "COMPLETED"}:
        raise _failure("replacement_case_closed", "This replacement case has already been reassigned or completed.", 409)
    detail = _case_detail(session, case)
    fields = (detail.get("project") or {}).get("extracted_fields") or {}
    if not fields:
        fields = {"title": detail.get("project", {}).get("title", "") if detail.get("project") else "", "research_domain": [], "required_skills": [], "methodology": "", "keywords": []}
    case.status = "REPLACEMENT_PENDING"
    team = session.get(Team, case.team_id)
    if team:
        team.supervision_status = "REPLACEMENT_PENDING"
    session.commit()
    candidates = rank_supervisors_for_fields(session, session.get(AcademicCycle, case.academic_cycle_id), fields, excluded_supervisor_ids={case.previous_supervisor_id}, limit=30)
    ranked, ranking_meta = await _ai_rank_candidates(candidates, fields, rate_key=f"supervisor-matching-replacement:{actor.id}", limit=10)
    return {"case_id": case.id, "status": case.status, **ranking_meta, "results": ranked}


@router.post("/cases/{case_id}/reassign")
def reassign(case_id: int, payload: ReplacementAssignWrite, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> dict:
    validate_mutating_origin(request)
    case = session.get(SupervisorReplacementCase, case_id, with_for_update=True)
    if case is None:
        raise _failure("replacement_case_not_found", "Replacement case was not found.", 404)
    if case.status in {"REASSIGNED", "COMPLETED"}:
        raise _failure("replacement_case_closed", "This replacement case has already been resolved.", 409)
    team = session.get(Team, case.team_id, with_for_update=True)
    cycle = session.get(AcademicCycle, case.academic_cycle_id)
    supervisor = session.get(User, payload.supervisor_id)
    if team is None or cycle is None:
        raise _failure("replacement_case_invalid", "The group or academic cycle no longer exists.", 409)
    if supervisor is None or supervisor.role != UserRole.SUPERVISOR or not supervisor.is_active:
        raise _failure("supervisor_unavailable", "Choose an active supervisor.", 422)
    if session.scalar(select(SupervisorDeparture.id).where(SupervisorDeparture.supervisor_id == supervisor.id, SupervisorDeparture.active.is_(True)).limit(1)) is not None:
        raise _failure("supervisor_unavailable", "The selected supervisor is marked unavailable.", 409)
    if session.scalar(select(SupervisorAssignment.id).where(SupervisorAssignment.team_id == team.id, SupervisorAssignment.ended_at.is_(None)).limit(1)) is not None:
        raise _failure("team_already_assigned", "This group already has an active supervisor.", 409)
    workload = _ensure_replacement_capacity(session, supervisor, cycle)
    assignment = SupervisorAssignment(team_id=team.id, academic_cycle_id=cycle.id, supervisor_id=supervisor.id, academic_year=cycle.academic_year, session=cycle.session, assigned_by_id=actor.id)
    session.add(assignment)
    session.flush()
    team.supervision_status = "REASSIGNED"
    case.replacement_assignment_id, case.replacement_supervisor_id, case.assigned_by_id, case.reassigned_at, case.status = assignment.id, supervisor.id, actor.id, utc_now(), "REASSIGNED"
    if payload.notes:
        case.notes = f"{case.notes}\n{payload.notes}" if case.notes else payload.notes
    from .collaboration_channels import ensure_collaboration_channel
    ensure_collaboration_channel(session, assignment, team)
    assignment_payload = {"case_id": case.id, "team_id": team.id, "previous_supervisor_id": case.previous_supervisor_id, "new_supervisor_id": supervisor.id, "reason": case.reason, "message": "An administrator reassigned your supervision."}
    if case.previous_supervisor_id == supervisor.id:
        _notify(session, {supervisor.id}, kind="SUPERVISOR_REASSIGNED", payload={**assignment_payload, "path": "/supervisor/assigned-groups"})
    else:
        _notify(session, {case.previous_supervisor_id}, kind="SUPERVISOR_REASSIGNED", payload={**assignment_payload, "path": "/supervisor/assigned-groups"})
        _notify(session, {supervisor.id}, kind="SUPERVISOR_REASSIGNED", payload={**assignment_payload, "path": f"/supervisor/groups/{team.id}?tab=overview"})
    _notify(session, _student_recipient_ids(session, team), kind="SUPERVISOR_REASSIGNED", payload={**assignment_payload, "path": "/student/supervisor-info"})
    session.add(AdminAuditEvent(actor_id=actor.id, affected_user_id=supervisor.id, target_type="SUPERVISOR_REPLACEMENT", target_id=case.id, action="supervisor_reassigned", changed_values={"team_id": team.id, "previous_supervisor_id": case.previous_supervisor_id, "new_supervisor_id": supervisor.id, "reason": case.reason, "notes": payload.notes}))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise _failure("replacement_conflict", "The supervisor reassignment conflicted with another change.", 409) from error
    return {"case": _case_detail(session, case), "assignment": {"id": assignment.id, "supervisor_id": assignment.supervisor_id, "assigned_by_id": assignment.assigned_by_id, "created_at": assignment.created_at}, "workload": workload}


@router.post("/cases/{case_id}/complete")
def complete_replacement(case_id: int, payload: ReplacementCompleteWrite, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> dict:
    validate_mutating_origin(request)
    case = session.get(SupervisorReplacementCase, case_id, with_for_update=True)
    if case is None:
        raise _failure("replacement_case_not_found", "Replacement case was not found.", 404)
    if case.status != "REASSIGNED":
        raise _failure("replacement_not_reassigned", "Only a reassigned case can be completed.", 409)
    case.status = "COMPLETED"
    case.completed_at, case.completed_by_id = utc_now(), actor.id
    if payload.notes:
        case.notes = f"{case.notes}\n{payload.notes}" if case.notes else payload.notes
    team = session.get(Team, case.team_id)
    if team:
        team.supervision_status = "COMPLETED"
    session.add(AdminAuditEvent(actor_id=actor.id, affected_user_id=case.replacement_supervisor_id, target_type="SUPERVISOR_REPLACEMENT", target_id=case.id, action="supervisor_replacement_completed", changed_values={"team_id": case.team_id, "notes": payload.notes}))
    session.commit()
    return _case_detail(session, case)
