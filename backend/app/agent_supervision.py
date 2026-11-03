"""Controlled supervision-agent planning and approval workflow."""
from datetime import datetime, timedelta
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .auth import get_current_user, require_roles, utc_now, validate_mutating_origin
from .database import get_db
from .models import (AcademicCycle, ProjectMilestone, ProjectTask, SupervisorAssignment, SupervisorRequest,
                      SupervisorRequestMessage, SupervisorRequestStatus, SupervisionAgentRun, Team, TeamMember, User, UserRole)
from .ai_provider import SupervisionPlanPayload, run_ai_json

router = APIRouter(prefix="/api/v1/agent-supervision")
WRITE = (UserRole.STUDENT, UserRole.SUPERVISOR, UserRole.COORDINATOR, UserRole.ADMIN)

class Approval(BaseModel):
    approved: bool
    comment: str | None = Field(default=None, max_length=2000)

def _team(session: Session, team_id: int) -> Team:
    row = session.get(Team, team_id)
    if row is None: raise HTTPException(404, "Team was not found.")
    return row

def _access(session: Session, team_id: int, actor: User, supervisor_write: bool = False) -> Team:
    team = _team(session, team_id)
    if actor.role in (UserRole.ADMIN, UserRole.COORDINATOR): return team
    assignment = session.scalar(select(SupervisorAssignment).where(SupervisorAssignment.team_id == team_id, SupervisorAssignment.ended_at.is_(None)))
    if actor.role == UserRole.SUPERVISOR and assignment and assignment.supervisor_id == actor.id: return team
    if actor.role == UserRole.STUDENT and session.scalar(select(TeamMember.id).where(TeamMember.team_id == team_id, TeamMember.is_active.is_(True), (TeamMember.registration_number == actor.registration_number) | (TeamMember.university_email == actor.email))): return team
    raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not authorized for this team.")

def _out(run: SupervisionAgentRun) -> dict:
    return {"id": run.id, "team_id": run.team_id, "state": run.state, "approval_status": run.approval_status, "plan": run.plan, "tool_calls": run.tool_calls, "result": run.result, "error": run.error, "approved_by_id": run.approved_by_id, "approved_at": run.approved_at, "created_at": run.created_at, "updated_at": run.updated_at}

def _accepted_proposal(session: Session, team_id: int) -> SupervisorRequest | None:
    return session.scalar(select(SupervisorRequest).where(SupervisorRequest.team_id == team_id, SupervisorRequest.status == SupervisorRequestStatus.ACCEPTED.value).order_by(SupervisorRequest.id.desc()))

@router.post("/{team_id}/runs", status_code=201)
def start_run(team_id: int, request: Request, actor: User = Depends(require_roles(*WRITE)), session: Session = Depends(get_db)):
    validate_mutating_origin(request); team = _access(session, team_id, actor)
    if session.scalar(select(SupervisionAgentRun.id).where(SupervisionAgentRun.team_id == team.id, SupervisionAgentRun.state.in_(("PLANNING", "WAITING_FOR_APPROVAL", "EXECUTING")))):
        raise HTTPException(409, "An agent run is already active for this team.")
    proposal = _accepted_proposal(session, team.id)
    if proposal is None: raise HTTPException(409, "An accepted proposal is required before generating a plan.")
    cycle = session.get(AcademicCycle, team.academic_cycle_id)
    assignment = session.scalar(select(SupervisorAssignment).where(SupervisorAssignment.team_id == team.id, SupervisorAssignment.ended_at.is_(None)))
    objectives = proposal.objectives or "Complete the approved project objectives"
    methodology = proposal.methodology or "Follow the approved methodology"
    provider = asyncio.run(run_ai_json("Objectives:\n" + objectives + "\nMethodology:\n" + methodology, SupervisionPlanPayload, model_kind="agent", rate_key=f"agent:{actor.id}:{team.id}"))
    if provider.get("status") in ("AVAILABLE", "COMPLETED"):
        plan = {"source": "AI", "confidence": provider["payload"]["confidence"], "milestones": provider["payload"]["milestones"], "metadata": {key: provider.get(key) for key in ("provider", "model", "timestamp", "request_id", "http_status", "latency_ms", "retry_count")}}
    else:
        plan = {"source": "DETERMINISTIC_FALLBACK", "confidence": 0.65, "fallback_reason": provider.get("fallback_reason"), "milestones": [{"title": "Plan and design", "description": objectives, "due_at": (utc_now() + timedelta(days=14)).isoformat(), "tasks": [{"title": "Define implementation tasks", "description": methodology, "due_at": (utc_now() + timedelta(days=7)).isoformat(), "dependencies": []}]}, {"title": "Implementation and validation", "description": "Implement and validate the approved objectives.", "due_at": (utc_now() + timedelta(days=42)).isoformat(), "tasks": [{"title": "Validate outcomes", "description": "Record evidence against the approved objectives.", "due_at": (utc_now() + timedelta(days=35)).isoformat(), "dependencies": ["Define implementation tasks"]}]},], "cycle_id": cycle.id if cycle else None, "supervisor_id": assignment.supervisor_id if assignment else None}
    run = SupervisionAgentRun(team_id=team.id, proposal_request_id=proposal.id, created_by_id=actor.id, state="WAITING_FOR_APPROVAL", approval_status="PENDING", plan=plan, tool_calls=[{"tool": "read_approved_proposal", "verified": True}, {"tool": "read_assignment", "verified": assignment is not None}, {"tool": "read_cycle_deadlines", "verified": cycle is not None}], result={})
    session.add(run); session.flush(); session.commit(); session.refresh(run); return _out(run)

@router.get("/{team_id}/runs")
def list_runs(team_id: int, actor: User = Depends(require_roles(*WRITE)), session: Session = Depends(get_db)):
    _access(session, team_id, actor); return [_out(row) for row in session.scalars(select(SupervisionAgentRun).where(SupervisionAgentRun.team_id == team_id).order_by(SupervisionAgentRun.id.desc())).all()]

@router.post("/runs/{run_id}/approval")
def approve_run(run_id: int, payload: Approval, request: Request, actor: User = Depends(require_roles(UserRole.SUPERVISOR)), session: Session = Depends(get_db)):
    validate_mutating_origin(request); run = session.get(SupervisionAgentRun, run_id)
    if run is None: raise HTTPException(404, "Agent run was not found.")
    _access(session, run.team_id, actor)
    if run.state != "WAITING_FOR_APPROVAL": raise HTTPException(409, "This run is not awaiting approval.")
    run.approval_status = "APPROVED" if payload.approved else "REJECTED"; run.approved_by_id = actor.id; run.approved_at = utc_now(); run.state = "IDLE" if not payload.approved else "WAITING_FOR_APPROVAL"; run.result = {"approval_comment": payload.comment}; session.commit(); session.refresh(run); return _out(run)

@router.post("/runs/{run_id}/execute")
def execute_run(run_id: int, request: Request, actor: User = Depends(require_roles(UserRole.SUPERVISOR)), session: Session = Depends(get_db)):
    validate_mutating_origin(request); run = session.get(SupervisionAgentRun, run_id)
    if run is None: raise HTTPException(404, "Agent run was not found.")
    _access(session, run.team_id, actor)
    if run.approval_status != "APPROVED": raise HTTPException(409, "Supervisor approval is required before execution.")
    run.state = "EXECUTING"; session.flush(); created = []
    try:
        for milestone in run.plan.get("milestones", []):
            existing = session.scalar(select(ProjectMilestone).where(ProjectMilestone.team_id == run.team_id, ProjectMilestone.title == milestone["title"]))
            due_at = datetime.fromisoformat(milestone["due_at"]) if milestone.get("due_at") else None
            m = existing or ProjectMilestone(team_id=run.team_id, created_by_id=actor.id, title=milestone["title"], description=milestone.get("description"), due_at=due_at)
            if existing is None: session.add(m); session.flush()
            for task in milestone.get("tasks", []):
                if session.scalar(select(ProjectTask.id).where(ProjectTask.team_id == run.team_id, ProjectTask.title == task["title"])): continue
                task_due = datetime.fromisoformat(task["due_at"]) if task.get("due_at") else None
                session.add(ProjectTask(team_id=run.team_id, milestone_id=m.id, created_by_id=actor.id, title=task["title"], description=task.get("description"), due_at=task_due)); created.append(task["title"])
        run.state = "COMPLETED"; run.result = {"created_tasks": created, "verified": True}; session.commit(); session.refresh(run); return _out(run)
    except Exception as exc:
        session.rollback(); run = session.get(SupervisionAgentRun, run_id); run.state = "FAILED"; run.error = str(exc)[:500]; session.commit(); raise HTTPException(500, "Agent execution failed; manual progress remains available.") from exc

@router.post("/runs/{run_id}/reminder/approve")
def approve_reminder(run_id: int, payload: Approval, request: Request, actor: User = Depends(require_roles(UserRole.SUPERVISOR)), session: Session = Depends(get_db)):
    validate_mutating_origin(request); run = session.get(SupervisionAgentRun, run_id)
    if run is None: raise HTTPException(404, "Agent run was not found.")
    _access(session, run.team_id, actor)
    if not payload.approved: run.result = {**run.result, "reminder_status": "REJECTED"}; session.commit(); return _out(run)
    proposal = session.get(SupervisorRequest, run.proposal_request_id) if run.proposal_request_id else None
    if proposal is None: raise HTTPException(409, "No proposal conversation is available for this reminder.")
    body = payload.comment or "Please review your overdue project tasks and update progress."
    message = SupervisorRequestMessage(request_id=proposal.id, sender_id=actor.id, body=body); session.add(message); session.flush(); run.result = {**run.result, "reminder_status": "SENT", "message_id": message.id, "verified": True}; session.commit(); session.refresh(run); return _out(run)
