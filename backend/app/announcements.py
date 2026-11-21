"""Secure, centralized announcements for every authenticated dashboard."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import get_current_user, utc_now, validate_mutating_origin
from .database import get_db
from .models import (
    Announcement,
    AnnouncementRead,
    AcademicCycle,
    DefensePanelMember,
    DefenseSchedule,
    Proposal,
    SupervisorAssignment,
    Team,
    User,
    UserRole,
)
from .schemas.announcements import AnnouncementOut, AnnouncementPatch, AnnouncementPermissions, AnnouncementScopeOption, AnnouncementWrite

router = APIRouter(prefix="/api/v1/announcements", tags=["announcements"])

ROLE_VALUES = {role.value for role in UserRole}
LOWER_ROLES = {UserRole.COORDINATOR.value, UserRole.SUPERVISOR.value, UserRole.PANEL_MEMBER.value, UserRole.STUDENT.value}
TARGET_TYPES = {"ALL_USERS", "ALL_GROUPS", "ROLE", "CYCLE", "GROUP", "PROJECT", "ASSIGNED_STUDENTS", "ASSIGNED_PANEL"}
ADMIN_TARGET_TYPES = ["ALL_USERS", "ALL_GROUPS", "ROLE", "CYCLE", "GROUP", "PROJECT", "ASSIGNED_STUDENTS", "ASSIGNED_PANEL"]


def _role(actor: User) -> str:
    return actor.role.value if isinstance(actor.role, UserRole) else str(actor.role)


def _scope_ids(session: Session, actor: User) -> tuple[set[int], set[int], set[int]]:
    """Return assigned team, cycle, and proposal ids for a non-admin recipient."""
    role = _role(actor)
    if role == UserRole.STUDENT.value:
        team_ids = set(session.scalars(select(Team.id).where(Team.shared_user_id == actor.id, Team.status != "dissolved")).all())
    elif role == UserRole.SUPERVISOR.value:
        team_ids = set(session.scalars(select(SupervisorAssignment.team_id).where(SupervisorAssignment.supervisor_id == actor.id, SupervisorAssignment.ended_at.is_(None))).all())
    elif role == UserRole.PANEL_MEMBER.value:
        team_ids = set(session.scalars(select(DefenseSchedule.team_id).join(DefensePanelMember, DefensePanelMember.schedule_id == DefenseSchedule.id).where(DefensePanelMember.user_id == actor.id, DefenseSchedule.status != "CANCELLED")).all())
    else:
        team_ids = set()
    if not team_ids:
        return set(), set(), set()
    cycle_ids = set(session.scalars(select(Team.academic_cycle_id).where(Team.id.in_(team_ids))).all())
    project_ids = set(session.scalars(select(Proposal.id).where(Proposal.team_id.in_(team_ids))).all())
    return team_ids, cycle_ids, project_ids


def _allowed_permissions(session: Session, actor: User) -> AnnouncementPermissions:
    role = _role(actor)
    if role == UserRole.ADMIN.value:
        base = AnnouncementPermissions(can_create=True, can_manage=True, allowed_target_types=ADMIN_TARGET_TYPES, allowed_roles=sorted(ROLE_VALUES))
    elif role == UserRole.COORDINATOR.value:
        base = AnnouncementPermissions(can_create=True, can_manage=False, allowed_target_types=["ROLE", "CYCLE", "GROUP", "PROJECT"], allowed_roles=sorted(LOWER_ROLES))
    elif role == UserRole.SUPERVISOR.value:
        base = AnnouncementPermissions(can_create=True, can_manage=False, allowed_target_types=["ASSIGNED_STUDENTS", "GROUP", "PROJECT"], allowed_roles=[UserRole.STUDENT.value])
    elif role == UserRole.PANEL_MEMBER.value:
        base = AnnouncementPermissions(can_create=True, can_manage=False, allowed_target_types=["ASSIGNED_PANEL", "GROUP", "PROJECT"], allowed_roles=[UserRole.PANEL_MEMBER.value])
    else:
        return AnnouncementPermissions(can_create=False, can_manage=False, allowed_target_types=[], allowed_roles=[])

    if role in {UserRole.ADMIN.value, UserRole.COORDINATOR.value}:
        team_ids = set(session.scalars(select(Team.id).where(Team.status != "dissolved")).all())
        cycle_ids = set(session.scalars(select(AcademicCycle.id)).all())
    else:
        team_ids, cycle_ids, _ = _scope_ids(session, actor)

    cycle_rows = session.scalars(select(AcademicCycle).where(AcademicCycle.id.in_(cycle_ids)).order_by(AcademicCycle.display_name, AcademicCycle.id)).all() if cycle_ids else []
    group_rows = session.execute(select(Team, AcademicCycle).join(AcademicCycle, AcademicCycle.id == Team.academic_cycle_id).where(Team.id.in_(team_ids), Team.status != "dissolved").order_by(AcademicCycle.display_name, Team.group_number, Team.id)).all() if team_ids else []
    project_rows = session.execute(select(Proposal, Team, AcademicCycle).join(Team, Team.id == Proposal.team_id).join(AcademicCycle, AcademicCycle.id == Team.academic_cycle_id).where(Team.id.in_(team_ids), Team.status != "dissolved").order_by(AcademicCycle.display_name, Team.group_number, Proposal.id)).all() if team_ids else []

    base.cycles = [AnnouncementScopeOption(id=row.id, label=f"{row.display_name} ({row.code})", cycle_id=row.id) for row in cycle_rows]
    base.groups = [AnnouncementScopeOption(id=team.id, label=f"Group {team.group_number or team.id} — {cycle.display_name}", cycle_id=team.academic_cycle_id, group_id=team.id) for team, cycle in group_rows]
    base.projects = [AnnouncementScopeOption(id=proposal.id, label=f"Project #{proposal.id} — Group {team.group_number or team.id} — {cycle.display_name}", cycle_id=team.academic_cycle_id, group_id=team.id, project_id=proposal.id) for proposal, team, cycle in project_rows]
    return base


def _assigned_team_ids(session: Session, actor: User) -> set[int]:
    return _scope_ids(session, actor)[0]


def _ensure_reference_scope(session: Session, actor: User, payload: AnnouncementWrite) -> None:
    role = _role(actor)
    permissions = _allowed_permissions(session, actor)
    if not permissions.can_create:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Students cannot create announcements.")
    if payload.target_type not in permissions.allowed_target_types:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This announcement audience is outside your authorization scope.")
    if payload.target_role is not None and payload.target_role not in ROLE_VALUES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "target_role is invalid.")
    if role == UserRole.COORDINATOR.value and payload.target_role == UserRole.ADMIN.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Coordinators cannot target administrators.")
    if role in {UserRole.SUPERVISOR.value, UserRole.PANEL_MEMBER.value} and payload.target_role not in {None, UserRole.STUDENT.value, role}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This role is outside your assigned audience.")

    if payload.cycle_id is not None:
        if session.get(AcademicCycle, payload.cycle_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Academic cycle not found.")
    if payload.group_id is not None:
        group = session.get(Team, payload.group_id)
        if group is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found.")
        if role in {UserRole.SUPERVISOR.value, UserRole.PANEL_MEMBER.value} and payload.group_id not in _assigned_team_ids(session, actor):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only target groups assigned to you.")
    if payload.project_id is not None:
        project = session.get(Proposal, payload.project_id)
        if project is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
        if role in {UserRole.SUPERVISOR.value, UserRole.PANEL_MEMBER.value} and project.team_id not in _assigned_team_ids(session, actor):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only target projects assigned to you.")

    if payload.target_type == "CYCLE" and payload.cycle_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "cycle_id is required for cycle announcements.")
    if payload.target_type in {"GROUP", "ASSIGNED_STUDENTS", "ASSIGNED_PANEL"} and payload.target_type == "GROUP" and payload.group_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "group_id is required for group announcements.")
    if payload.target_type == "PROJECT" and payload.project_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "project_id is required for project announcements.")
    if role == UserRole.ADMIN.value and payload.target_type in {"ASSIGNED_STUDENTS", "ASSIGNED_PANEL"} and payload.group_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "group_id is required for administrator assigned-audience announcements.")


def _active(row: Announcement, now: datetime) -> bool:
    return row.status == "PUBLISHED" and row.published_at is not None and row.published_at <= now and (row.expires_at is None or row.expires_at > now)


def _visible(row: Announcement, actor: User, session: Session, now: datetime, *, include_authored: bool = True) -> bool:
    if not _active(row, now):
        return False
    role = _role(actor)
    # Administrative recipient visibility is intentionally separate from
    # management permissions. Private group, project, cycle, and assigned
    # audience announcements must not appear in an administrator's dashboard
    # feed unless the administrator is an explicit recipient.
    if role == UserRole.ADMIN.value:
        if row.target_type == "ALL_USERS":
            return True
        if row.target_type == "ROLE":
            return row.target_role == UserRole.ADMIN.value
        return False
    if include_authored and row.author_id == actor.id:
        return True
    if row.target_role and row.target_role != role:
        return False
    if row.author_role == UserRole.STUDENT.value:
        return False
    if row.target_type == "ALL_USERS":
        return role in LOWER_ROLES
    if row.target_type == "ALL_GROUPS":
        return role == UserRole.STUDENT.value
    if row.target_type == "ROLE":
        return row.target_role == role
    team_ids, cycle_ids, project_ids = _scope_ids(session, actor)
    if row.target_type == "CYCLE":
        return role == UserRole.COORDINATOR.value or (role in {UserRole.SUPERVISOR.value, UserRole.PANEL_MEMBER.value, UserRole.STUDENT.value} and row.cycle_id in cycle_ids)
    if row.target_type == "GROUP":
        return role == UserRole.COORDINATOR.value or row.group_id in team_ids
    if row.target_type == "PROJECT":
        return role == UserRole.COORDINATOR.value or row.project_id in project_ids
    if row.target_type == "ASSIGNED_STUDENTS":
        if role != UserRole.STUDENT.value:
            return False
        author_team_ids = _scope_ids(session, session.get(User, row.author_id))[0] if session.get(User, row.author_id) is not None else set()
        return (row.group_id in team_ids if row.group_id is not None else bool(author_team_ids.intersection(team_ids)))
    if row.target_type == "ASSIGNED_PANEL":
        if role != UserRole.PANEL_MEMBER.value:
            return False
        author = session.get(User, row.author_id)
        author_team_ids = _scope_ids(session, author)[0] if author is not None else set()
        return (row.group_id in team_ids if row.group_id is not None else bool(author_team_ids.intersection(team_ids)))
    return False


def _read_at(session: Session, announcement_id: int, user_id: int):
    return session.scalar(select(AnnouncementRead.read_at).where(AnnouncementRead.announcement_id == announcement_id, AnnouncementRead.user_id == user_id))


def _display_status(row: Announcement, now: datetime) -> str:
    if row.status == "PUBLISHED" and row.expires_at is not None and row.expires_at <= now:
        return "EXPIRED"
    return row.status


def _serialize(row: Announcement, author: User, actor: User, session: Session, now: datetime, *, admin_view: bool = False) -> dict:
    read_at = _read_at(session, row.id, actor.id)
    owner = row.author_id == actor.id
    can_edit = _role(actor) == UserRole.ADMIN.value or (owner and row.status not in {"ARCHIVED", "EXPIRED"})
    can_archive = _role(actor) == UserRole.ADMIN.value or (owner and row.status == "PUBLISHED")
    return AnnouncementOut(
        id=row.id, title=row.title, message=row.message, author_id=row.author_id, author_name=author.full_name,
        author_role=row.author_role, priority=row.priority, status=_display_status(row, now), target_type=row.target_type,
        target_role=row.target_role, cycle_id=row.cycle_id, group_id=row.group_id, project_id=row.project_id,
        published_at=row.published_at, expires_at=row.expires_at, created_at=row.created_at, updated_at=row.updated_at,
        archived_at=row.archived_at, read_at=read_at, is_read=read_at is not None, can_edit=can_edit, can_archive=can_archive,
    ).model_dump(mode="json")


def _rows(session: Session, actor: User, *, include_all: bool = False, author_only: bool = False, include_archived: bool = False, limit: int = 50) -> list[dict]:
    now = utc_now()
    max_rows = min(max(limit, 1), 100)
    query = select(Announcement, User).join(User, User.id == Announcement.author_id).order_by(Announcement.published_at.desc().nullslast(), Announcement.created_at.desc(), Announcement.id.desc())
    if author_only:
        query = query.where(Announcement.author_id == actor.id)
    elif include_all:
        if _role(actor) != UserRole.ADMIN.value:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access is required.")
        # The admin page is still a management surface, but it must not become
        # a feed of private announcements created for another portal. Keep only
        # announcements addressed to administrators or to the whole platform.
        query = query.where(
            (Announcement.author_id == actor.id)
            | (Announcement.target_type == "ALL_USERS")
            | ((Announcement.target_type == "ROLE") & (Announcement.target_role == UserRole.ADMIN.value))
        )
        if not include_archived:
            query = query.where(Announcement.status != "ARCHIVED")
    else:
        query = query.where(Announcement.status == "PUBLISHED")
    output = []
    for row, author in session.execute(query).all():
        if include_all or author_only:
            if not include_all and row.author_id != actor.id:
                continue
            output.append(_serialize(row, author, actor, session, now, admin_view=include_all))
        elif _visible(row, actor, session, now):
            output.append(_serialize(row, author, actor, session, now))
        if len(output) >= max_rows:
            break
    return output


def _audit(session: Session, actor: User, action: str, announcement_id: int, changed_values: dict) -> None:
    from .models import AdminAuditEvent
    session.add(AdminAuditEvent(actor_id=actor.id, affected_user_id=None, target_type="ANNOUNCEMENT", target_id=announcement_id, action=action, changed_values=changed_values))


@router.get("/permissions", response_model=AnnouncementPermissions)
def permissions(actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    return _allowed_permissions(session, actor)


@router.get("/latest")
def latest(limit: int = Query(default=5, ge=1, le=10), actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    return _rows(session, actor, limit=limit)


@router.get("/unread-count")
def unread_count(actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    return {"count": sum(1 for item in _rows(session, actor, limit=100) if not item["is_read"])}


@router.get("/mine")
def mine(limit: int = Query(default=100, ge=1, le=100), actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    return _rows(session, actor, author_only=True, limit=limit)


@router.get("/admin")
def admin_list(include_archived: bool = False, limit: int = Query(default=100, ge=1, le=100), actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    return _rows(session, actor, include_all=True, include_archived=include_archived, limit=limit)


@router.get("")
def visible_announcements(limit: int = Query(default=50, ge=1, le=100), actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    return _rows(session, actor, limit=limit)


@router.get("/{announcement_id}")
def announcement_detail(announcement_id: int, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    row_author = session.execute(select(Announcement, User).join(User, User.id == Announcement.author_id).where(Announcement.id == announcement_id)).one_or_none()
    if row_author is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found.")
    row, author = row_author
    now = utc_now()
    if not _visible(row, actor, session, now):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found.")
    return _serialize(row, author, actor, session, now, admin_view=False)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_announcement(payload: AnnouncementWrite, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    _ensure_reference_scope(session, actor, payload)
    row = Announcement(
        title=payload.title, message=payload.message, author_id=actor.id, author_role=_role(actor), priority=payload.priority,
        status="DRAFT", target_type=payload.target_type, target_role=payload.target_role, cycle_id=payload.cycle_id,
        group_id=payload.group_id, project_id=payload.project_id, published_at=payload.published_at, expires_at=payload.expires_at,
    )
    session.add(row)
    session.flush()
    _audit(session, actor, "announcement_created", row.id, {"target_type": row.target_type, "priority": row.priority})
    session.commit()
    session.refresh(row)
    return _serialize(row, actor, actor, session, utc_now())


@router.patch("/{announcement_id}")
def update_announcement(announcement_id: int, payload: AnnouncementPatch, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(Announcement, announcement_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found.")
    if _role(actor) != UserRole.ADMIN.value and row.author_id != actor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You may only edit announcements you created.")
    if row.status == "ARCHIVED":
        raise HTTPException(status.HTTP_409_CONFLICT, "Archived announcements cannot be edited.")
    values = {key: getattr(row, key) for key in ("title", "message", "priority", "target_type", "target_role", "cycle_id", "group_id", "project_id", "published_at", "expires_at")}
    for key in payload.model_fields_set:
        values[key] = getattr(payload, key)
    normalized = AnnouncementWrite.model_validate(values)
    _ensure_reference_scope(session, actor, normalized)
    row.title, row.message, row.priority = normalized.title, normalized.message, normalized.priority
    row.target_type, row.target_role = normalized.target_type, normalized.target_role
    row.cycle_id, row.group_id, row.project_id = normalized.cycle_id, normalized.group_id, normalized.project_id
    row.published_at, row.expires_at = normalized.published_at, normalized.expires_at
    session.flush()
    _audit(session, actor, "announcement_updated", row.id, {"target_type": row.target_type, "priority": row.priority})
    session.commit()
    author = session.get(User, row.author_id)
    return _serialize(row, author or actor, actor, session, utc_now())


@router.post("/{announcement_id}/publish")
def publish_announcement(announcement_id: int, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(Announcement, announcement_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found.")
    if _role(actor) != UserRole.ADMIN.value and row.author_id != actor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You may only publish announcements you created.")
    if row.status == "ARCHIVED":
        raise HTTPException(status.HTTP_409_CONFLICT, "Archived announcements cannot be published.")
    now = utc_now()
    if row.expires_at is not None and row.expires_at <= now:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The announcement expiry must be in the future.")
    row.status, row.published_at, row.archived_at = "PUBLISHED", row.published_at or now, None
    session.flush()
    _audit(session, actor, "announcement_published", row.id, {})
    session.commit()
    author = session.get(User, row.author_id)
    return _serialize(row, author or actor, actor, session, now)


@router.post("/{announcement_id}/archive")
def archive_announcement(announcement_id: int, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(Announcement, announcement_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found.")
    if _role(actor) != UserRole.ADMIN.value and row.author_id != actor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You may only archive announcements you created.")
    row.status, row.archived_at = "ARCHIVED", utc_now()
    session.flush()
    _audit(session, actor, "announcement_archived", row.id, {})
    session.commit()
    author = session.get(User, row.author_id)
    return _serialize(row, author or actor, actor, session, utc_now())


@router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_announcement(announcement_id: int, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(Announcement, announcement_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found.")
    if _role(actor) != UserRole.ADMIN.value and (row.author_id != actor.id or row.status not in {"DRAFT", "ARCHIVED"}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an administrator can delete this announcement.")
    _audit(session, actor, "announcement_deleted", row.id, {})
    session.delete(row)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This announcement cannot be deleted.") from error


@router.post("/{announcement_id}/read")
def mark_read(announcement_id: int, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(Announcement, announcement_id)
    if row is None or not _visible(row, actor, session, utc_now()):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found.")
    marker = session.scalar(select(AnnouncementRead).where(AnnouncementRead.announcement_id == announcement_id, AnnouncementRead.user_id == actor.id).with_for_update())
    if marker is None:
        marker = AnnouncementRead(announcement_id=announcement_id, user_id=actor.id, read_at=utc_now())
        session.add(marker)
    else:
        marker.read_at = utc_now()
    session.commit()
    return {"id": announcement_id, "read_at": marker.read_at}


@router.delete("/{announcement_id}/read")
def mark_unread(announcement_id: int, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(Announcement, announcement_id)
    if row is None or not _visible(row, actor, session, utc_now()):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found.")
    session.execute(delete(AnnouncementRead).where(AnnouncementRead.announcement_id == announcement_id, AnnouncementRead.user_id == actor.id))
    session.commit()
    return {"id": announcement_id, "read_at": None}
