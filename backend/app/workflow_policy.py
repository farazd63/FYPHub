from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .auth import require_roles, validate_mutating_origin
from .database import get_db
from .models import User, UserRole
from .models.workflow_policy import WorkflowPolicy, WorkflowPolicyVersion
from .schemas.workflow_policy import PolicyWrite

router = APIRouter(prefix="/api/v1/admin/workflow-policies")

def version_out(version):
    return {"id": version.id, "version_number": version.version_number, "name": version.name,
            "states": version.states, "transitions": version.transitions, "created_at": version.created_at}

def history(session, policy):
    versions = session.scalars(select(WorkflowPolicyVersion).where(WorkflowPolicyVersion.policy_id == policy.id).order_by(WorkflowPolicyVersion.version_number)).all()
    return {"id": policy.id, "created_at": policy.created_at, "versions": [version_out(v) for v in versions]}

def save(session, policy, payload, actor, number):
    from .main import add_admin_audit_event
    version = WorkflowPolicyVersion(policy_id=policy.id, version_number=number, name=payload.name,
        states=payload.states, transitions=[transition.model_dump() for transition in payload.transitions], created_by_id=actor.id)
    session.add(version); session.flush()
    add_admin_audit_event(session, actor_id=actor.id, affected_user_id=None, target_type="WORKFLOW_POLICY", target_id=policy.id,
        action="workflow_policy_version_created", changed_values={"version": number, "name": payload.name, "state_count": len(payload.states), "transition_count": len(payload.transitions)})
    return version

def error(code, message, status):
    return HTTPException(status_code=status, detail={"code": code, "message": message})

@router.get("")
def listing(_: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    latest = select(WorkflowPolicyVersion.policy_id, func.max(WorkflowPolicyVersion.version_number).label("number")).group_by(WorkflowPolicyVersion.policy_id).subquery()
    rows = session.execute(select(WorkflowPolicy, WorkflowPolicyVersion).join(latest, latest.c.policy_id == WorkflowPolicy.id).join(WorkflowPolicyVersion, (WorkflowPolicyVersion.policy_id == WorkflowPolicy.id) & (WorkflowPolicyVersion.version_number == latest.c.number)).order_by(WorkflowPolicy.id)).all()
    return [{"id": p.id, "name": v.name, "latest_version_number": v.version_number} for p, v in rows]

@router.get("/{policy_id}")
def detail(policy_id: int, _: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    policy = session.get(WorkflowPolicy, policy_id)
    if policy is None: raise error("policy_not_found", "Workflow policy was not found.", 404)
    return history(session, policy)

@router.post("", status_code=201)
def create(payload: PolicyWrite, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    try:
        policy = WorkflowPolicy(); session.add(policy); session.flush()
        save(session, policy, payload, actor, 1); session.commit()
        return history(session, policy)
    except Exception as exc:
        session.rollback(); raise error("policy_save_failed", "Workflow policy could not be saved.", 500) from exc

@router.post("/{policy_id}/versions", status_code=201)
def create_version(policy_id: int, payload: PolicyWrite, request: Request, actor: User = Depends(require_roles(UserRole.ADMIN)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    try:
        policy = session.execute(select(WorkflowPolicy).where(WorkflowPolicy.id == policy_id).with_for_update()).scalar_one_or_none()
        if policy is None: raise error("policy_not_found", "Workflow policy was not found.", 404)
        number = (session.scalar(select(func.max(WorkflowPolicyVersion.version_number)).where(WorkflowPolicyVersion.policy_id == policy.id)) or 0) + 1
        version = save(session, policy, payload, actor, number); session.commit()
        return version_out(version)
    except HTTPException:
        session.rollback(); raise
    except Exception as exc:
        session.rollback(); raise error("policy_save_failed", "Workflow policy could not be saved.", 500) from exc
