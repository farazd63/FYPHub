"""Equal-weight aggregation for team compatibility assessments.

How preferences become assessments is deliberately left to a later decision.
"""
from collections.abc import Mapping

PREFERENCE_CATEGORIES = ("skills", "domain", "availability", "work_style", "preferred_role", "commitment")

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
