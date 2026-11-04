"""Role-scoped FYP evaluation, marks, audit, reporting, and result APIs."""

from __future__ import annotations

from io import BytesIO
from statistics import median
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles, utc_now, validate_mutating_origin
from .database import get_db
from .models import (
    AcademicCycle,
    DefensePanelMember,
    DefenseSchedule,
    EvaluationAggregationConfig,
    EvaluationAuditEvent,
    EvaluationCorrection,
    EvaluationRecord,
    SupervisorAssignment,
    Team,
    TeamMember,
    User,
    UserRole,
)
from .schemas.evaluations import (
    MAXIMUM_MARKS,
    AssignmentMemberOut,
    ConsolidatedResultOut,
    EvaluationAggregationOut,
    EvaluationAggregationWrite,
    EvaluationAssignmentOut,
    EvaluationCategory,
    EvaluationCorrectionWrite,
    EvaluationOut,
    EvaluationReturn,
    EvaluationStatus,
    EvaluationWrite,
    ResultCategoryOut,
)


router = APIRouter(prefix="/api/v1")
PANEL_CATEGORIES = {EvaluationCategory.FINAL_PRESENTATION.value, EvaluationCategory.MID_REVIEW.value}
SUPERVISOR_CATEGORIES = {EvaluationCategory.SUPERVISOR_EVALUATION.value}
ADMIN_CATEGORIES = {EvaluationCategory.PROJECT_DOCUMENTATION.value, EvaluationCategory.PROPOSAL.value}
PANEL_ROLES = (UserRole.PANEL_MEMBER,)
ADMIN_ROLES = (UserRole.ADMIN, UserRole.COORDINATOR)


def _error(code: str, message: str, code_status: int = status.HTTP_409_CONFLICT) -> HTTPException:
    return HTTPException(code_status, detail={"code": code, "message": message})


def _role_categories(role: UserRole) -> set[str]:
    if role == UserRole.PANEL_MEMBER:
        return PANEL_CATEGORIES
    if role == UserRole.SUPERVISOR:
        return SUPERVISOR_CATEGORIES
    if role in ADMIN_ROLES:
        return ADMIN_CATEGORIES
    return set()


def _target_group_ids(session: Session, user: User, target_group_id: int | None = None) -> set[int]:
    if target_group_id is not None:
        return {target_group_id}
    if user.role == UserRole.SUPERVISOR:
        return set(session.scalars(select(SupervisorAssignment.team_id).where(SupervisorAssignment.supervisor_id == user.id, SupervisorAssignment.ended_at.is_(None))).all())
    if user.role == UserRole.PANEL_MEMBER:
        return set(session.scalars(select(DefenseSchedule.team_id).join(DefensePanelMember, DefensePanelMember.schedule_id == DefenseSchedule.id).where(DefensePanelMember.user_id == user.id, DefenseSchedule.status != "CANCELLED")).all())
    if user.role in ADMIN_ROLES:
        return set(session.scalars(select(Team.id)).all())
    return set()


def _panel_can_access(session: Session, actor: User, group_id: int) -> bool:
    return session.scalar(
        select(DefensePanelMember.id)
        .join(DefenseSchedule, DefenseSchedule.id == DefensePanelMember.schedule_id)
        .where(DefensePanelMember.user_id == actor.id, DefenseSchedule.team_id == group_id, DefenseSchedule.status != "CANCELLED")
    ) is not None


def _actor_can_access_group(session: Session, actor: User, group_id: int) -> bool:
    if actor.role in ADMIN_ROLES:
        return session.scalar(select(Team.id).where(Team.id == group_id)) is not None
    if actor.role == UserRole.SUPERVISOR:
        return session.scalar(select(SupervisorAssignment.id).where(SupervisorAssignment.team_id == group_id, SupervisorAssignment.supervisor_id == actor.id, SupervisorAssignment.ended_at.is_(None))) is not None
    if actor.role == UserRole.PANEL_MEMBER:
        return _panel_can_access(session, actor, group_id)
    return False


def _record_target(record: EvaluationRecord) -> int:
    return record.group_id or record.student_id or 0


def _record_out(record: EvaluationRecord) -> EvaluationOut:
    return EvaluationOut.model_validate(record)


def _audit(session: Session, record: EvaluationRecord, actor: User, action: str, *, reason: str | None = None, previous: int | None = None, changed: dict | None = None) -> None:
    session.add(EvaluationAuditEvent(evaluation_id=record.id, actor_id=actor.id, action=action, previous_marks=previous, new_marks=record.obtained_marks, reason=reason, changed_values=changed or {"status": record.status, "category": record.evaluation_category}))


def _validate_category_owner(actor: User, category: str) -> None:
    if category not in _role_categories(actor.role):
        raise _error("category_not_owned", "Your role is not authorized to enter this evaluation category.", status.HTTP_403_FORBIDDEN)


def _resolve_target(session: Session, payload: EvaluationWrite) -> tuple[int | None, int | None]:
    group_id = payload.group_id or payload.team_id
    if group_id is not None:
        if session.scalar(select(Team.id).where(Team.id == group_id)) is None:
            raise _error("group_not_found", "The selected FYP group was not found.", status.HTTP_404_NOT_FOUND)
        if payload.student_id is not None:
            student = session.scalar(select(User).where(User.id == payload.student_id, User.role == UserRole.STUDENT))
            if student is None or session.scalar(select(TeamMember.id).where(TeamMember.team_id == group_id, TeamMember.is_active.is_(True), or_(TeamMember.registration_number == student.registration_number, TeamMember.university_email == student.email))) is None:
                raise _error("student_group_mismatch", "The selected student is not a member of the selected group.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        return None, group_id
    if session.scalar(select(User.id).where(User.id == payload.student_id, User.role == UserRole.STUDENT)) is None:
        raise _error("student_not_found", "The selected student was not found.", status.HTTP_404_NOT_FOUND)
    return payload.student_id, None


def _target_filter(record: EvaluationRecord, student_id: int | None, group_id: int | None):
    return or_(and_(student_id is not None, record.student_id == student_id), and_(group_id is not None, record.group_id == group_id))


def _assignment_out(session: Session, team: Team, categories: Iterable[str]) -> EvaluationAssignmentOut:
    members = session.scalars(select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True)).order_by(TeamMember.is_creator.desc(), TeamMember.id)).all()
    return EvaluationAssignmentOut(group_id=team.id, academic_cycle_id=team.academic_cycle_id, students=[AssignmentMemberOut(id=item.id, full_name=item.full_name, registration_number=item.registration_number, university_email=item.university_email) for item in members], categories=sorted(categories))


@router.get("/evaluations/assignments", response_model=list[EvaluationAssignmentOut])
def evaluation_assignments(actor: User = Depends(get_current_user), session: Session = Depends(get_db)) -> list[EvaluationAssignmentOut]:
    group_ids = _target_group_ids(session, actor)
    teams = session.scalars(select(Team).where(Team.id.in_(group_ids)).order_by(Team.id)).all() if group_ids else []
    return [_assignment_out(session, team, _role_categories(actor.role)) for team in teams]


@router.get("/evaluations/my", response_model=list[EvaluationOut])
def my_evaluations(
    evaluation_status: str | None = Query(default=None, alias="status"),
    category: str | None = None,
    actor: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[EvaluationOut]:
    query = select(EvaluationRecord).where(EvaluationRecord.evaluator_id == actor.id)
    if evaluation_status:
        query = query.where(EvaluationRecord.status == evaluation_status.upper())
    if category:
        query = query.where(EvaluationRecord.evaluation_category == category.upper())
    return [_record_out(row) for row in session.scalars(query.order_by(EvaluationRecord.updated_at.desc(), EvaluationRecord.id.desc())).all()]


def _save_record(session: Session, actor: User, payload: EvaluationWrite, record: EvaluationRecord | None = None) -> EvaluationRecord:
    category = payload.evaluation_category.value
    _validate_category_owner(actor, category)
    student_id, group_id = _resolve_target(session, payload)
    if group_id is not None and not _actor_can_access_group(session, actor, group_id):
        raise _error("assignment_not_authorized", "This group is not assigned to your evaluator role.", status.HTTP_403_FORBIDDEN)
    if record is None:
        filters = [EvaluationRecord.evaluator_id == actor.id, EvaluationRecord.evaluation_category == category]
        filters.append(EvaluationRecord.group_id == group_id if group_id is not None else EvaluationRecord.student_id == student_id)
        record = session.scalar(select(EvaluationRecord).where(*filters).with_for_update())
    elif record.evaluation_category != category or record.student_id != student_id or record.group_id != group_id:
        raise _error("evaluation_target_immutable", "An existing evaluation cannot be reassigned or moved to another category.", status.HTTP_409_CONFLICT)
    if record is None:
        record = EvaluationRecord(student_id=student_id, group_id=group_id, evaluator_id=actor.id, evaluator_role=actor.role.value, evaluation_category=category, maximum_marks=MAXIMUM_MARKS[payload.evaluation_category])
        session.add(record)
        session.flush()
    if record.evaluator_id != actor.id:
        raise _error("evaluation_owner_required", "Only the assigned evaluator can edit this record.", status.HTTP_403_FORBIDDEN)
    if record.status in {EvaluationStatus.SUBMITTED.value, EvaluationStatus.APPROVED.value, EvaluationStatus.PUBLISHED.value} and record.status != EvaluationStatus.RETURNED.value:
        raise _error("evaluation_locked", "Submitted evaluations are locked. Request an authorized correction before editing.", status.HTTP_409_CONFLICT)
    previous = record.obtained_marks
    record.obtained_marks = payload.obtained_marks
    record.feedback = payload.feedback
    record.returned_reason = None
    if payload.submit:
        if payload.obtained_marks is None:
            raise _error("marks_required", "Marks are required before submission.", status.HTTP_422_UNPROCESSABLE_CONTENT)
        record.status = EvaluationStatus.SUBMITTED.value
        record.submitted_at = utc_now()
        _audit(session, record, actor, "submitted", previous=previous)
    else:
        record.status = EvaluationStatus.DRAFT.value
        _audit(session, record, actor, "draft_saved", previous=previous)
    session.flush()
    return record


@router.post("/evaluations", response_model=EvaluationOut, status_code=status.HTTP_201_CREATED)
def create_evaluation(payload: EvaluationWrite, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)) -> EvaluationOut:
    validate_mutating_origin(request)
    try:
        record = _save_record(session, actor, payload)
        session.commit()
        session.refresh(record)
        return _record_out(record)
    except HTTPException:
        session.rollback()
        raise
    except IntegrityError as error:
        session.rollback()
        raise _error("evaluation_conflict", "An evaluation already exists for this evaluator and category.") from error


@router.patch("/evaluations/{evaluation_id}", response_model=EvaluationOut)
def update_evaluation(evaluation_id: int, payload: EvaluationWrite, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)) -> EvaluationOut:
    validate_mutating_origin(request)
    record = session.scalar(select(EvaluationRecord).where(EvaluationRecord.id == evaluation_id).with_for_update())
    if record is None:
        raise _error("evaluation_not_found", "The evaluation was not found.", status.HTTP_404_NOT_FOUND)
    try:
        record = _save_record(session, actor, payload, record)
        session.commit()
        session.refresh(record)
        return _record_out(record)
    except HTTPException:
        session.rollback()
        raise


@router.post("/evaluations/{evaluation_id}/submit", response_model=EvaluationOut)
def submit_evaluation(evaluation_id: int, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)) -> EvaluationOut:
    validate_mutating_origin(request)
    record = session.scalar(select(EvaluationRecord).where(EvaluationRecord.id == evaluation_id).with_for_update())
    if record is None:
        raise _error("evaluation_not_found", "The evaluation was not found.", status.HTTP_404_NOT_FOUND)
    if record.evaluator_id != actor.id:
        raise _error("evaluation_owner_required", "Only the assigned evaluator can submit this record.", status.HTTP_403_FORBIDDEN)
    if record.obtained_marks is None:
        raise _error("marks_required", "Marks are required before submission.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if record.status not in {EvaluationStatus.DRAFT.value, EvaluationStatus.RETURNED.value}:
        raise _error("evaluation_locked", "This evaluation is already submitted or approved.")
    record.status = EvaluationStatus.SUBMITTED.value
    record.submitted_at = utc_now()
    record.returned_reason = None
    _audit(session, record, actor, "submitted")
    session.commit()
    session.refresh(record)
    return _record_out(record)


@router.post("/evaluations/{evaluation_id}/return", response_model=EvaluationOut)
def return_evaluation(evaluation_id: int, payload: EvaluationReturn, request: Request, actor: User = Depends(require_roles(*ADMIN_ROLES)), session: Session = Depends(get_db)) -> EvaluationOut:
    validate_mutating_origin(request)
    record = session.scalar(select(EvaluationRecord).where(EvaluationRecord.id == evaluation_id).with_for_update())
    if record is None:
        raise _error("evaluation_not_found", "The evaluation was not found.", status.HTTP_404_NOT_FOUND)
    if record.status not in {EvaluationStatus.SUBMITTED.value, EvaluationStatus.APPROVED.value}:
        raise _error("evaluation_not_returnable", "Only submitted or approved evaluations can be returned.")
    previous = record.obtained_marks
    record.status = EvaluationStatus.RETURNED.value
    record.returned_reason = payload.reason.strip()
    record.approved_at = None
    _audit(session, record, actor, "returned_for_correction", reason=payload.reason.strip(), previous=previous)
    session.commit()
    session.refresh(record)
    return _record_out(record)


@router.post("/evaluations/{evaluation_id}/approve", response_model=EvaluationOut)
def approve_evaluation(evaluation_id: int, request: Request, actor: User = Depends(require_roles(*ADMIN_ROLES)), session: Session = Depends(get_db)) -> EvaluationOut:
    validate_mutating_origin(request)
    record = session.scalar(select(EvaluationRecord).where(EvaluationRecord.id == evaluation_id).with_for_update())
    if record is None:
        raise _error("evaluation_not_found", "The evaluation was not found.", status.HTTP_404_NOT_FOUND)
    if record.status != EvaluationStatus.SUBMITTED.value:
        raise _error("evaluation_not_submitted", "Only submitted evaluations can be approved.")
    record.status = EvaluationStatus.APPROVED.value
    record.approved_at = utc_now()
    _audit(session, record, actor, "approved")
    session.commit()
    session.refresh(record)
    return _record_out(record)


@router.post("/evaluations/{evaluation_id}/correct", response_model=EvaluationOut)
def correct_evaluation(evaluation_id: int, payload: EvaluationCorrectionWrite, request: Request, actor: User = Depends(require_roles(*ADMIN_ROLES)), session: Session = Depends(get_db)) -> EvaluationOut:
    validate_mutating_origin(request)
    record = session.scalar(select(EvaluationRecord).where(EvaluationRecord.id == evaluation_id).with_for_update())
    if record is None:
        raise _error("evaluation_not_found", "The evaluation was not found.", status.HTTP_404_NOT_FOUND)
    if record.obtained_marks is None:
        raise _error("marks_required", "Only an evaluation with existing marks can be corrected.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if payload.new_marks > record.maximum_marks:
        raise _error("marks_out_of_range", f"Marks cannot exceed the maximum of {record.maximum_marks}.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    previous = record.obtained_marks
    session.add(EvaluationCorrection(evaluation_id=record.id, authorized_by_id=actor.id, previous_marks=previous, new_marks=payload.new_marks, reason=payload.reason))
    record.obtained_marks = payload.new_marks
    record.returned_reason = None
    record.status = EvaluationStatus.APPROVED.value if actor.role == UserRole.ADMIN else EvaluationStatus.SUBMITTED.value
    record.approved_at = utc_now() if actor.role == UserRole.ADMIN else None
    _audit(session, record, actor, "authorized_correction", reason=payload.reason, previous=previous, changed={"previous_marks": previous, "new_marks": payload.new_marks})
    session.commit()
    session.refresh(record)
    return _record_out(record)


@router.post("/evaluations/{evaluation_id}/publish", response_model=EvaluationOut)
def publish_evaluation(evaluation_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> EvaluationOut:
    validate_mutating_origin(request)
    record = session.scalar(select(EvaluationRecord).where(EvaluationRecord.id == evaluation_id).with_for_update())
    if record is None:
        raise _error("evaluation_not_found", "The evaluation was not found.", status.HTTP_404_NOT_FOUND)
    if record.status != EvaluationStatus.APPROVED.value:
        raise _error("evaluation_not_approved", "Only approved evaluations can be published.")
    record.status = EvaluationStatus.PUBLISHED.value
    record.published_at = utc_now()
    _audit(session, record, actor, "published")
    session.commit()
    session.refresh(record)
    return _record_out(record)


@router.get("/evaluations/{evaluation_id}/audit")
def evaluation_audit(evaluation_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)) -> list[dict]:
    record = session.get(EvaluationRecord, evaluation_id)
    if record is None:
        raise _error("evaluation_not_found", "The evaluation was not found.", status.HTTP_404_NOT_FOUND)
    if actor.role not in ADMIN_ROLES and record.evaluator_id != actor.id:
        raise _error("evaluation_access_denied", "You are not authorized to view this evaluation history.", status.HTTP_403_FORBIDDEN)
    rows = session.scalars(select(EvaluationAuditEvent).where(EvaluationAuditEvent.evaluation_id == evaluation_id).order_by(EvaluationAuditEvent.created_at, EvaluationAuditEvent.id)).all()
    return [{"id": row.id, "evaluation_id": row.evaluation_id, "actor_id": row.actor_id, "action": row.action, "previous_marks": row.previous_marks, "new_marks": row.new_marks, "reason": row.reason, "changed_values": row.changed_values, "created_at": row.created_at} for row in rows]


@router.get("/admin/evaluations", response_model=list[EvaluationOut])
def admin_evaluations(evaluation_status: str | None = Query(default=None, alias="status"), category: str | None = None, evaluator_id: int | None = None, actor: User = Depends(require_roles(*ADMIN_ROLES)), session: Session = Depends(get_db)) -> list[EvaluationOut]:
    query = select(EvaluationRecord)
    if evaluation_status:
        query = query.where(EvaluationRecord.status == evaluation_status.upper())
    if category:
        query = query.where(EvaluationRecord.evaluation_category == category.upper())
    if evaluator_id:
        query = query.where(EvaluationRecord.evaluator_id == evaluator_id)
    return [_record_out(row) for row in session.scalars(query.order_by(EvaluationRecord.updated_at.desc(), EvaluationRecord.id.desc())).all()]


@router.get("/admin/evaluations/aggregation", response_model=list[EvaluationAggregationOut])
def list_aggregation(actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> list[EvaluationAggregationOut]:
    rows = session.scalars(select(EvaluationAggregationConfig).order_by(EvaluationAggregationConfig.evaluation_category)).all()
    configured = {row.evaluation_category: row for row in rows}
    result = []
    for category in sorted(PANEL_CATEGORIES):
        row = configured.get(category)
        result.append(EvaluationAggregationOut(id=row.id if row else 0, evaluation_category=category, method=row.method if row else "AVERAGE", is_active=row.is_active if row else True))
    return result


@router.put("/admin/evaluations/aggregation", response_model=EvaluationAggregationOut)
def update_aggregation(payload: EvaluationAggregationWrite, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)) -> EvaluationAggregationOut:
    validate_mutating_origin(request)
    category = payload.evaluation_category.value
    if category not in PANEL_CATEGORIES:
        raise _error("aggregation_category_invalid", "Only panel evaluation categories can be aggregated.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    row = session.scalar(select(EvaluationAggregationConfig).where(EvaluationAggregationConfig.evaluation_category == category).with_for_update())
    if row is None:
        row = EvaluationAggregationConfig(evaluation_category=category, method=payload.method, created_by_id=actor.id)
        session.add(row)
    else:
        row.method = payload.method
        row.is_active = True
    session.commit()
    session.refresh(row)
    return EvaluationAggregationOut(id=row.id, evaluation_category=row.evaluation_category, method=row.method, is_active=row.is_active)


def _student_group(session: Session, student: User) -> Team | None:
    return session.scalar(select(Team).join(TeamMember, TeamMember.team_id == Team.id).where(TeamMember.is_active.is_(True), or_(TeamMember.registration_number == student.registration_number, TeamMember.university_email == student.email)).order_by(Team.id.desc()))


def _aggregation_method(session: Session, category: str) -> str:
    row = session.scalar(select(EvaluationAggregationConfig).where(EvaluationAggregationConfig.evaluation_category == category, EvaluationAggregationConfig.is_active.is_(True)))
    return row.method if row else "AVERAGE"


def _category_result(session: Session, student: User, category: str, *, published_only: bool) -> ResultCategoryOut:
    team = _student_group(session, student)
    filters = [EvaluationRecord.evaluation_category == category]
    if published_only:
        filters.append(EvaluationRecord.status == EvaluationStatus.PUBLISHED.value)
    else:
        filters.append(EvaluationRecord.status != EvaluationStatus.DRAFT.value)
    target = []
    if team is not None:
        target.append(EvaluationRecord.group_id == team.id)
    target.append(EvaluationRecord.student_id == student.id)
    rows = session.scalars(select(EvaluationRecord).where(*filters, or_(*target)).order_by(EvaluationRecord.updated_at.desc(), EvaluationRecord.id.desc())).all()
    maximum = MAXIMUM_MARKS[EvaluationCategory(category)]
    values = [row.obtained_marks for row in rows if row.obtained_marks is not None]
    if not values:
        return ResultCategoryOut(category=category, maximum_marks=maximum, obtained_marks=None, status="HIDDEN" if published_only else "MISSING", evaluator_ids=[], feedback=[])
    method = _aggregation_method(session, category) if category in PANEL_CATEGORIES else "AVERAGE"
    value = sum(values) / len(values) if method == "AVERAGE" else max(values) if method == "MAXIMUM" else float(median(values))
    status_value = "PUBLISHED" if all(row.status == EvaluationStatus.PUBLISHED.value for row in rows) else rows[0].status
    return ResultCategoryOut(category=category, maximum_marks=maximum, obtained_marks=round(value, 2), status=status_value, evaluator_ids=sorted({row.evaluator_id for row in rows}), feedback=[row.feedback for row in rows if row.feedback])


def _grade(total: float) -> tuple[str, float]:
    if total >= 90: return "A+", 4.00
    if total >= 85: return "A", 3.75
    if total >= 80: return "A-", 3.50
    if total >= 75: return "B+", 3.25
    if total >= 70: return "B", 3.00
    if total >= 66: return "B-", 2.75
    if total >= 63: return "C+", 2.50
    if total >= 60: return "C", 2.00
    if total >= 55: return "C-", 1.50
    return "F", 0.00


def _result(session: Session, student: User, *, published_only: bool) -> ConsolidatedResultOut:
    categories = [_category_result(session, student, category, published_only=published_only) for category in ("PROJECT_DOCUMENTATION", "FINAL_PRESENTATION", "PROPOSAL", "MID_REVIEW", "SUPERVISOR_EVALUATION")]
    complete = all(item.obtained_marks is not None for item in categories)
    total = round(sum(item.obtained_marks or 0 for item in categories), 2)
    grade, gpa = _grade(total) if complete else (None, None)
    team = _student_group(session, student)
    return ConsolidatedResultOut(student_id=student.id, group_id=team.id if team else None, student_name=student.full_name, registration_number=student.registration_number, categories=categories, total_marks=total, maximum_marks=100, percentage=total, grade=grade, gpa=gpa, published=published_only and complete)


@router.get("/student/results", response_model=ConsolidatedResultOut)
def student_results(actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)) -> ConsolidatedResultOut:
    return _result(session, actor, published_only=True)


@router.get("/admin/results/group/{group_id}", response_model=list[ConsolidatedResultOut])
def admin_group_results(group_id: int, actor: User = Depends(require_roles(*ADMIN_ROLES)), session: Session = Depends(get_db)) -> list[ConsolidatedResultOut]:
    if session.scalar(select(Team.id).where(Team.id == group_id)) is None:
        raise _error("group_not_found", "The FYP group was not found.", status.HTTP_404_NOT_FOUND)
    students = session.scalars(
        select(User).join(TeamMember, or_(TeamMember.registration_number == User.registration_number, TeamMember.university_email == User.email)).where(TeamMember.team_id == group_id, TeamMember.is_active.is_(True), User.role == UserRole.STUDENT).order_by(User.id)
    ).all()
    return [_result(session, student, published_only=False) for student in students]


@router.get("/admin/results/{student_id}", response_model=ConsolidatedResultOut)
def admin_results(student_id: int, actor: User = Depends(require_roles(*ADMIN_ROLES)), session: Session = Depends(get_db)) -> ConsolidatedResultOut:
    student = session.scalar(select(User).where(User.id == student_id, User.role == UserRole.STUDENT))
    if student is None:
        raise _error("student_not_found", "The student was not found.", status.HTTP_404_NOT_FOUND)
    return _result(session, student, published_only=False)


def _report_lines(record: EvaluationRecord, student: User | None) -> list[str]:
    return [
        "FYPHub Individual Evaluation Report",
        f"Student: {student.full_name if student else 'Assigned group'}",
        f"Evaluator role: {record.evaluator_role}",
        f"Category: {record.evaluation_category}",
        f"Marks: {record.obtained_marks if record.obtained_marks is not None else 'Not entered'} / {record.maximum_marks}",
        f"Status: {record.status}",
        f"Feedback: {record.feedback or 'No feedback provided.'}",
    ]


def _simple_pdf(lines: list[str]) -> bytes:
    escaped = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")[:180] for line in lines]
    stream = "BT /F1 11 Tf 50 760 Td " + " ".join(f"({line}) Tj 0 -18 Td" for line in escaped) + " ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>", b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", f"<< /Length {len(stream.encode())} >>\nstream\n{stream}\nendstream".encode()]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output)); output.extend(f"{index} 0 obj\n".encode()); output.extend(obj); output.extend(b"\nendobj\n")
    start = len(output); output.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode()); output.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])); output.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF".encode()); return bytes(output)


@router.get("/evaluations/{evaluation_id}/report")
def evaluation_report(evaluation_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)) -> dict:
    record = session.get(EvaluationRecord, evaluation_id)
    if record is None:
        raise _error("evaluation_not_found", "The evaluation was not found.", status.HTTP_404_NOT_FOUND)
    if actor.role not in ADMIN_ROLES and record.evaluator_id != actor.id:
        raise _error("evaluation_access_denied", "You are not authorized to view this report.", status.HTTP_403_FORBIDDEN)
    student = session.get(User, record.student_id) if record.student_id else None
    return {"record": _record_out(record).model_dump(mode="json"), "lines": _report_lines(record, student)}


@router.get("/evaluations/{evaluation_id}/report.pdf")
def evaluation_report_pdf(evaluation_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)) -> Response:
    record = session.get(EvaluationRecord, evaluation_id)
    if record is None:
        raise _error("evaluation_not_found", "The evaluation was not found.", status.HTTP_404_NOT_FOUND)
    if actor.role not in ADMIN_ROLES and record.evaluator_id != actor.id:
        raise _error("evaluation_access_denied", "You are not authorized to download this report.", status.HTTP_403_FORBIDDEN)
    student = session.get(User, record.student_id) if record.student_id else None
    return Response(content=_simple_pdf(_report_lines(record, student)), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="evaluation-{record.id}.pdf"'})
