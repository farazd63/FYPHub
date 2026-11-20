"""Structured, wording-independent comparison of audited proposal versions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field


class VersionComparisonSummaryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    output_token_budget: ClassVar[int] = 256
    inference_timeout: ClassVar[float] = 30.0
    summary: str = Field(min_length=1, max_length=800)


def _location(item: dict[str, Any]) -> dict[str, Any]:
    location = item.get("location")
    return location if isinstance(location, dict) else {}


def _pages(item: dict[str, Any], location: dict[str, Any]) -> list[int]:
    values = item.get("affectedPages") if isinstance(item.get("affectedPages"), list) else [location.get("page")]
    pages: list[int] = []
    for value in values:
        try:
            page = int(value)
        except (TypeError, ValueError):
            continue
        if page > 0 and page not in pages:
            pages.append(page)
    return sorted(pages)


def issue_fingerprint(item: dict[str, Any]) -> str:
    """Create an identity from rule, section, page, and relevant field—not wording."""
    location = _location(item)
    identity = {
        "ruleCode": str(item.get("rule_code") or item.get("ruleCode") or item.get("id") or item.get("name") or item.get("issue") or "unknown-rule"),
        "section": str(location.get("section_name") or location.get("section") or item.get("section") or item.get("category") or "document"),
        "pages": _pages(item, location),
        "field": str(location.get("field") or location.get("section_number") or location.get("key") or item.get("field") or location.get("scope") or ""),
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _normalize_issue(item: dict[str, Any]) -> dict[str, Any]:
    location = _location(item)
    return {
        "fingerprint": issue_fingerprint(item),
        "ruleCode": str(item.get("rule_code") or item.get("ruleCode") or item.get("id") or item.get("name") or item.get("issue") or "unknown-rule"),
        "issue": str(item.get("name") or item.get("issue") or "Compliance issue"),
        "category": str(item.get("category") or "Template Compliance"),
        "status": str(item.get("status") or "UNVERIFIABLE"),
        "section": location.get("section_name") or location.get("section") or location.get("section_number") or item.get("section") or item.get("category") or "Document",
        "pages": _pages(item, location),
        "location": location,
        "expected": item.get("expected") if "expected" in item else item.get("originalTemplate"),
        "actual": item.get("actual") if "actual" in item else item.get("studentDocument"),
        "difference": item.get("difference"),
    }


def extract_structured_issues(report: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Use stored structured checks; never inspect proposal PDFs or extracted text."""
    if not isinstance(report, dict):
        return []
    issues: list[dict[str, Any]] = []
    for category in report.get("categories") or []:
        if not isinstance(category, dict):
            continue
        for check in category.get("checks") or []:
            if not isinstance(check, dict) or str(check.get("status", "")).upper() == "PASS":
                continue
            issues.append(_normalize_issue({"category": category.get("name"), **check}))
    if issues:
        return issues
    return [_normalize_issue(item) for item in report.get("documentDifferenceIssues") or [] if isinstance(item, dict) and str(item.get("status", "")).casefold() not in {"passed", "pass"}]


def _score(report: dict[str, Any]) -> int | None:
    summary = report.get("reportSummary") if isinstance(report, dict) else None
    score = summary.get("score") if isinstance(summary, dict) else None
    return int(score) if isinstance(score, (int, float)) else None


def _issue_state(item: dict[str, Any]) -> str:
    return json.dumps({key: item.get(key) for key in ("status", "section", "pages", "expected", "actual", "difference")}, sort_keys=True, default=str, separators=(",", ":"))


def _status_rank(item: dict[str, Any]) -> int:
    return {"PASS": 0, "UNVERIFIABLE": 1, "PARTIAL": 1, "FAIL": 2}.get(str(item.get("status", "UNVERIFIABLE")).upper(), 1)


def _overall_result(previous_score: int | None, current_score: int | None, net_issue_change: int) -> str:
    if previous_score is not None and current_score is not None:
        if current_score > previous_score:
            return "Improved"
        if current_score < previous_score:
            return "Worse"
    return "Improved" if net_issue_change < 0 else "Worse" if net_issue_change > 0 else "Unchanged"


def deterministic_summary(comparison: dict[str, Any]) -> str:
    score_difference = comparison.get("scoreDifference")
    score_text = ""
    if comparison.get("previousScore") is not None and comparison.get("newScore") is not None:
        sign = "+" if isinstance(score_difference, (int, float)) and score_difference > 0 else ""
        score_text = f" Compliance score changed from {comparison['previousScore']} to {comparison['newScore']} ({sign}{score_difference})."
    worsened = len(comparison.get("worsenedIssues", []))
    worsened_text = f" {worsened} issue{'s' if worsened != 1 else ''} became worse." if worsened else ""
    return (
        f"Version {comparison['previousVersion']} contained {comparison['previousIssueCount']} issues. "
        f"Version {comparison['currentVersion']} contains {comparison['currentIssueCount']} issues. "
        f"{len(comparison['fixedIssues'])} issues were resolved, {len(comparison['remainingIssues'])} previous issues remain, "
        f"and {len(comparison['newIssues'])} new issues were detected.{worsened_text}{score_text} "
        f"Overall compliance has {str(comparison['overallResult']).lower()}."
    )


def build_version_comparison(*, previous_report: dict[str, Any], current_report: dict[str, Any], previous_version: int, current_version: int, previous_template_version_id: int | None, current_template_version_id: int | None) -> dict[str, Any]:
    previous = extract_structured_issues(previous_report)
    current = extract_structured_issues(current_report)
    previous_by_id = {item["fingerprint"]: item for item in previous}
    current_by_id = {item["fingerprint"]: item for item in current}
    previous_ids, current_ids = set(previous_by_id), set(current_by_id)
    remaining_ids = previous_ids & current_ids
    fixed_ids = previous_ids - current_ids
    new_ids = current_ids - previous_ids
    unchanged_ids = {key for key in remaining_ids if _issue_state(previous_by_id[key]) == _issue_state(current_by_id[key])}
    worsened_ids = {key for key in remaining_ids if _status_rank(current_by_id[key]) > _status_rank(previous_by_id[key])}
    previous_score, current_score = _score(previous_report), _score(current_report)
    score_difference = current_score - previous_score if previous_score is not None and current_score is not None else None
    net_issue_change = len(current) - len(previous)
    different_templates = previous_template_version_id is not None and current_template_version_id is not None and previous_template_version_id != current_template_version_id
    result: dict[str, Any] = {
        "previousVersion": previous_version,
        "currentVersion": current_version,
        "previousIssueCount": len(previous),
        "currentIssueCount": len(current),
        "netIssueChange": net_issue_change,
        "previousScore": previous_score,
        "newScore": current_score,
        "scoreDifference": score_difference,
        "overallResult": _overall_result(previous_score, current_score, net_issue_change),
        "fixedIssues": [previous_by_id[key] for key in sorted(fixed_ids)],
        "remainingIssues": [{"previous": previous_by_id[key], "current": current_by_id[key]} for key in sorted(remaining_ids)],
        "worsenedIssues": [{"previous": previous_by_id[key], "current": current_by_id[key]} for key in sorted(worsened_ids)],
        "newIssues": [current_by_id[key] for key in sorted(new_ids)],
        "unchangedIssues": [current_by_id[key] for key in sorted(unchanged_ids)],
        "differentTemplateVersions": different_templates,
        "templateVersionMessage": "Comparison based on different template versions." if different_templates else None,
    }
    result["deterministicSummary"] = deterministic_summary(result)
    return result


def _summary_prompt(comparison: dict[str, Any]) -> str:
    context = {key: comparison.get(key) for key in ("previousVersion", "currentVersion", "previousIssueCount", "currentIssueCount", "netIssueChange", "previousScore", "newScore", "scoreDifference", "overallResult", "differentTemplateVersions")}
    context.update({"fixedIssueCount": len(comparison["fixedIssues"]), "remainingIssueCount": len(comparison["remainingIssues"]), "worsenedIssueCount": len(comparison.get("worsenedIssues", [])), "newIssueCount": len(comparison["newIssues"]), "unchangedIssueCount": len(comparison["unchangedIssues"])})
    return "Write one concise paragraph from these structured comparison counts and scores. Do not invent details or request proposal text. Return JSON matching the schema.\n" + json.dumps(context, sort_keys=True)


async def generate_comparison_summary(comparison: dict[str, Any], runner: Callable[..., Awaitable[dict[str, Any]]], *, rate_key: str) -> dict[str, Any]:
    result = await runner(_summary_prompt(comparison), VersionComparisonSummaryPayload, model_kind="proposal", rate_key=rate_key)
    saved: dict[str, Any] = {"status": result.get("status", "UNAVAILABLE"), "source": result.get("source"), "model": result.get("model"), "provider": result.get("provider"), "generatedAt": result.get("timestamp") or datetime.now(timezone.utc).isoformat(), "advisory": True, "inputScope": "STRUCTURED_VERSION_COMPARISON_V1"}
    payload = result.get("payload") or {}
    if result.get("status") == "COMPLETED" and isinstance(payload, dict) and isinstance(payload.get("summary"), str) and payload["summary"].strip():
        saved["summary"] = payload["summary"].strip()
        return saved
    saved.update({"status": "FALLBACK", "source": "DETERMINISTIC_COMPARISON_SUMMARY", "summary": comparison.get("deterministicSummary") or deterministic_summary(comparison), "fallbackReason": result.get("fallback_reason") or "AI summary unavailable"})
    return saved
