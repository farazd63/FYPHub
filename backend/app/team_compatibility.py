"""Equal-weight aggregation for team compatibility assessments.

How preferences become assessments is deliberately left to a later decision.
"""
from collections.abc import Mapping

PREFERENCE_CATEGORIES = ("skills", "domain", "availability", "work_style", "preferred_role", "commitment")

DEFAULT_MATCHING_WEIGHTS = {
    "skills": 0.25,
    "domain": 0.20,
    "availability": 0.15,
    "work_style": 0.15,
    "preferred_role": 0.15,
    "commitment": 0.10,
}

def aggregate_compatibility(assessments: Mapping[str, bool | None]) -> dict[str, object]:
    """Aggregate comparable categories, leaving missing assessments unscored."""
    if set(assessments) - set(PREFERENCE_CATEGORIES):
        raise ValueError("Unsupported preference category.")
    if any(value is not None and type(value) is not bool for value in assessments.values()):
        raise ValueError("Assessments must be boolean or unanswered.")
    considered = {category: assessments.get(category) for category in PREFERENCE_CATEGORIES if assessments.get(category) is not None}
    matched = sum(value is True for value in considered.values())
    return {"categories": considered, "matched": matched, "answered": len(considered),
            "fraction": matched / len(considered) if considered else None}


def _tokens(value: object) -> set[str]:
    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = str(value or "").replace("/", ",").replace(";", ",").split(",")
    return {str(item).strip().casefold() for item in values if str(item).strip()}


def _overlap(left: object, right: object) -> float | None:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return None
    return len(a & b) / len(a | b)


def _similar_scale(left: object, right: object) -> float | None:
    try:
        a, b = float(left), float(right)
    except (TypeError, ValueError):
        return _overlap(left, right)
    return max(0.0, 1.0 - min(abs(a - b) / 10.0, 1.0))


def _complementary(left: object, right: object) -> float | None:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return None
    if a.isdisjoint(b):
        return 1.0
    return max(0.0, 1.0 - len(a & b) / len(a | b))


def hybrid_compatibility(left: Mapping[str, object], right: Mapping[str, object], weights: Mapping[str, object] | None = None) -> dict[str, object]:
    """Reproducible, explainable score; Ollama is never involved in this function."""
    configured = {**DEFAULT_MATCHING_WEIGHTS, **(weights or {})}
    dimensions: dict[str, float | None] = {
        "skills": _complementary(left.get("skills"), right.get("skills_wanted")) if left.get("skills") and right.get("skills_wanted") else _complementary(left.get("skills"), right.get("skills")),
        "domain": _overlap(left.get("domain_interest") or left.get("domain"), right.get("domain_interest") or right.get("domain")),
        "availability": _overlap(left.get("availability"), right.get("availability")),
        "work_style": _similar_scale(left.get("work_style"), right.get("work_style")),
        "preferred_role": _complementary(left.get("preferred_role"), right.get("preferred_role")),
        "commitment": _similar_scale(left.get("commitment"), right.get("commitment")),
    }
    considered = {key: value for key, value in dimensions.items() if value is not None}
    denominator = sum(float(configured.get(key, 0.0)) for key in considered) or 1.0
    score = sum(float(configured.get(key, 0.0)) * float(value) for key, value in considered.items()) / denominator
    explanation = [f"{key.replace('_', ' ').title()} {round(value * 100)}%" for key, value in considered.items()]
    return {"score": round(score, 4), "dimensions": dimensions, "answered": len(considered), "explanation_parts": explanation}
