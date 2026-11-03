"""Read-only operational data exposed specifically to coordinators."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import require_roles
from .database import get_db
from .models import AcademicCycle, AdminAuditEvent, EvaluationRubric, EvaluationRubricVersion, M03ReferenceTemplate, SupervisorCapacityPolicy, TemplateReference, TemplateReferenceVersion, User, UserRole, WorkflowPolicy, WorkflowPolicyVersion

router = APIRouter(prefix="/api/v1/coordinator", tags=["coordinator-operations"])
COORDINATOR_ROLES = (UserRole.ADMIN, UserRole.COORDINATOR)


@router.get("/supervisor-capacity")
def supervisor_capacity(_: User = Depends(require_roles(*COORDINATOR_ROLES)), session: Session = Depends(get_db)):
    rows = session.execute(
        select(SupervisorCapacityPolicy, User, AcademicCycle)
        .join(User, User.id == SupervisorCapacityPolicy.supervisor_id)
        .join(AcademicCycle, AcademicCycle.id == SupervisorCapacityPolicy.academic_cycle_id)
        .order_by(AcademicCycle.id, User.full_name, User.id)
    ).all()
    return [{
        "id": policy.id,
        "supervisor_id": user.id,
        "supervisor_name": user.full_name,
        "academic_cycle_id": cycle.id,
        "academic_cycle": cycle.display_name,
        "max_group_capacity": policy.max_group_capacity,
    } for policy, user, cycle in rows]


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


@router.get("/workflow-policies")
def workflow_policies(_: User = Depends(require_roles(*COORDINATOR_ROLES)), session: Session = Depends(get_db)):
    latest = select(WorkflowPolicyVersion.policy_id, func.max(WorkflowPolicyVersion.version_number).label("version")).group_by(WorkflowPolicyVersion.policy_id).subquery()
    rows = session.execute(select(WorkflowPolicyVersion).join(latest, (latest.c.policy_id == WorkflowPolicyVersion.policy_id) & (latest.c.version == WorkflowPolicyVersion.version_number)).order_by(WorkflowPolicyVersion.policy_id)).scalars().all()
    return [{"id": row.policy_id, "name": row.name, "latest_version_number": row.version_number, "states": row.states, "transition_count": len(row.transitions)} for row in rows]


@router.get("/proposal-templates")
def proposal_templates(_: User = Depends(require_roles(*COORDINATOR_ROLES)), session: Session = Depends(get_db)):
    latest = select(TemplateReferenceVersion.template_reference_id, func.max(TemplateReferenceVersion.version_number).label("version")).group_by(TemplateReferenceVersion.template_reference_id).subquery()
    rows = session.execute(select(TemplateReferenceVersion, TemplateReference).join(latest, (latest.c.template_reference_id == TemplateReferenceVersion.template_reference_id) & (latest.c.version == TemplateReferenceVersion.version_number)).join(TemplateReference, TemplateReference.id == TemplateReferenceVersion.template_reference_id).order_by(TemplateReference.id)).all()
    return [{"id": reference.id, "template_type": str(reference.template_type), "title": version.title, "version": version.version_number, "provenance": version.provenance} for version, reference in rows]


@router.get("/module03-compliance")
def module03_compliance(_: User = Depends(require_roles(*COORDINATOR_ROLES)), session: Session = Depends(get_db)):
    rows = session.scalars(select(M03ReferenceTemplate).where(M03ReferenceTemplate.is_active.is_(True)).order_by(M03ReferenceTemplate.template_type, M03ReferenceTemplate.version.desc())).all()
    return [{"id": row.id, "template_type": row.template_type, "filename": row.filename, "version": row.version, "extraction_status": row.extraction_status, "activation_mode": row.activation_mode} for row in rows]


@router.get("/evaluation-criteria")
def evaluation_criteria(_: User = Depends(require_roles(*COORDINATOR_ROLES)), session: Session = Depends(get_db)):
    latest = select(EvaluationRubricVersion.rubric_id, func.max(EvaluationRubricVersion.version_number).label("version")).group_by(EvaluationRubricVersion.rubric_id).subquery()
    rows = session.scalars(select(EvaluationRubricVersion).join(latest, (latest.c.rubric_id == EvaluationRubricVersion.rubric_id) & (latest.c.version == EvaluationRubricVersion.version_number)).order_by(EvaluationRubricVersion.rubric_id)).all()
    return [{"id": row.rubric_id, "name": row.name, "description": row.description, "version": row.version_number} for row in rows]
