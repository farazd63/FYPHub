"""Generic review API for requirement submissions.

The existing proposal review API remains available for historical proposal
records. This adapter uses the same frontend review contract but scopes every
record to a generic document submission *and* its exact uploaded version.
"""

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles, validate_mutating_origin
from .database import get_db
from .document_requirements import _submission_group, _supervisor_can_review
from .models import (
    DocumentReviewAnnotation,
    DocumentReviewFeedback,
    DocumentReviewFeedbackMessage,
    DocumentSubmission,
    DocumentSubmissionVersion,
    DocumentUploadRequirement,
    Team,
    User,
    UserRole,
)
from .notification_service import notify, team_student_ids, team_supervisor_ids


router = APIRouter(prefix="/api/v1/document-review", tags=["document-review"])
WRITERS = (UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.COORDINATOR, UserRole.PLATFORM_ADMIN)


class FeedbackWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: int = Field(gt=0)
    version_id: int = Field(gt=0)
    feedback_level: str = Field(default="FULL_DOCUMENT", max_length=24)
    feedback_type: Literal["GENERAL_COMMENT", "CORRECTION", "EDITING_SUGGESTION", "FORMAL_REVISION", "FORMAL_REVISION_REQUEST", "CLARIFICATION_REQUEST"] = "GENERAL_COMMENT"
    correction_action: str = Field(default="NONE", max_length=24)
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=12000)
    suggested_text: str | None = Field(default=None, max_length=12000)
    selected_text: str | None = Field(default=None, max_length=12000)
    location: dict[str, Any] = Field(default_factory=dict)
    destination_location: dict[str, Any] | None = None
    expected_outcome: str | None = Field(default=None, max_length=12000)
    is_mandatory: bool = False
    priority: str = Field(default="MEDIUM", max_length=16)
    due_at: datetime | None = None
    publish: bool = False


class FeedbackUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1, max_length=12000)
    feedback_level: str | None = Field(default=None, max_length=24)
    feedback_type: str | None = Field(default=None, max_length=32)
    correction_action: str | None = Field(default=None, max_length=24)
    suggested_text: str | None = Field(default=None, max_length=12000)
    selected_text: str | None = Field(default=None, max_length=12000)
    location: dict[str, Any] | None = None
    destination_location: dict[str, Any] | None = None
    expected_outcome: str | None = Field(default=None, max_length=12000)
    is_mandatory: bool | None = None
    priority: str | None = Field(default=None, max_length=16)
    due_at: datetime | None = None


class MessageWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=12000)


class AnnotationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: int = Field(gt=0)
    version_id: int = Field(gt=0)
    annotation_type: Literal["HIGHLIGHT", "UNDERLINE", "STRIKETHROUGH", "PEN", "RECTANGLE", "CIRCLE", "ARROW", "TEXT_BOX", "STICKY_NOTE", "EDITING_SUGGESTION", "REVISION_REQUEST"]
    page_number: int = Field(gt=0)
    geometry: dict[str, Any] = Field(default_factory=dict)
    drawing: dict[str, Any] = Field(default_factory=dict)
    selected_text: str | None = Field(default=None, max_length=12000)
    content: str | None = Field(default=None, max_length=12000)
    suggested_text: str | None = Field(default=None, max_length=12000)
    color: str = Field(default="#F5C542", pattern=r"^#[0-9A-Fa-f]{6}$")
    stroke_width: float = Field(default=2, ge=1, le=16)
    publication_status: Literal["DRAFT", "PUBLISHED"] = "DRAFT"
    feedback_id: int | None = Field(default=None, gt=0)


def _error(message: str, code: str = "document_review_error", code_status: int = 422) -> HTTPException:
    return HTTPException(code_status, {"code": code, "message": message})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _access(session: Session, actor: User, submission_id: int, *, version_id: int | None = None, write: bool = False, published_only: bool = False) -> tuple[DocumentSubmission, DocumentUploadRequirement, Team, DocumentSubmissionVersion]:
    submission = session.get(DocumentSubmission, submission_id)
    if submission is None:
        raise _error("The document submission was not found.", "submission_not_found", 404)
    requirement = session.get(DocumentUploadRequirement, submission.requirement_id)
    group = _submission_group(submission, session, requirement.academic_cycle_id if requirement else None)
    if requirement is None or group is None:
        raise _error("The submission is not connected to an active group.", "review_scope_missing", 403)
    authorized_supervisor = _supervisor_can_review(submission, requirement, actor, session)
    same_student_group = actor.role == UserRole.STUDENT and (submission.student_id == actor.id or submission.group_id == group.id)
    privileged_read = actor.role in {UserRole.ADMIN, UserRole.COORDINATOR, UserRole.PLATFORM_ADMIN}
    if write:
        if not authorized_supervisor and actor.role not in {UserRole.ADMIN, UserRole.PLATFORM_ADMIN}:
            raise _error("Only the assigned supervisor can edit this review.", "review_access_denied", 403)
    elif not (authorized_supervisor or privileged_read or same_student_group):
        raise _error("You are not authorized to access this document review.", "review_access_denied", 403)
    version_query = select(DocumentSubmissionVersion).where(DocumentSubmissionVersion.submission_id == submission.id)
    if version_id is not None:
        version_query = version_query.where(DocumentSubmissionVersion.id == version_id)
    version = session.scalar(version_query)
    if version is None or (actor.role == UserRole.STUDENT and version.student_hidden_at is not None):
        raise _error("The selected submission version was not found.", "version_not_found", 404)
    return submission, requirement, group, version


def _message_out(session: Session, row: DocumentReviewFeedbackMessage) -> dict[str, Any]:
    sender = session.get(User, row.sender_id)
    return {"id": row.id, "sender_id": row.sender_id, "sender_name": sender.full_name if sender else "User", "body": row.body, "created_at": row.created_at}


def _feedback_out(session: Session, row: DocumentReviewFeedback) -> dict[str, Any]:
    author = session.get(User, row.author_id)
    messages = session.scalars(select(DocumentReviewFeedbackMessage).where(DocumentReviewFeedbackMessage.feedback_id == row.id, DocumentReviewFeedbackMessage.deleted_at.is_(None)).order_by(DocumentReviewFeedbackMessage.created_at, DocumentReviewFeedbackMessage.id)).all()
    return {
        "id": row.id,
        "submission_id": row.submission_id,
        "version_id": row.version_id,
        "author": {"id": row.author_id, "name": author.full_name if author else "Supervisor"},
        "marker_number": row.marker_number,
        "feedback_level": row.feedback_level,
        "feedback_type": row.feedback_type,
        "correction_action": row.correction_action,
        "title": row.title,
        "content": row.content,
        "suggested_text": row.suggested_text,
        "selected_text": row.selected_text,
        "location": row.location or {},
        "destination_location": row.destination_location or {},
        "expected_outcome": row.expected_outcome,
        "is_mandatory": row.is_mandatory,
        "priority": row.priority,
        "due_at": row.due_at,
        "workflow_status": row.workflow_status,
        "publication_status": row.publication_status,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "published_at": row.published_at,
        "messages": [_message_out(session, item) for item in messages],
    }


def _annotation_out(session: Session, row: DocumentReviewAnnotation) -> dict[str, Any]:
    author = session.get(User, row.author_id)
    return {
        "id": row.id,
        "group_id": row.group_id,
        "submission_id": row.submission_id,
        "version_id": row.version_id,
        "author_id": row.author_id,
        "author_name": author.full_name if author else "Supervisor",
        "annotation_type": row.annotation_type,
        "page_number": row.page_number,
        "geometry": row.geometry or {},
        "drawing": row.drawing or {},
        "selected_text": row.selected_text,
        "content": row.content,
        "suggested_text": row.suggested_text,
        "color": row.color,
        "stroke_width": row.stroke_width,
        "publication_status": row.publication_status,
        "feedback_id": row.feedback_id,
        "revision_request_id": None,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "published_at": row.published_at,
    }


def _notify_feedback(session: Session, actor: User, submission: DocumentSubmission, requirement: DocumentUploadRequirement, group: Team, *, title: str, message: str, feedback_id: int, version_id: int) -> None:
    payload = {"requirement_id": requirement.id, "submission_id": submission.id, "version_id": version_id, "group_id": group.id, "feedback_id": feedback_id}
    notify(session, set(team_student_ids(session, group.id)), kind="DOCUMENT_REVIEW_FEEDBACK", title=title, message=message, path=f"/student/documents?requirement_id={requirement.id}&submission_id={submission.id}", exclude={actor.id}, **payload)


def _notify_annotation(session: Session, actor: User, submission: DocumentSubmission, requirement: DocumentUploadRequirement, group: Team, annotation_id: int, version_id: int) -> None:
    notify(session, set(team_student_ids(session, group.id)), kind="DOCUMENT_REVIEW_ANNOTATION", title="New document annotation", message=f"{actor.full_name} published an annotation on {requirement.title}.", path=f"/student/documents?requirement_id={requirement.id}&submission_id={submission.id}", exclude={actor.id}, requirement_id=requirement.id, submission_id=submission.id, version_id=version_id, group_id=group.id, annotation_id=annotation_id)


@router.get("/submissions/{submission_id}/annotations")
def list_annotations(submission_id: int, version_id: int | None = None, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    submission, _, _, version = _access(session, actor, submission_id, version_id=version_id)
    query = select(DocumentReviewAnnotation).where(DocumentReviewAnnotation.submission_id == submission.id, DocumentReviewAnnotation.version_id == version.id).order_by(DocumentReviewAnnotation.page_number, DocumentReviewAnnotation.created_at, DocumentReviewAnnotation.id)
    if actor.role == UserRole.STUDENT:
        query = query.where(DocumentReviewAnnotation.publication_status == "PUBLISHED")
    return [_annotation_out(session, row) for row in session.scalars(query).all()]


@router.post("/submissions/{submission_id}/annotations", status_code=status.HTTP_201_CREATED)
def create_annotation(submission_id: int, payload: AnnotationWrite, request: Request, actor: User = Depends(require_roles(*WRITERS)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    if payload.submission_id != submission_id:
        raise _error("The annotation belongs to another submission.", "submission_scope_mismatch")
    submission, requirement, group, version = _access(session, actor, submission_id, version_id=payload.version_id, write=True)
    if payload.feedback_id:
        feedback = session.get(DocumentReviewFeedback, payload.feedback_id)
        if feedback is None or feedback.submission_id != submission.id or feedback.version_id != version.id:
            raise _error("The selected feedback does not belong to this submission version.", "feedback_scope_mismatch")
    row = DocumentReviewAnnotation(submission_id=submission.id, version_id=version.id, group_id=group.id, author_id=actor.id, annotation_type=payload.annotation_type, page_number=payload.page_number, geometry=payload.geometry, drawing=payload.drawing, selected_text=payload.selected_text.strip() if payload.selected_text else None, content=payload.content.strip() if payload.content else None, suggested_text=payload.suggested_text.strip() if payload.suggested_text else None, color=payload.color, stroke_width=payload.stroke_width, publication_status=payload.publication_status, feedback_id=payload.feedback_id, published_at=_now() if payload.publication_status == "PUBLISHED" else None)
    session.add(row); session.flush()
    if row.publication_status == "PUBLISHED":
        _notify_annotation(session, actor, submission, requirement, group, row.id, version.id)
    session.commit(); session.refresh(row)
    return _annotation_out(session, row)


@router.patch("/annotations/{annotation_id}")
def update_annotation(annotation_id: int, payload: AnnotationWrite, request: Request, actor: User = Depends(require_roles(*WRITERS)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(DocumentReviewAnnotation, annotation_id)
    if row is None:
        raise _error("The annotation was not found.", "annotation_not_found", 404)
    submission, requirement, group, version = _access(session, actor, row.submission_id, version_id=row.version_id, write=True)
    if payload.submission_id != row.submission_id or payload.version_id != version.id:
        raise _error("An annotation cannot move to another submission version.", "submission_scope_mismatch")
    if payload.feedback_id:
        feedback = session.get(DocumentReviewFeedback, payload.feedback_id)
        if feedback is None or feedback.submission_id != submission.id or feedback.version_id != version.id:
            raise _error("The selected feedback does not belong to this submission version.", "feedback_scope_mismatch")
    for key in ("annotation_type", "page_number", "geometry", "drawing", "selected_text", "content", "suggested_text", "color", "stroke_width", "feedback_id"):
        setattr(row, key, getattr(payload, key))
    if row.publication_status != "PUBLISHED" and payload.publication_status == "PUBLISHED":
        row.published_at = _now()
    row.publication_status = payload.publication_status
    if row.publication_status == "PUBLISHED":
        _notify_annotation(session, actor, submission, requirement, group, row.id, version.id)
    session.commit(); session.refresh(row)
    return _annotation_out(session, row)


@router.post("/annotations/{annotation_id}/publish")
def publish_annotation(annotation_id: int, request: Request, actor: User = Depends(require_roles(*WRITERS)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(DocumentReviewAnnotation, annotation_id)
    if row is None:
        raise _error("The annotation was not found.", "annotation_not_found", 404)
    submission, requirement, group, version = _access(session, actor, row.submission_id, version_id=row.version_id, write=True)
    row.publication_status = "PUBLISHED"; row.published_at = _now(); row.withdrawn_at = None
    _notify_annotation(session, actor, submission, requirement, group, row.id, version.id)
    session.commit(); session.refresh(row)
    return _annotation_out(session, row)


@router.post("/annotations/{annotation_id}/withdraw")
def withdraw_annotation(annotation_id: int, request: Request, actor: User = Depends(require_roles(*WRITERS)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row = session.get(DocumentReviewAnnotation, annotation_id)
    if row is None:
        raise _error("The annotation was not found.", "annotation_not_found", 404)
    _access(session, actor, row.submission_id, version_id=row.version_id, write=True)
    row.publication_status = "WITHDRAWN"; row.withdrawn_at = _now()
    session.commit(); session.refresh(row)
    return _annotation_out(session, row)


@router.get("/submissions/{submission_id}/feedback")
def list_feedback(submission_id: int, version_id: int | None = None, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    submission, _, _, version = _access(session, actor, submission_id, version_id=version_id)
    query = select(DocumentReviewFeedback).where(DocumentReviewFeedback.submission_id == submission.id, DocumentReviewFeedback.version_id == version.id).order_by(desc(DocumentReviewFeedback.created_at), desc(DocumentReviewFeedback.id))
    if actor.role == UserRole.STUDENT:
        query = query.where(DocumentReviewFeedback.publication_status == "PUBLISHED")
    return [_feedback_out(session, row) for row in session.scalars(query).all()]


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
def create_feedback(payload: FeedbackWrite, request: Request, actor: User = Depends(require_roles(*WRITERS)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    submission, requirement, group, version = _access(session, actor, payload.submission_id, version_id=payload.version_id, write=True)
    marker = (session.scalar(select(func.max(DocumentReviewFeedback.marker_number)).where(DocumentReviewFeedback.submission_id == submission.id, DocumentReviewFeedback.version_id == version.id)) or 0) + 1
    mandatory = bool(payload.is_mandatory or payload.feedback_type in {"FORMAL_REVISION", "FORMAL_REVISION_REQUEST"})
    row = DocumentReviewFeedback(submission_id=submission.id, version_id=version.id, group_id=group.id, author_id=actor.id, marker_number=marker, feedback_level=payload.feedback_level, feedback_type=payload.feedback_type, correction_action=payload.correction_action, title=payload.title.strip(), content=payload.content.strip(), suggested_text=payload.suggested_text.strip() if payload.suggested_text else None, selected_text=payload.selected_text.strip() if payload.selected_text else None, location=payload.location, destination_location=payload.destination_location, expected_outcome=payload.expected_outcome.strip() if payload.expected_outcome else None, is_mandatory=mandatory, priority=payload.priority, due_at=payload.due_at, publication_status="PUBLISHED" if payload.publish else "DRAFT", published_at=_now() if payload.publish else None)
    session.add(row); session.flush()
    if payload.publish:
        submission.review_comment = row.content
        _notify_feedback(session, actor, submission, requirement, group, title="New supervisor feedback", message=f"{actor.full_name} published feedback on {requirement.title}.", feedback_id=row.id, version_id=version.id)
    session.commit(); session.refresh(row)
    return _feedback_out(session, row)


def _feedback_access(session: Session, actor: User, feedback_id: int, *, write: bool = False) -> tuple[DocumentReviewFeedback, DocumentSubmission, DocumentUploadRequirement, Team]:
    row = session.get(DocumentReviewFeedback, feedback_id)
    if row is None:
        raise _error("The feedback item was not found.", "feedback_not_found", 404)
    if actor.role == UserRole.STUDENT and row.publication_status != "PUBLISHED":
        raise _error("The feedback item is not published.", "feedback_not_found", 404)
    submission, requirement, group, _ = _access(session, actor, row.submission_id, version_id=row.version_id, write=write)
    return row, submission, requirement, group


@router.patch("/feedback/{feedback_id}")
def update_feedback(feedback_id: int, payload: FeedbackUpdate, request: Request, actor: User = Depends(require_roles(*WRITERS)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row, _, _, _ = _feedback_access(session, actor, feedback_id, write=True)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value.strip() if isinstance(value, str) else value)
    session.commit(); session.refresh(row)
    return _feedback_out(session, row)


@router.post("/feedback/{feedback_id}/publish")
def publish_feedback(feedback_id: int, request: Request, actor: User = Depends(require_roles(*WRITERS)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row, submission, requirement, group = _feedback_access(session, actor, feedback_id, write=True)
    row.publication_status = "PUBLISHED"; row.published_at = _now(); row.withdrawn_at = None
    submission.review_comment = row.content
    _notify_feedback(session, actor, submission, requirement, group, title="New supervisor feedback", message=f"{actor.full_name} published feedback: {row.title}.", feedback_id=row.id, version_id=row.version_id)
    session.commit(); session.refresh(row)
    return _feedback_out(session, row)


@router.post("/feedback/{feedback_id}/withdraw")
def withdraw_feedback(feedback_id: int, request: Request, actor: User = Depends(require_roles(*WRITERS)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row, _, _, _ = _feedback_access(session, actor, feedback_id, write=True)
    row.publication_status = "WITHDRAWN"; row.withdrawn_at = _now()
    session.commit(); session.refresh(row)
    return _feedback_out(session, row)


@router.post("/feedback/{feedback_id}/addressed")
def address_feedback(feedback_id: int, request: Request, actor: User = Depends(require_roles(UserRole.STUDENT)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row, submission, _, group = _feedback_access(session, actor, feedback_id)
    row.workflow_status = "ADDRESSED"
    notify(session, set(team_supervisor_ids(session, group.id)), kind="DOCUMENT_REVIEW_FEEDBACK_ADDRESSED", title="Student marked feedback addressed", message=f"{actor.full_name} marked '{row.title}' as addressed.", path=f"/supervisor/groups/{group.id}?tab=documents", exclude={actor.id}, submission_id=submission.id, feedback_id=row.id, group_id=group.id)
    session.commit(); session.refresh(row)
    return _feedback_out(session, row)


@router.post("/feedback/{feedback_id}/verify")
def verify_feedback(feedback_id: int, request: Request, actor: User = Depends(require_roles(*WRITERS)), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row, _, _, _ = _feedback_access(session, actor, feedback_id, write=True)
    row.workflow_status = "VERIFIED"
    session.commit(); session.refresh(row)
    return _feedback_out(session, row)


@router.post("/feedback/{feedback_id}/messages", status_code=status.HTTP_201_CREATED)
def create_feedback_message(feedback_id: int, payload: MessageWrite, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    row, submission, requirement, group = _feedback_access(session, actor, feedback_id)
    message = DocumentReviewFeedbackMessage(feedback_id=row.id, sender_id=actor.id, body=payload.body.strip())
    session.add(message)
    recipients = team_supervisor_ids(session, group.id) if actor.role == UserRole.STUDENT else team_student_ids(session, group.id)
    notify(session, set(recipients), kind="DOCUMENT_REVIEW_MESSAGE", title="New message on document feedback", message=f"{actor.full_name} replied to '{row.title}'.", path=f"/supervisor/groups/{group.id}?tab=documents" if actor.role != UserRole.STUDENT else f"/student/documents?requirement_id={requirement.id}&submission_id={submission.id}", exclude={actor.id}, submission_id=submission.id, feedback_id=row.id, group_id=group.id)
    session.commit(); session.refresh(message)
    return _message_out(session, message)
