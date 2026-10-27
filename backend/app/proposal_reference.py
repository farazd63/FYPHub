"""Authorized, advisory search over archived proposal references."""

import re
from difflib import SequenceMatcher
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles
from .database import get_db
from .models import ProposalReference, ProposalReferenceDocument, User, UserRole

router = APIRouter(prefix="/api/v1/proposal-references")
REFERENCE_ROLES = (UserRole.STUDENT, UserRole.SUPERVISOR, UserRole.COORDINATOR, UserRole.ADMIN)


def normalize_title(value: str) -> str:
    """Normalize case, punctuation, and repeated whitespace for advisory matching."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.casefold())).strip()


def _similarity(query: str, title: str) -> float:
    query_tokens = set(query.split())
    title_tokens = set(title.split())
    token_score = len(query_tokens & title_tokens) / max(len(query_tokens | title_tokens), 1)
    sequence_score = SequenceMatcher(None, query, title).ratio()
    return max(token_score, sequence_score)


def _result(reference: ProposalReference, document: ProposalReferenceDocument | None, match_type: str, score: float | None = None) -> dict:
    return {
        "id": reference.id,
        "match_type": match_type,
        "match_score": round(score, 3) if score is not None else None,
        "title": reference.title,
        "academic_year": reference.academic_year,
        "academic_cycle_id": reference.academic_cycle_id,
        "short_summary": reference.short_summary,
        "category_scope": reference.category_scope,
        "source_label": reference.source_label,
        "pdf_available": document is not None,
        "pdf_url": f"/api/v1/proposal-references/{reference.id}/document" if document else None,
    }


@router.get("/search")
def search_references(
    q: str = Query(min_length=1, max_length=255),
    _: User = Depends(require_roles(*REFERENCE_ROLES)),
    session: Session = Depends(get_db),
):
    normalized = normalize_title(q)
    if not normalized:
        raise HTTPException(status_code=422, detail="Search title must contain letters or numbers.")
    rows = session.execute(
        select(ProposalReference, ProposalReferenceDocument)
        .outerjoin(ProposalReferenceDocument, ProposalReferenceDocument.reference_id == ProposalReference.id)
        .where(ProposalReference.is_active.is_(True))
    ).all()
    exact = [(reference, document) for reference, document in rows if reference.normalized_title == normalized]
    if exact:
        results = [_result(reference, document, "exact_title_match", 1.0) for reference, document in exact]
        return {"query": q, "normalized_query": normalized, "match_type": "exact_title_match", "semantic_analysis": "unavailable", "advisory": True, "results": results}
    scored = sorted(
        ((_similarity(normalized, reference.normalized_title), reference, document) for reference, document in rows),
        key=lambda item: (-item[0], item[1].id),
    )
    close = [(score, reference, document) for score, reference, document in scored if score >= 0.45]
    if close:
        return {"query": q, "normalized_query": normalized, "match_type": "possible_similar_title", "semantic_analysis": "unavailable", "advisory": True, "results": [_result(reference, document, "possible_similar_title", score) for score, reference, document in close[:10]]}
    return {"query": q, "normalized_query": normalized, "match_type": "no_close_match", "semantic_analysis": "unavailable", "advisory": True, "results": []}


@router.get("/{reference_id}/document")
def reference_document(
    reference_id: int,
    _: User = Depends(require_roles(*REFERENCE_ROLES)),
    session: Session = Depends(get_db),
):
    reference = session.scalar(select(ProposalReference).where(ProposalReference.id == reference_id, ProposalReference.is_active.is_(True)))
    if reference is None:
        raise HTTPException(status_code=404, detail="Proposal reference was not found.")
    document = session.scalar(select(ProposalReferenceDocument).where(ProposalReferenceDocument.reference_id == reference.id))
    if document is None:
        raise HTTPException(status_code=404, detail="Proposal reference PDF is not available.")
    filename = document.filename.replace('"', "'").replace("\r", "").replace("\n", "")
    return StreamingResponse(BytesIO(document.content), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})
