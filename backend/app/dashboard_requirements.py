"""Role-scoped deadlines and requirements for all dashboards."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from .auth import get_current_user, require_roles, validate_mutating_origin
from .database import get_db
from .models import AcademicDeadline, AcademicDeadlineVersion, DashboardRequirement, User, UserRole
from .schemas.dashboard_requirements import DashboardRequirementOut, DashboardRequirementWrite

router = APIRouter(prefix="/api/v1/dashboard")

def _status(item: DashboardRequirement) -> str:
    if item.completed_at is not None or item.completion_percent >= 100: return "COMPLETED"
    due = item.due_at if item.due_at.tzinfo else item.due_at.replace(tzinfo=timezone.utc)
    delta = (due - datetime.now(timezone.utc)).total_seconds()
    return "OVERDUE" if delta < 0 else "DUE_SOON" if delta <= 7 * 86400 else "UPCOMING"

def _due_source(session: Session, item: DashboardRequirement) -> tuple[datetime, str]:
    if item.academic_deadline_id:
        version = session.scalar(select(AcademicDeadlineVersion).where(AcademicDeadlineVersion.academic_deadline_id == item.academic_deadline_id).order_by(AcademicDeadlineVersion.version_number.desc()))
        if version is not None: return version.due_at_utc, version.time_zone
    return item.due_at, "UTC"

def _out(session: Session, item: DashboardRequirement, actor: User) -> dict[str, object]:
    due, zone = _due_source(session, item)
    return {"id": item.id, "title": item.title, "description": item.description, "due_date": due, "timezone": zone, "academic_cycle": item.academic_cycle_id, "module": item.module, "requirement_type": item.requirement_type, "priority": item.priority, "status": _status(item), "completion_percent": item.completion_percent, "is_required": item.is_required, "source_deadline_id": item.academic_deadline_id, "assigned_to_current_user": item.assigned_user_id == actor.id, "can_update": item.assigned_user_id == actor.id or actor.role in (UserRole.ADMIN, UserRole.COORDINATOR)}

def _visible(session: Session, actor: User):
    role = actor.role.value
    rows = session.scalars(select(DashboardRequirement).where(DashboardRequirement.role_visibility.contains([role]))).all()
    return [row for row in rows if row.assigned_user_id is None or row.assigned_user_id == actor.id]

@router.get("/requirements", response_model=list[DashboardRequirementOut])
@router.get("/deadlines", response_model=list[DashboardRequirementOut])
def dashboard_requirements(actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    priority = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    rows = [_out(session, item, actor) for item in _visible(session, actor)]
    rank = {"OVERDUE": 0, "DUE_SOON": 1, "UPCOMING": 2, "COMPLETED": 3, "NOT_APPLICABLE": 4}
    return sorted(rows, key=lambda item: (rank[item["status"]], item["due_date"], priority[item["priority"]]))

@router.get("/summary")
def dashboard_summary(actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    rows = dashboard_requirements(actor, session)
    return {"total": len(rows), "overdue": sum(row["status"] == "OVERDUE" for row in rows), "due_soon": sum(row["status"] == "DUE_SOON" for row in rows), "completed": sum(row["status"] == "COMPLETED" for row in rows)}

@router.post("/requirements", response_model=DashboardRequirementOut, status_code=status.HTTP_201_CREATED)
def create_requirement(payload: DashboardRequirementWrite, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN, UserRole.COORDINATOR)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    if payload.academic_deadline_id is not None and session.get(AcademicDeadline, payload.academic_deadline_id) is None:
        from fastapi import HTTPException
        raise HTTPException(404, "Source deadline was not found.")
    item = DashboardRequirement(**payload.model_dump(), created_by_id=actor.id)
    session.add(item); session.commit(); session.refresh(item); return _out(session, item, actor)

@router.patch("/requirements/{requirement_id}", response_model=DashboardRequirementOut)
def update_requirement(requirement_id: int, payload: DashboardRequirementWrite, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN, UserRole.COORDINATOR)), session: Session = Depends(get_db)):
    validate_mutating_origin(request); item = session.get(DashboardRequirement, requirement_id)
    if item is None:
        from fastapi import HTTPException
        raise HTTPException(404, "Requirement was not found.")
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    session.commit(); session.refresh(item); return _out(session, item, actor)

@router.delete("/requirements/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_requirement(requirement_id: int, request: Request, _: User = Depends(require_roles(UserRole.ADMIN, UserRole.COORDINATOR)), session: Session = Depends(get_db)):
    validate_mutating_origin(request); item = session.get(DashboardRequirement, requirement_id)
    if item is None:
        from fastapi import HTTPException
        raise HTTPException(404, "Requirement was not found.")
    session.delete(item); session.commit()
