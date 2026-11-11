"""Supervisor-owned group workspace assembled from persisted workflow records."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .auth import require_roles
from .database import get_db
from .models import (AcademicCycle, CollaborationChannel, DocumentSubmission,
                     DocumentUploadRequirement, SupervisorAssignment, SupervisorRequest,
                     Team, TeamMember, User, UserRole)
from .document_requirements import _submission_out
from .supervisor_requests import DecisionAction, _out, decide_request
from .collaboration_channels import collaboration_messages, send_collaboration_message, MessageWrite

router = APIRouter(prefix="/api/v1/supervisor", tags=["supervisor-workspace"])
supervisor = require_roles(UserRole.SUPERVISOR)


def owned_request(db, actor, request_id):
    row = db.scalar(select(SupervisorRequest).where(SupervisorRequest.id == request_id, SupervisorRequest.supervisor_id == actor.id, SupervisorRequest.status != "DRAFT"))
    if row is None:
        raise HTTPException(404, "Supervision request was not found.")
    return row


def owned_group(db, actor, group_id):
    assignment = db.scalar(select(SupervisorAssignment).where(SupervisorAssignment.team_id == group_id, SupervisorAssignment.supervisor_id == actor.id, SupervisorAssignment.ended_at.is_(None)))
    group = db.get(Team, group_id) if assignment else None
    if group is None:
        raise HTTPException(404, "Assigned group was not found.")
    return group, assignment


def workspace(db, actor, group, assignment=None, request_row=None):
    account = db.get(User, group.shared_user_id)
    cycle = db.get(AcademicCycle, group.academic_cycle_id)
    members = db.scalars(select(TeamMember).where(TeamMember.team_id == group.id).order_by(TeamMember.is_creator.desc(), TeamMember.id)).all()
    leader = next((m for m in members if m.is_creator), members[0] if members else None)
    if request_row is None:
        request_row = db.scalar(select(SupervisorRequest).where(SupervisorRequest.team_id == group.id, SupervisorRequest.supervisor_id == actor.id, SupervisorRequest.status != "DRAFT").order_by((SupervisorRequest.assignment_id == assignment.id).desc().nulls_last() if assignment else SupervisorRequest.updated_at.desc(), SupervisorRequest.updated_at.desc(), SupervisorRequest.id.desc()))
    request_data = _out(db, request_row) if request_row else None
    document = request_data.get("document") if request_data else None
    extracted = document.get("extracted_fields", {}) if document else {}
    def value(*names):
        for name in names:
            item = extracted.get(name)
            if isinstance(item, dict) and item.get("display"):
                return item["display"]
            if isinstance(item, str) and item:
                return item
            if isinstance(item, list) and item:
                return "\n".join(str(part.get("display", "")) if isinstance(part, dict) else str(part) for part in item)
        return None
    # Pending requests can inspect their own group's progress without granting a
    # general group URL permission. The selector is derived from the owned request.
    from .models import ProjectMilestone, ProjectTask, SupervisionMeeting
    from .project_workflow import _milestone_out, _task_out, _health
    milestones = db.scalars(select(ProjectMilestone).where(ProjectMilestone.team_id == group.id).order_by(ProjectMilestone.id)).all()
    tasks = db.scalars(select(ProjectTask).where(ProjectTask.team_id == group.id).order_by(ProjectTask.id)).all()
    meetings = db.scalars(select(SupervisionMeeting).where(SupervisionMeeting.team_id == group.id, SupervisionMeeting.supervisor_id == actor.id).order_by(SupervisionMeeting.held_at.desc())).all()
    progress = {"milestones": [_milestone_out(m) for m in milestones], "tasks": [_task_out(t) for t in tasks], "meetings": [{"id": m.id, "held_at": m.held_at, "minutes": m.minutes, "decisions": m.decisions, "created_at": m.created_at} for m in meetings], "health": _health(milestones, tasks)}
    requirements = db.scalars(select(DocumentUploadRequirement).where(DocumentUploadRequirement.academic_cycle_id == group.academic_cycle_id, DocumentUploadRequirement.status.in_(["PUBLISHED", "CLOSED", "ACTIVE", "ARCHIVED"]), or_(DocumentUploadRequirement.assigned_group_id.is_(None), DocumentUploadRequirement.assigned_group_id == group.id), or_(DocumentUploadRequirement.assigned_user_id.is_(None), DocumentUploadRequirement.assigned_user_id == account.id)).order_by(DocumentUploadRequirement.due_at)).all()
    documents = []
    activity = [group.updated_at]
    for req in requirements:
        rows = db.scalars(select(DocumentSubmission).where(DocumentSubmission.requirement_id == req.id, or_(DocumentSubmission.group_id == group.id, (DocumentSubmission.group_id.is_(None)) & (DocumentSubmission.student_id == account.id)))).all()
        submissions = [_submission_out(row, db).model_dump() for row in rows]
        for sub in submissions:
            activity.extend(v["uploaded_at"] for v in sub["versions"])
        documents.append({"id": req.id, "title": req.title, "allowed_file_types": req.allowed_file_types, "due_at": req.due_at, "status": req.status, "submissions": submissions})
    if request_row:
        activity.append(request_row.updated_at)
    activity.extend(m.updated_at for m in [*milestones, *tasks])
    activity.extend(m.created_at for m in meetings)
    completion_items = tasks or milestones
    completion = round(sum(m.completion_percent for m in completion_items) / len(completion_items)) if completion_items else None
    proposal = None
    if request_row:
        proposal = {"id": request_row.id, "title": request_row.title or value("title"), "abstract": request_row.summary or value("abstract", "purpose"), "problem_statement": request_row.problem_statement or value("problem_statement", "problem"), "objectives": request_row.objectives or value("objectives"), "scope": request_row.scope or value("scope"), "features": value("features", "proposed_features", "proposed_solution"), "domain": value("domain", "topic"), "technologies": value("technologies", "technologies_used"), "status": request_row.status, "submitted_at": request_row.submitted_at, "updated_at": request_row.updated_at, "version": document.get("version") if document else request_row.revision, "document": document, "comments": request_data.get("status_history", [])}
    project = {"title": proposal["title"], "description": proposal["abstract"], "domain": proposal["domain"], "technologies": proposal["technologies"], "status": "COMPLETED" if completion == 100 else "IN_PROGRESS", "phase": milestones[-1].title if milestones else None, "completion_percentage": completion, "completion_basis": "Average task completion" if tasks else "Average milestone completion", "last_progress_update": max([m.updated_at for m in [*milestones, *tasks]], default=None), "risks": [t["title"] for t in progress["tasks"] if t["overdue"]]} if proposal and (assignment or completion_items) else None
    channel = db.scalar(select(CollaborationChannel).where(CollaborationChannel.assignment_id == assignment.id, CollaborationChannel.supervisor_id == actor.id, CollaborationChannel.status == "ACTIVE")) if assignment else None
    if channel:
        activity.append(channel.updated_at)
    return {"group": {"id": group.id, "name": f"{leader.full_name}'s Group" if leader else account.full_name, "email": account.email, "status": group.status.upper() if account.is_active else "INACTIVE", "created_at": group.created_at, "updated_at": group.updated_at, "last_activity_at": max(activity), "academic_cycle": {"id": cycle.id, "name": cycle.display_name, "year": cycle.academic_year, "session": cycle.session}}, "members": [{"id": m.id, "full_name": m.full_name, "registration_number": m.registration_number, "email": m.university_email, "designation": "Leader" if m.is_creator else "Member", "is_active": m.is_active, "account_active": account.is_active} for m in members], "supervisor": {"id": actor.id, "name": actor.full_name, "email": actor.email}, "assignment": {"id": assignment.id, "status": "ACTIVE", "assigned_at": assignment.created_at, "request_id": request_row.id if request_row and request_row.assignment_id == assignment.id else None} if assignment else None, "proposal": proposal, "project": project, "documents": documents, "progress": progress, "conversation": {"channel_id": channel.id, "assignment_id": channel.assignment_id, "group_id": group.id} if channel else None}


@router.get("/assigned-groups")
def assigned_groups(actor: User = Depends(supervisor), db: Session = Depends(get_db)):
    rows = db.scalars(select(SupervisorAssignment).where(SupervisorAssignment.supervisor_id == actor.id, SupervisorAssignment.ended_at.is_(None)).order_by(SupervisorAssignment.created_at.desc())).all()
    return [workspace(db, actor, db.get(Team, row.team_id), row) for row in rows]


@router.get("/groups/{group_id}")
def group_detail(group_id: int, actor: User = Depends(supervisor), db: Session = Depends(get_db)):
    group, assignment = owned_group(db, actor, group_id)
    return workspace(db, actor, group, assignment)


@router.get("/groups/{group_id}/members")
@router.get("/groups/{group_id}/proposal")
@router.get("/groups/{group_id}/project")
@router.get("/groups/{group_id}/documents")
@router.get("/groups/{group_id}/progress")
def group_section(group_id: int, request: Request, actor: User = Depends(supervisor), db: Session = Depends(get_db)):
    return group_detail(group_id, actor, db)[request.url.path.rsplit("/", 1)[-1]]


@router.get("/requests")
def requests(actor: User = Depends(supervisor), db: Session = Depends(get_db), include_history: bool = False):
    statuses = ["SUBMITTED", "CHANGES_REQUESTED", "ACCEPTED", "REJECTED", "WITHDRAWN"] if include_history else ["SUBMITTED", "CHANGES_REQUESTED"]
    rows = db.scalars(select(SupervisorRequest).where(SupervisorRequest.supervisor_id == actor.id, SupervisorRequest.status.in_(statuses)).order_by(SupervisorRequest.updated_at.desc())).all()
    return [request_detail(row.id, actor, db) for row in rows]


@router.get("/requests/{request_id}")
def request_detail(request_id: int, actor: User = Depends(supervisor), db: Session = Depends(get_db)):
    row = owned_request(db, actor, request_id)
    data = _out(db, row)
    group = db.get(Team, row.team_id) if row.team_id else None
    assignment = db.scalar(select(SupervisorAssignment).where(SupervisorAssignment.team_id == group.id, SupervisorAssignment.supervisor_id == actor.id, SupervisorAssignment.ended_at.is_(None))) if group else None
    data["workspace"] = workspace(db, actor, group, assignment, row) if group else None
    return data


class DecisionInput(BaseModel):
    revision: int = Field(gt=0)
    comment: str | None = Field(default=None, max_length=2000)


@router.post("/requests/{request_id}/accept")
@router.post("/requests/{request_id}/reject")
@router.post("/requests/{request_id}/request-changes")
def decision(request_id: int, payload: DecisionInput, request: Request, actor: User = Depends(supervisor), db: Session = Depends(get_db)):
    action = request.url.path.rsplit("/", 1)[-1].replace("-", "_")
    return decide_request(request_id, DecisionAction(action=action, **payload.model_dump()), request, actor, db)


def group_channel(db, actor, group_id):
    _, assignment = owned_group(db, actor, group_id)
    channel = db.scalar(select(CollaborationChannel).where(CollaborationChannel.assignment_id == assignment.id, CollaborationChannel.supervisor_id == actor.id, CollaborationChannel.status == "ACTIVE"))
    if channel is None:
        raise HTTPException(404, "Group discussion is not available yet.")
    return channel


@router.get("/groups/{group_id}/conversation")
def conversation(group_id: int, actor: User = Depends(supervisor), db: Session = Depends(get_db)):
    channel = group_channel(db, actor, group_id)
    return {"group_id": group_id, "assignment_id": channel.assignment_id, "channel_id": channel.id, "messages": collaboration_messages(channel.id, actor, db)}


@router.post("/groups/{group_id}/conversation", status_code=201)
def send_message(group_id: int, payload: MessageWrite, request: Request, actor: User = Depends(supervisor), db: Session = Depends(get_db)):
    channel = group_channel(db, actor, group_id)
    return send_collaboration_message(channel.id, payload, request, actor, db)
