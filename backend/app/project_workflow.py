"""Authorized, persisted project progress, defense scheduling, and evaluation workflows."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles, utc_now, validate_mutating_origin
from .database import get_db
from .models import (
    AcademicCycle,
    DefensePanelMember,
    DefenseSchedule,
    PanelEvaluation,
    PanelEvaluationScore,
    ProjectMilestone,
    ProjectTask,
    SupervisorAssignment,
    SupervisionMeeting,
    Team,
    TeamMember,
    User,
    UserRole,
)
from .schemas.project_workflow import EvaluationWrite, MeetingWrite, MilestoneWrite, ResolutionWrite, ScheduleReschedule, ScheduleWrite, TaskWrite

router = APIRouter(prefix="/api/v1")
WRITE_ROLES = (UserRole.STUDENT, UserRole.SUPERVISOR, UserRole.COORDINATOR, UserRole.ADMIN)
READ_ROLES = WRITE_ROLES + (UserRole.PANEL_MEMBER,)


def failure(code: str, message: str, code_status: int = status.HTTP_409_CONFLICT) -> HTTPException:
    return HTTPException(code_status, detail={"code": code, "message": message})


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _team(session: Session, team_id: int) -> Team:
    team = session.get(Team, team_id)
    if team is None:
        raise failure("team_not_found", "Team was not found.", status.HTTP_404_NOT_FOUND)
    return team


def _is_team_member(session: Session, team: Team, user: User) -> bool:
    if team.shared_user_id == user.id:
        return True
    if user.role != UserRole.STUDENT:
        return False
    if not user.registration_number:
        return False
    return session.scalar(
        select(TeamMember.id).where(
            TeamMember.team_id == team.id,
            TeamMember.academic_cycle_id == team.academic_cycle_id,
            TeamMember.registration_number == user.registration_number,
            TeamMember.is_active.is_(True),
        )
    ) is not None


def _assigned_supervisor(session: Session, team_id: int) -> SupervisorAssignment | None:
    return session.scalar(select(SupervisorAssignment).where(SupervisorAssignment.team_id == team_id, SupervisorAssignment.ended_at.is_(None)))


def _can_access_team(session: Session, team: Team, user: User, *, write: bool = False) -> bool:
    if user.role in (UserRole.ADMIN, UserRole.COORDINATOR):
        return True
    assignment = _assigned_supervisor(session, team.id)
    if user.role == UserRole.SUPERVISOR:
        return assignment is not None and assignment.supervisor_id == user.id
    return _is_team_member(session, team, user)


def _require_team_access(session: Session, team_id: int, user: User, *, write: bool = False) -> Team:
    team = _team(session, team_id)
    if not _can_access_team(session, team, user, write=write):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You are not authorized to access this team.")
    return team


def _audit(session: Session, actor: User, action: str, target_type: str, target_id: int, values: dict) -> None:
    from .main import add_admin_audit_event

    add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type=target_type, target_id=target_id, action=action, changed_values=values)


def _milestone_out(row: ProjectMilestone) -> dict:
    return {"id": row.id, "team_id": row.team_id, "title": row.title, "description": row.description, "due_at": row.due_at, "completion_percent": row.completion_percent, "overdue": bool(row.due_at and row.due_at < utc_now() and row.completion_percent < 100), "created_at": row.created_at, "updated_at": row.updated_at}


def _task_out(row: ProjectTask) -> dict:
    return {"id": row.id, "team_id": row.team_id, "milestone_id": row.milestone_id, "owner_user_id": row.owner_user_id, "title": row.title, "description": row.description, "due_at": row.due_at, "completion_percent": row.completion_percent, "overdue": bool(row.due_at and row.due_at < utc_now() and row.completion_percent < 100), "created_at": row.created_at, "updated_at": row.updated_at}


def _health(milestones: list[ProjectMilestone], tasks: list[ProjectTask]) -> str:
    overdue = sum(1 for row in [*milestones, *tasks] if row.due_at and row.due_at < utc_now() and row.completion_percent < 100)
    if overdue >= 3:
        return "Critical"
    if overdue or any(row.completion_percent < 50 for row in milestones):
        return "Attention Required"
    return "On Track"


@router.get("/project-progress/{team_id}")
def project_progress(team_id: int, user: User = Depends(require_roles(*READ_ROLES)), session: Session = Depends(get_db)) -> dict:
    team = _require_team_access(session, team_id, user)
    milestones = session.scalars(select(ProjectMilestone).where(ProjectMilestone.team_id == team.id).order_by(ProjectMilestone.due_at, ProjectMilestone.id)).all()
    tasks = session.scalars(select(ProjectTask).where(ProjectTask.team_id == team.id).order_by(ProjectTask.due_at, ProjectTask.id)).all()
    meetings = session.scalars(select(SupervisionMeeting).where(SupervisionMeeting.team_id == team.id).order_by(SupervisionMeeting.held_at.desc(), SupervisionMeeting.id.desc())).all()
    return {"team_id": team.id, "health": _health(milestones, tasks), "milestones": [_milestone_out(row) for row in milestones], "tasks": [_task_out(row) for row in tasks], "meetings": [{"id": row.id, "held_at": row.held_at, "minutes": row.minutes, "decisions": row.decisions, "action_items": row.action_items, "supervisor_id": row.supervisor_id, "created_by_id": row.created_by_id, "created_at": row.created_at} for row in meetings]}


@router.post("/project-progress/{team_id}/milestones", status_code=201)
def create_milestone(team_id: int, payload: MilestoneWrite, request: Request, actor: User = Depends(require_roles(*WRITE_ROLES)), session: Session = Depends(get_db)) -> dict:
    validate_mutating_origin(request)
    team = _require_team_access(session, team_id, actor, write=True)
    row = ProjectMilestone(team_id=team.id, created_by_id=actor.id, **payload.model_dump())
    session.add(row); session.flush(); _audit(session, actor, "project_milestone_created", "PROJECT_MILESTONE", row.id, {"team_id": team.id, "title": row.title}); session.commit(); session.refresh(row)
    return _milestone_out(row)


@router.patch("/project-progress/milestones/{milestone_id}")
def update_milestone(milestone_id: int, payload: MilestoneWrite, request: Request, actor: User = Depends(require_roles(*WRITE_ROLES)), session: Session = Depends(get_db)) -> dict:
    validate_mutating_origin(request)
    row = session.get(ProjectMilestone, milestone_id)
    if row is None: raise failure("milestone_not_found", "Milestone was not found.", 404)
    _require_team_access(session, row.team_id, actor, write=True)
    for key, value in payload.model_dump().items(): setattr(row, key, value)
    session.flush(); _audit(session, actor, "project_milestone_updated", "PROJECT_MILESTONE", row.id, {"completion_percent": row.completion_percent, "due_at": row.due_at.isoformat() if row.due_at else None}); session.commit(); session.refresh(row)
    return _milestone_out(row)


@router.post("/project-progress/{team_id}/tasks", status_code=201)
def create_task(team_id: int, payload: TaskWrite, request: Request, actor: User = Depends(require_roles(*WRITE_ROLES)), session: Session = Depends(get_db)) -> dict:
    validate_mutating_origin(request)
    team = _require_team_access(session, team_id, actor, write=True)
    if payload.milestone_id is not None and session.scalar(select(ProjectMilestone.id).where(ProjectMilestone.id == payload.milestone_id, ProjectMilestone.team_id == team.id)) is None:
        raise failure("milestone_not_found", "The selected milestone does not belong to this team.", 422)
    if payload.owner_user_id is not None and not session.scalar(select(TeamMember.id).where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True), or_(TeamMember.registration_number == session.get(User, payload.owner_user_id).registration_number if session.get(User, payload.owner_user_id) else False, TeamMember.university_email == session.get(User, payload.owner_user_id).email if session.get(User, payload.owner_user_id) else False))):
        raise failure("task_owner_not_member", "Task owner must be an active team member.", 422)
    row = ProjectTask(team_id=team.id, created_by_id=actor.id, **payload.model_dump())
    session.add(row); session.flush(); _audit(session, actor, "project_task_created", "PROJECT_TASK", row.id, {"team_id": team.id, "title": row.title}); session.commit(); session.refresh(row)
    return _task_out(row)


@router.patch("/project-progress/tasks/{task_id}")
def update_task(task_id: int, payload: TaskWrite, request: Request, actor: User = Depends(require_roles(*WRITE_ROLES)), session: Session = Depends(get_db)) -> dict:
    validate_mutating_origin(request)
    row = session.get(ProjectTask, task_id)
    if row is None: raise failure("task_not_found", "Task was not found.", 404)
    _require_team_access(session, row.team_id, actor, write=True)
    if payload.milestone_id is not None and session.scalar(select(ProjectMilestone.id).where(ProjectMilestone.id == payload.milestone_id, ProjectMilestone.team_id == row.team_id)) is None:
        raise failure("milestone_not_found", "The selected milestone does not belong to this team.", 422)
    for key, value in payload.model_dump().items(): setattr(row, key, value)
    session.flush(); _audit(session, actor, "project_task_updated", "PROJECT_TASK", row.id, {"completion_percent": row.completion_percent, "due_at": row.due_at.isoformat() if row.due_at else None}); session.commit(); session.refresh(row)
    return _task_out(row)


@router.get("/project-progress/{team_id}/meetings")
def list_meetings(team_id: int, user: User = Depends(require_roles(*READ_ROLES)), session: Session = Depends(get_db)) -> list[dict]:
    team = _require_team_access(session, team_id, user)
    rows = session.scalars(select(SupervisionMeeting).where(SupervisionMeeting.team_id == team.id).order_by(SupervisionMeeting.held_at.desc(), SupervisionMeeting.id.desc())).all()
    return [{"id": row.id, "held_at": row.held_at, "minutes": row.minutes, "decisions": row.decisions, "action_items": row.action_items, "supervisor_id": row.supervisor_id, "created_by_id": row.created_by_id, "created_at": row.created_at} for row in rows]


@router.post("/project-progress/{team_id}/meetings", status_code=201)
def create_meeting(team_id: int, payload: MeetingWrite, request: Request, actor: User = Depends(require_roles(*WRITE_ROLES)), session: Session = Depends(get_db)) -> dict:
    validate_mutating_origin(request)
    team = _require_team_access(session, team_id, actor, write=True)
    assignment = _assigned_supervisor(session, team.id)
    if assignment is None:
        raise failure("supervisor_assignment_required", "An active supervisor assignment is required before recording a meeting.")
    row = SupervisionMeeting(team_id=team.id, supervisor_id=assignment.supervisor_id, created_by_id=actor.id, held_at=_utc(payload.held_at), minutes=payload.minutes, decisions=payload.decisions, action_items=payload.action_items)
    session.add(row); session.flush(); _audit(session, actor, "supervision_meeting_recorded", "SUPERVISION_MEETING", row.id, {"team_id": team.id}); session.commit(); session.refresh(row)
    return {"id": row.id, "held_at": row.held_at, "minutes": row.minutes, "decisions": row.decisions, "action_items": row.action_items, "supervisor_id": row.supervisor_id, "created_by_id": row.created_by_id, "created_at": row.created_at}


def _schedule_out(session: Session, row: DefenseSchedule) -> dict:
    team = session.get(Team, row.team_id)
    members = session.execute(select(DefensePanelMember, User.full_name, User.email).join(User, User.id == DefensePanelMember.user_id).where(DefensePanelMember.schedule_id == row.id).order_by(DefensePanelMember.id)).all()
    assignment = _assigned_supervisor(session, row.team_id)
    return {"id": row.id, "team_id": row.team_id, "academic_cycle_id": row.academic_cycle_id, "start_at": row.start_at, "end_at": row.end_at, "room": row.room, "online_link": row.online_link, "status": row.status, "conflict_note": row.conflict_note, "team_label": f"Team {row.team_id}", "supervisor_id": assignment.supervisor_id if assignment else None, "panel_members": [{"id": item.user_id, "name": name, "email": email} for item, name, email in members], "created_at": row.created_at, "updated_at": row.updated_at}


def _schedule_access(session: Session, row: DefenseSchedule, user: User) -> bool:
    if user.role in (UserRole.ADMIN, UserRole.COORDINATOR): return True
    if user.role == UserRole.PANEL_MEMBER:
        return session.scalar(select(DefensePanelMember.id).where(DefensePanelMember.schedule_id == row.id, DefensePanelMember.user_id == user.id)) is not None
    team = session.get(Team, row.team_id)
    return team is not None and _can_access_team(session, team, user)


def _check_schedule_conflicts(session: Session, payload: ScheduleWrite | ScheduleReschedule, *, schedule_id: int | None = None) -> None:
    start_at, end_at = _utc(payload.start_at), _utc(payload.end_at)
    if end_at <= start_at: raise failure("invalid_schedule_time", "Defense end time must be after the start time.", 422)
    rows = session.scalars(select(DefenseSchedule).where(DefenseSchedule.status != "CANCELLED", DefenseSchedule.start_at < end_at, DefenseSchedule.end_at > start_at, DefenseSchedule.id != schedule_id if schedule_id is not None else True)).all()
    panel_ids = set(payload.panel_member_ids or [])
    for row in rows:
        if isinstance(payload, ScheduleWrite) and row.team_id == payload.team_id: raise failure("student_conflict", "This team already has an overlapping defense schedule.")
        if payload.room and row.room and payload.room.casefold() == row.room.casefold(): raise failure("room_conflict", "The selected room is already booked for this time.")
        assigned_ids = set(session.scalars(select(DefensePanelMember.user_id).where(DefensePanelMember.schedule_id == row.id)).all())
        if panel_ids & assigned_ids: raise failure("panel_conflict", "One or more panel members are already scheduled at this time.")
    if isinstance(payload, ScheduleWrite):
        assignment = _assigned_supervisor(session, payload.team_id)
        if assignment is None: raise failure("supervisor_assignment_required", "A supervisor assignment is required before scheduling a defense.")
        if assignment.supervisor_id in panel_ids: raise failure("conflict_of_interest", "The assigned supervisor cannot serve as a panel member for the same team.")
        members = session.scalars(select(TeamMember).where(TeamMember.team_id == payload.team_id, TeamMember.is_active.is_(True))).all()
        member_user_ids = set(session.scalars(select(User.id).where(or_(*[and_(User.registration_number == member.registration_number, User.email == member.university_email) for member in members]))).all()) if members else set()
        if member_user_ids and panel_ids & member_user_ids:
            raise failure("conflict_of_interest", "A team member cannot serve as a panel member for the same team.")
        if not payload.room and not payload.online_link: raise failure("location_required", "Provide a room or an online defense link.", 422)
    elif not payload.room and not payload.online_link:
        raise failure("location_required", "Provide a room or an online defense link.", 422)


def _validate_panel_members(session: Session, ids: list[int]) -> None:
    if len(set(ids)) != len(ids): raise failure("duplicate_panel_member", "Panel members must be unique.", 422)
    if ids and len(session.scalars(select(User.id).where(User.id.in_(ids), User.role == UserRole.PANEL_MEMBER, User.is_active.is_(True))).all()) != len(ids):
        raise failure("panel_member_invalid", "Every selected panel member must be an active Evaluator account.", 422)


@router.get("/panel-schedules")
def list_schedules(user: User = Depends(require_roles(*READ_ROLES)), academic_cycle_id: int | None = Query(default=None, gt=0), session: Session = Depends(get_db)) -> list[dict]:
    query = select(DefenseSchedule).order_by(DefenseSchedule.start_at, DefenseSchedule.id)
    if academic_cycle_id is not None: query = query.where(DefenseSchedule.academic_cycle_id == academic_cycle_id)
    rows = session.scalars(query).all()
    return [_schedule_out(session, row) for row in rows if _schedule_access(session, row, user)]


@router.get("/panel-schedules/options")
def schedule_options(actor: User = Depends(require_roles(UserRole.ADMIN, UserRole.COORDINATOR)), session: Session = Depends(get_db)) -> dict:
    teams = session.scalars(select(Team).order_by(Team.id)).all()
    evaluators = session.scalars(select(User).where(User.role == UserRole.PANEL_MEMBER, User.is_active.is_(True)).order_by(User.full_name, User.id)).all()
    cycles = session.scalars(select(AcademicCycle).order_by(AcademicCycle.id.desc())).all()
    return {"teams": [{"id": team.id, "academic_cycle_id": team.academic_cycle_id} for team in teams], "evaluators": [{"id": user.id, "name": user.full_name, "email": user.email} for user in evaluators], "cycles": [{"id": cycle.id, "name": cycle.display_name} for cycle in cycles]}


@router.get("/panel-schedules/{schedule_id}")
def schedule_detail(schedule_id: int, user: User = Depends(require_roles(*READ_ROLES)), session: Session = Depends(get_db)) -> dict:
    row = session.get(DefenseSchedule, schedule_id)
    if row is None: raise failure("schedule_not_found", "Defense schedule was not found.", 404)
    if not _schedule_access(session, row, user): raise HTTPException(403, detail="You are not authorized to access this defense schedule.")
    return _schedule_out(session, row)


@router.post("/panel-schedules", status_code=201)
def create_schedule(payload: ScheduleWrite, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN, UserRole.COORDINATOR)), session: Session = Depends(get_db)) -> dict:
    validate_mutating_origin(request)
    team = _team(session, payload.team_id)
    if team.academic_cycle_id != payload.academic_cycle_id: raise failure("cycle_mismatch", "Team does not belong to the selected academic cycle.", 422)
    if session.get(AcademicCycle, payload.academic_cycle_id) is None: raise failure("cycle_not_found", "Academic cycle was not found.", 404)
    _validate_panel_members(session, payload.panel_member_ids); _check_schedule_conflicts(session, payload)
    row = DefenseSchedule(team_id=team.id, academic_cycle_id=payload.academic_cycle_id, created_by_id=actor.id, start_at=_utc(payload.start_at), end_at=_utc(payload.end_at), room=payload.room, online_link=payload.online_link)
    session.add(row); session.flush()
    for user_id in payload.panel_member_ids: session.add(DefensePanelMember(schedule_id=row.id, user_id=user_id, assigned_by_id=actor.id))
    _audit(session, actor, "defense_schedule_created", "DEFENSE_SCHEDULE", row.id, {"team_id": row.team_id, "panel_member_ids": payload.panel_member_ids}); session.commit(); session.refresh(row)
    return _schedule_out(session, row)


@router.patch("/panel-schedules/{schedule_id}")
def reschedule(schedule_id: int, payload: ScheduleReschedule, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN, UserRole.COORDINATOR)), session: Session = Depends(get_db)) -> dict:
    validate_mutating_origin(request)
    row = session.get(DefenseSchedule, schedule_id)
    if row is None: raise failure("schedule_not_found", "Defense schedule was not found.", 404)
    write = ScheduleWrite(team_id=row.team_id, academic_cycle_id=row.academic_cycle_id, panel_member_ids=payload.panel_member_ids or list(session.scalars(select(DefensePanelMember.user_id).where(DefensePanelMember.schedule_id == row.id)).all()), start_at=payload.start_at, end_at=payload.end_at, room=payload.room, online_link=payload.online_link)
    _validate_panel_members(session, write.panel_member_ids); _check_schedule_conflicts(session, write, schedule_id=row.id)
    row.start_at, row.end_at, row.room, row.online_link, row.status = _utc(payload.start_at), _utc(payload.end_at), payload.room, payload.online_link, "RESCHEDULED"
    if payload.panel_member_ids is not None:
        session.query(DefensePanelMember).filter(DefensePanelMember.schedule_id == row.id).delete(synchronize_session=False)
        for user_id in payload.panel_member_ids: session.add(DefensePanelMember(schedule_id=row.id, user_id=user_id, assigned_by_id=actor.id))
    _audit(session, actor, "defense_schedule_rescheduled", "DEFENSE_SCHEDULE", row.id, {"start_at": row.start_at.isoformat(), "end_at": row.end_at.isoformat()}); session.commit(); session.refresh(row)
    return _schedule_out(session, row)


def _evaluation_out(session: Session, row: PanelEvaluation) -> dict:
    scores = session.scalars(select(PanelEvaluationScore).where(PanelEvaluationScore.evaluation_id == row.id).order_by(PanelEvaluationScore.id)).all()
    return {"id": row.id, "schedule_id": row.schedule_id, "evaluator_id": row.evaluator_id, "status": row.status, "overall_score": row.overall_score, "overall_feedback": row.overall_feedback, "decision": row.decision, "disagreement_detected": row.disagreement_detected, "resolution_note": row.resolution_note, "scores": [{"criterion_key": score.criterion_key, "score": score.score, "max_score": score.max_score, "feedback": score.feedback} for score in scores], "created_at": row.created_at, "updated_at": row.updated_at}


def _evaluation_access(session: Session, row: PanelEvaluation, user: User) -> bool:
    schedule = session.get(DefenseSchedule, row.schedule_id)
    return schedule is not None and _schedule_access(session, schedule, user)


@router.get("/panel-evaluations/schedule/{schedule_id}")
def list_evaluations(schedule_id: int, user: User = Depends(require_roles(*READ_ROLES)), session: Session = Depends(get_db)) -> list[dict]:
    schedule = session.get(DefenseSchedule, schedule_id)
    if schedule is None: raise failure("schedule_not_found", "Defense schedule was not found.", 404)
    if not _schedule_access(session, schedule, user): raise HTTPException(403, detail="You are not authorized to access evaluations for this schedule.")
    return [_evaluation_out(session, row) for row in session.scalars(select(PanelEvaluation).where(PanelEvaluation.schedule_id == schedule_id).order_by(PanelEvaluation.id)).all()]


@router.post("/panel-evaluations", status_code=201)
def save_evaluation(payload: EvaluationWrite, request: Request, actor: User = Depends(require_roles(UserRole.PANEL_MEMBER)), session: Session = Depends(get_db)) -> dict:
    validate_mutating_origin(request)
    schedule = session.get(DefenseSchedule, payload.schedule_id)
    if schedule is None: raise failure("schedule_not_found", "Defense schedule was not found.", 404)
    if session.scalar(select(DefensePanelMember.id).where(DefensePanelMember.schedule_id == schedule.id, DefensePanelMember.user_id == actor.id)) is None: raise HTTPException(403, detail="You are not assigned to this defense schedule.")
    if payload.submit and not (payload.overall_feedback and payload.overall_feedback.strip()): raise failure("feedback_required", "Overall feedback is required before submitting an evaluation.", 422)
    for score in payload.scores:
        if score.score > score.max_score: raise failure("score_out_of_range", "A criterion score cannot exceed its maximum.", 422)
    row = session.scalar(select(PanelEvaluation).where(PanelEvaluation.schedule_id == schedule.id, PanelEvaluation.evaluator_id == actor.id).with_for_update())
    if row is None: row = PanelEvaluation(schedule_id=schedule.id, evaluator_id=actor.id); session.add(row); session.flush()
    row.status = "SUBMITTED" if payload.submit else "DRAFT"; row.overall_score = payload.overall_score; row.overall_feedback = payload.overall_feedback.strip() if payload.overall_feedback else None; row.decision = payload.decision.strip() if payload.decision else None
    session.query(PanelEvaluationScore).filter(PanelEvaluationScore.evaluation_id == row.id).delete(synchronize_session=False)
    for score in payload.scores: session.add(PanelEvaluationScore(evaluation_id=row.id, criterion_key=score.criterion_key.strip(), score=score.score, max_score=score.max_score, feedback=score.feedback.strip() if score.feedback else None))
    session.flush()
    submitted = session.scalars(select(PanelEvaluation).where(PanelEvaluation.schedule_id == schedule.id, PanelEvaluation.status == "SUBMITTED")).all()
    disagreement = len({item.decision for item in submitted if item.decision}) > 1 or (len([item.overall_score for item in submitted if item.overall_score is not None]) > 1 and max(item.overall_score for item in submitted if item.overall_score is not None) - min(item.overall_score for item in submitted if item.overall_score is not None) >= 20)
    for item in submitted: item.disagreement_detected = disagreement
    _audit(session, actor, "panel_evaluation_submitted" if payload.submit else "panel_evaluation_saved", "PANEL_EVALUATION", row.id, {"schedule_id": schedule.id, "status": row.status}); session.commit(); session.refresh(row)
    return _evaluation_out(session, row)


@router.post("/panel-evaluations/{evaluation_id}/resolution")
def resolve_evaluation(evaluation_id: int, payload: ResolutionWrite, request: Request, actor: User = Depends(require_roles(*WRITE_ROLES)), session: Session = Depends(get_db)) -> dict:
    validate_mutating_origin(request)
    row = session.get(PanelEvaluation, evaluation_id)
    if row is None: raise failure("evaluation_not_found", "Evaluation was not found.", 404)
    if actor.role not in (UserRole.ADMIN, UserRole.COORDINATOR):
        if payload.status != "RECHECK_REQUESTED" or not _evaluation_access(session, row, actor): raise HTTPException(403, detail="Only the assigned team or authorized reviewer may request a recheck.")
    row.status = payload.status; row.resolution_note = payload.note.strip(); _audit(session, actor, "panel_evaluation_resolution_updated", "PANEL_EVALUATION", row.id, {"status": row.status}); session.commit(); session.refresh(row)
    return _evaluation_out(session, row)
