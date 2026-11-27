"""Metadata and permission primitives for the shared document/vector index."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import KnowledgeDocument


def register_knowledge_document(
    session: Session,
    *,
    source_type: str,
    source_id: int,
    storage_key: str | None,
    academic_cycle_id: int | None,
    team_id: int | None,
    student_user_id: int | None,
    supervisor_id: int | None,
    project_title: str | None,
    document_type: str,
    content_type: str | None,
    file_size: int | None,
    content_hash: str | None,
    access_policy: dict[str, Any],
    uploaded_at: datetime | None = None,
) -> KnowledgeDocument:
    row = session.scalar(select(KnowledgeDocument).where(KnowledgeDocument.source_type == source_type, KnowledgeDocument.source_id == source_id).limit(1))
    values = {
        "storage_key": storage_key,
        "academic_cycle_id": academic_cycle_id,
        "team_id": team_id,
        "student_user_id": student_user_id,
        "supervisor_id": supervisor_id,
        "project_title": project_title,
        "document_type": document_type,
        "content_type": content_type,
        "file_size": file_size,
        "content_hash": content_hash,
        "access_policy": access_policy,
    }
    if row is None:
        row = KnowledgeDocument(source_type=source_type, source_id=source_id, **values)
        if uploaded_at is not None:
            row.uploaded_at = uploaded_at
        session.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    return row
