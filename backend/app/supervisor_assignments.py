from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .auth import require_roles, utc_now, validate_mutating_origin
from .database import get_db
from .models import SupervisorAssignment, SupervisorCapacityPolicy, SupervisorRequest, SupervisorRequestStatus, Team, User, UserRole

router = APIRouter(prefix="/api/v1/admin/supervisor-assignments")
class AssignmentWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    team_id: StrictInt = Field(gt=0)
    supervisor_id: StrictInt = Field(gt=0)
    academic_cycle_id: StrictInt = Field(gt=0)
def failure(code, message, status=409):
    return HTTPException(status_code=status, detail={"code": code, "message": message})
def out(row):
    return {"id": row.id, "team_id": row.team_id, "academic_cycle_id": row.academic_cycle_id, "supervisor_id": row.supervisor_id, "assigned_by_id": row.assigned_by_id, "created_at": row.created_at, "ended_at": row.ended_at, "ended_by_id": row.ended_by_id}
@router.get("/teams")
def teams(academic_cycle_id: int = Query(gt=0), _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    rows = session.execute(select(Team, User.full_name).join(User, Team.shared_user_id == User.id).where(Team.academic_cycle_id == academic_cycle_id).order_by(Team.id)).all()
    return [{"id": team.id, "academic_cycle_id": team.academic_cycle_id, "creator_name": name} for team, name in rows]
@router.get("")
def listing(academic_cycle_id: int = Query(gt=0), _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    return [out(row) for row in session.scalars(select(SupervisorAssignment).where(SupervisorAssignment.academic_cycle_id == academic_cycle_id).order_by(SupervisorAssignment.created_at, SupervisorAssignment.id)).all()]
@router.post("", status_code=201)
def assign(payload: AssignmentWrite, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    from .main import add_admin_audit_event, locked_eligible_supervisor_and_cycle
    validate_mutating_origin(request)
    try:
        session.execute(text("SELECT pg_advisory_xact_lock(98137243)"))
        locked_eligible_supervisor_and_cycle(session, payload.supervisor_id, payload.academic_cycle_id)
        policy = session.execute(select(SupervisorCapacityPolicy).where(SupervisorCapacityPolicy.supervisor_id == payload.supervisor_id, SupervisorCapacityPolicy.academic_cycle_id == payload.academic_cycle_id).with_for_update()).scalar_one_or_none()
        if policy is None: raise failure("capacity_policy_missing", "No capacity policy exists for this supervisor and cycle.")
        team = session.execute(select(Team).where(Team.id == payload.team_id).with_for_update()).scalar_one_or_none()
        if team is None: raise failure("team_not_found", "Team was not found.", 404)
        if team.academic_cycle_id != payload.academic_cycle_id: raise failure("cycle_mismatch", "Team does not belong to the selected cycle.")
        if session.scalar(select(SupervisorAssignment.id).where(SupervisorAssignment.team_id == team.id, SupervisorAssignment.ended_at.is_(None))) is not None: raise failure("team_already_assigned", "Team already has an active supervisor assignment.")
        count = session.scalar(select(func.count(SupervisorAssignment.id)).where(SupervisorAssignment.supervisor_id == payload.supervisor_id, SupervisorAssignment.academic_cycle_id == payload.academic_cycle_id, SupervisorAssignment.ended_at.is_(None))) or 0
        count += session.scalar(select(func.count(SupervisorRequest.id)).where(SupervisorRequest.supervisor_id == payload.supervisor_id, SupervisorRequest.academic_cycle_id == payload.academic_cycle_id, SupervisorRequest.status == SupervisorRequestStatus.ACCEPTED.value, SupervisorRequest.assignment_id.is_(None))) or 0
        if count >= policy.max_group_capacity: raise failure("capacity_full", "Supervisor capacity is full for this cycle.")
        assignment = SupervisorAssignment(**payload.model_dump(), assigned_by_id=actor.id); session.add(assignment); session.flush()
        add_admin_audit_event(session, actor_id=actor.id, affected_user_id=payload.supervisor_id, target_type="SUPERVISOR_ASSIGNMENT", target_id=assignment.id, action="supervisor_assignment_created", changed_values=payload.model_dump())
        session.commit(); session.refresh(assignment); return out(assignment)
    except HTTPException:
        session.rollback(); raise
    except IntegrityError as exc:
        session.rollback(); raise failure("assignment_conflict", "The assignment conflicts with another change.") from exc
    except Exception as exc:
        session.rollback(); raise failure("assignment_save_failed", "Assignment could not be saved.", 500) from exc
@router.post("/{assignment_id}/end")
def end(assignment_id: int, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    from .main import add_admin_audit_event
    validate_mutating_origin(request)
    try:
        session.execute(text("SELECT pg_advisory_xact_lock(98137243)"))
        row = session.execute(select(SupervisorAssignment).where(SupervisorAssignment.id == assignment_id).with_for_update()).scalar_one_or_none()
        if row is None: raise failure("assignment_not_found", "Assignment was not found.", 404)
        if row.ended_at is not None: raise failure("assignment_already_ended", "Assignment has already ended.")
        row.ended_at = utc_now(); row.ended_by_id = actor.id
        add_admin_audit_event(session, actor_id=actor.id, affected_user_id=row.supervisor_id, target_type="SUPERVISOR_ASSIGNMENT", target_id=row.id, action="supervisor_assignment_ended", changed_values={"team_id": row.team_id, "academic_cycle_id": row.academic_cycle_id, "supervisor_id": row.supervisor_id})
        session.commit(); session.refresh(row); return out(row)
    except HTTPException:
        session.rollback(); raise
    except Exception as exc:
        session.rollback(); raise failure("assignment_save_failed", "Assignment could not be saved.", 500) from exc
