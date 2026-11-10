"""Read-only operational data exposed specifically to coordinators."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import require_roles
from .database import get_db
from .models import AcademicCycle, AdminAuditEvent, EvaluationRubric, EvaluationRubricVersion, SupervisorAssignment, SupervisorCapacityPolicy, TemplateReference, TemplateReferenceVersion, User, UserRole

router = APIRouter(prefix="/api/v1/coordinator", tags=["coordinator-operations"])
COORDINATOR_ROLES = (UserRole.ADMIN, UserRole.COORDINATOR)


@router.get("/supervisor-capacity")
def supervisor_capacity(_: User = Depends(require_roles(*COORDINATOR_ROLES)), session: Session = Depends(get_db)):
    rows = session.execute(
        select(SupervisorCapacityPolicy, User, AcademicCycle)
        .join(User, User.id == SupervisorCapacityPolicy.supervisor_id)
        .outerjoin(AcademicCycle, AcademicCycle.id == SupervisorCapacityPolicy.academic_cycle_id)
        .order_by(SupervisorCapacityPolicy.academic_year, User.full_name, User.id)
    ).all()
    result = []
    for policy, user, cycle in rows:
        assignments = session.execute(select(SupervisorAssignment, AcademicCycle.session).outerjoin(AcademicCycle, AcademicCycle.id == SupervisorAssignment.academic_cycle_id).where(SupervisorAssignment.supervisor_id == policy.supervisor_id, SupervisorAssignment.ended_at.is_(None), (SupervisorAssignment.academic_year == policy.academic_year) | ((SupervisorAssignment.academic_year.is_(None)) & (AcademicCycle.academic_year == policy.academic_year)))).all()
        fall_assigned = sum(1 for assignment, cycle_session in assignments if (assignment.session or cycle_session) == "FALL")
        spring_assigned = sum(1 for assignment, cycle_session in assignments if (assignment.session or cycle_session) == "SPRING")
        assigned = len(assignments)
        remaining = max(policy.max_group_capacity - assigned, 0)
        eligible = user.is_active and user.role == UserRole.SUPERVISOR
        status = "INACTIVE" if not eligible else "OVER_CAPACITY" if assigned > policy.max_group_capacity else "FULL" if assigned == policy.max_group_capacity else "NEARLY_FULL" if assigned * 100 >= policy.max_group_capacity * 80 else "AVAILABLE"
        result.append({
        "id": policy.id,
        "supervisor_id": user.id,
        "supervisor_name": user.full_name,
        "academic_cycle_id": cycle.id if cycle else None,
        "academic_cycle": cycle.display_name if cycle else None,
        "max_group_capacity": policy.max_group_capacity,
        "academic_year": policy.academic_year or cycle.academic_year,
        "maximum_groups": policy.max_group_capacity,
        "assigned_groups": assigned,
        "remaining_groups": remaining,
        "fall_assigned": fall_assigned,
        "spring_assigned": spring_assigned,
        "total_assigned": assigned,
        "remaining_capacity": remaining,
        "status": status,
        })
    return result


@router.get("/audit-history")
def audit_history(_: User = Depends(require_roles(*COORDINATOR_ROLES)), session: Session = Depends(get_db)):
    rows = session.scalars(select(AdminAuditEvent).order_by(AdminAuditEvent.created_at.desc(), AdminAuditEvent.id.desc()).limit(100)).all()
    return [{
        "id": event.id,
        "actor_id": event.actor_id,
        "action": event.action,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "created_at": event.created_at,
    } for event in rows]


@router.get("/proposal-templates")
def proposal_templates(_: User = Depends(require_roles(*COORDINATOR_ROLES)), session: Session = Depends(get_db)):
    active = select(TemplateReferenceVersion.template_reference_id, TemplateReferenceVersion.id.label("version_id")).where(TemplateReferenceVersion.is_active.is_(True)).subquery()
    rows = session.execute(
        select(TemplateReferenceVersion, TemplateReference)
        .join(active, active.c.version_id == TemplateReferenceVersion.id)
        .join(TemplateReference, TemplateReference.id == TemplateReferenceVersion.template_reference_id)
        .order_by(TemplateReference.id)
    ).all()
    return [{"id": reference.id, "template_type": str(reference.template_type), "title": version.title, "version": version.version_number, "provenance": version.provenance, "is_active": version.is_active, "activated_at": version.activated_at} for version, reference in rows]


@router.get("/evaluation-criteria")
def evaluation_criteria(_: User = Depends(require_roles(*COORDINATOR_ROLES)), session: Session = Depends(get_db)):
    latest = select(EvaluationRubricVersion.rubric_id, func.max(EvaluationRubricVersion.version_number).label("version")).group_by(EvaluationRubricVersion.rubric_id).subquery()
    rows = session.scalars(select(EvaluationRubricVersion).join(latest, (latest.c.rubric_id == EvaluationRubricVersion.rubric_id) & (latest.c.version == EvaluationRubricVersion.version_number)).order_by(EvaluationRubricVersion.rubric_id)).all()
    return [{"id": row.rubric_id, "name": row.name, "description": row.description, "version": row.version_number} for row in rows]
