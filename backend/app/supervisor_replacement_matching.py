"""Deterministic supervisor ranking for administrator replacement cases."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .models import (
    AcademicCycle,
    SupervisorAssignment,
    SupervisorAvailability,
    SupervisorCapacityPolicy,
    SupervisorDeparture,
    SupervisorExpertise,
    SupervisorProfile,
    SupervisorResearchInterest,
    SupervisorSkill,
    SupervisedProjectHistory,
    User,
    UserRole,
)

TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
WEIGHTS = {
    "expertise": 0.25,
    "research_interest": 0.20,
    "history": 0.15,
    "methodology": 0.10,
    "technology": 0.15,
    "domain": 0.10,
    "preference": 0.05,
}
HISTORY_TYPES = {"ARCHIVED_PROJECT", "SUPERVISED_ASSIGNMENT"}


def _tokens(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, dict):
        return _tokens(list(value.values()))
    if isinstance(value, (list, tuple, set)):
        return {token for item in value for token in _tokens(item)}
    return set(TOKEN_RE.findall(str(value).casefold()))


def _score(proposal_terms: set[str], candidate_terms: set[str]) -> float:
    if not proposal_terms or not candidate_terms:
        return 0.0
    return len(proposal_terms & candidate_terms) / len(proposal_terms | candidate_terms)


def _profile_terms(profile: SupervisorProfile, session: Session) -> dict[str, set[str]]:
    expertise = session.scalars(select(SupervisorExpertise).where(SupervisorExpertise.profile_id == profile.id, SupervisorExpertise.active.is_(True))).all()
    skills = session.scalars(select(SupervisorSkill).where(SupervisorSkill.profile_id == profile.id, SupervisorSkill.active.is_(True))).all()
    interests = session.scalars(select(SupervisorResearchInterest).where(SupervisorResearchInterest.profile_id == profile.id, SupervisorResearchInterest.active.is_(True))).all()
    history = session.scalars(
        select(SupervisedProjectHistory)
        .where(SupervisedProjectHistory.profile_id == profile.id, SupervisedProjectHistory.source_type.in_(HISTORY_TYPES), SupervisedProjectHistory.source_verified.is_(True))
        .order_by(SupervisedProjectHistory.year.desc().nullslast(), SupervisedProjectHistory.id.desc())
    ).all()
    return {
        "expertise": _tokens([row.name for row in expertise] + [row.evidence for row in expertise] + [profile.degree, profile.specialization, profile.publications]),
        "research_interest": _tokens([row.name for row in interests] + [row.evidence for row in interests]),
        "history": _tokens([[row.project_title, row.abstract, row.keywords] for row in history]),
        "methodology": _tokens([[row.methodology, row.name] for row in skills if row.category.casefold() in {"methodology", "methods"}] + [row.methodology for row in history]),
        "technology": _tokens([[row.name, row.category] for row in skills] + [row.technologies for row in history]),
        "domain": _tokens([[profile.department, profile.program, profile.degree, profile.specialization, profile.biography, profile.publications]] + [row.research_domain for row in history]),
        "preference": _tokens(profile.preferred_categories),
    }, history


def _proposal_text(fields: dict[str, Any]) -> str:
    keys = ("title", "topic", "problem_statement", "methodology", "proposed_solution", "scope", "research_domain", "required_skills", "technologies", "methods", "keywords", "objectives", "expected_outcomes")
    return " ".join(" ".join(value) if isinstance(value, list) else str(value or "") for key in keys for value in [fields.get(key)])


def rank_supervisors_for_replacement(
    session: Session,
    cycle: AcademicCycle,
    fields: dict[str, Any],
    *,
    excluded_supervisor_ids: set[int] | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Rank eligible supervisors using profile evidence and capacity only.

    This workflow intentionally has no external model, AI state, or matching cache.
    """

    excluded = excluded_supervisor_ids or set()
    proposal_text = _proposal_text(fields)
    proposal_terms = _tokens(proposal_text)
    proposal_domains = _tokens(fields.get("research_domain", []))
    proposal_methods = _tokens([fields.get("methodology", ""), fields.get("methods", [])])
    proposal_technology = _tokens([fields.get("technologies", []), fields.get("required_skills", [])])
    rows = session.execute(
        select(SupervisorProfile, User)
        .join(User, User.id == SupervisorProfile.supervisor_id)
        .where(
            User.role == UserRole.SUPERVISOR,
            User.is_active.is_(True),
            SupervisorProfile.is_active.is_(True),
            SupervisorProfile.profile_status == "VERIFIED",
            SupervisorProfile.visibility_status == "PUBLIC",
        )
        .order_by(SupervisorProfile.id)
    ).all()
    candidates: list[dict[str, Any]] = []
    for profile, user in rows:
        if user.id in excluded:
            continue
        if session.scalar(select(SupervisorDeparture.id).where(SupervisorDeparture.supervisor_id == user.id, SupervisorDeparture.active.is_(True)).limit(1)) is not None:
            continue
        availability = session.scalar(select(SupervisorAvailability).where(SupervisorAvailability.profile_id == profile.id, SupervisorAvailability.academic_cycle_id == cycle.id).limit(1))
        if availability is not None and not availability.available:
            continue
        active_groups = session.scalar(
            select(func.count(SupervisorAssignment.id)).where(
                SupervisorAssignment.supervisor_id == user.id,
                SupervisorAssignment.ended_at.is_(None),
                SupervisorAssignment.academic_year == cycle.academic_year,
            )
        ) or 0
        policy = session.scalar(
            select(SupervisorCapacityPolicy)
            .where(
                SupervisorCapacityPolicy.supervisor_id == user.id,
                or_(SupervisorCapacityPolicy.academic_cycle_id == cycle.id, SupervisorCapacityPolicy.academic_year == cycle.academic_year),
            )
            .order_by(SupervisorCapacityPolicy.academic_cycle_id.desc().nullslast())
            .limit(1)
        )
        capacity_limit = policy.max_group_capacity if policy is not None else availability.maximum_capacity if availability is not None and availability.maximum_capacity > 0 else None
        if capacity_limit is not None and active_groups >= capacity_limit:
            continue
        terms, history = _profile_terms(profile, session)
        values = {
            "expertise": _score(proposal_terms, terms["expertise"]),
            "research_interest": _score(proposal_domains or proposal_terms, terms["research_interest"]),
            "history": _score(proposal_terms, terms["history"]),
            "methodology": _score(proposal_methods or proposal_terms, terms["methodology"]),
            "technology": _score(proposal_technology or proposal_terms, terms["technology"]),
            "domain": _score(proposal_domains or proposal_terms, terms["domain"]),
            "preference": _score(proposal_domains or proposal_terms, terms["preference"]),
        }
        final_score = round(sum(WEIGHTS[key] * value for key, value in values.items()) * 100, 4)
        related = [row for row in history if _tokens([row.project_title, row.abstract, row.keywords]) & proposal_terms][:3]
        reasons = []
        if values["expertise"] > 0:
            reasons.append("Profile expertise overlaps the proposal.")
        if values["research_interest"] > 0:
            reasons.append("Research interests overlap the project domain.")
        if values["history"] > 0:
            reasons.append("Verified supervision history contains related terms.")
        candidates.append(
            {
                "supervisor_id": user.id,
                "supervisor_name": user.full_name,
                "final_score": final_score,
                "deterministic_score": round(final_score, 2),
                "score_components": {f"{key}_score": round(value * 100, 2) for key, value in values.items()} | {"final_score": round(final_score, 2)},
                "explanation": {
                    "reasons": reasons or ["The supervisor is eligible but has limited direct vocabulary overlap."],
                    "related_projects": [{"title": row.project_title, "year": row.year, "summary": row.public_summary or row.abstract} for row in related],
                    "gaps": [label for label, value in values.items() if value < 0.1],
                    "confidence": round(sum(value > 0 for value in values.values()) / len(values), 2),
                    "ranking_method": "deterministic",
                    "evidence_policy": "Scores use verified public profile fields, recorded supervision history, proposal text, and current capacity.",
                },
                "workload": {
                    "active_groups": active_groups,
                    "capacity_limit": capacity_limit,
                    "remaining_capacity": max(capacity_limit - active_groups, 0) if capacity_limit is not None else None,
                    "availability": availability.available if availability is not None else True,
                },
            }
        )
    candidates.sort(key=lambda item: (-item["final_score"], item["supervisor_id"]))
    for rank, item in enumerate(candidates[:limit], 1):
        item["rank"] = rank
    return candidates[:limit]
