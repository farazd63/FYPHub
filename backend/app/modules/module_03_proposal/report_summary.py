"""User-facing compliance report preparation and summary generation.

The compliance engine remains the source of truth for rules, measurements, and
scores.  This module only converts those structured results into readable report
rows and, optionally, asks the configured language model to explain them.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field


class ComplianceReportSummaryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    output_token_budget: ClassVar[int] = 220
    inference_timeout: ClassVar[float] = 30.0
    summary: str = Field(min_length=1, max_length=900)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return ""
    return str(value).strip()


def _status_code(item: dict[str, Any]) -> str:
    value = str(item.get("statusCode") or item.get("status") or "UNVERIFIABLE").upper()
    return {"PASSED": "PASS", "FAILED": "FAIL", "WARNING": "PARTIAL", "REVIEW": "UNVERIFIABLE"}.get(value, value)


def _status_label(code: str) -> str:
    return {"PASS": "Passed", "FAIL": "Failed", "PARTIAL": "Verify", "UNVERIFIABLE": "Verify"}.get(code, "Verify")


def _human_value(value: Any, *, missing: str = "Not found in the uploaded document") -> str:
    if value is None or value == "":
        return missing
    if isinstance(value, list):
        return ", ".join(_text(item) for item in value if _text(item)) or missing
    if isinstance(value, dict):
        return "Evidence available in administrator view"
    return str(value)


def _friendly_row(item: dict[str, Any], category: str | None = None) -> dict[str, Any]:
    code = _status_code(item)
    severity = str(item.get("severity") or "warning").casefold()
    status = str(item.get("status") or "").casefold()
    priority = str(item.get("priority") or ("High" if code == "FAIL" and severity == "critical" else "Medium"))
    expected = item.get("originalTemplate") if "originalTemplate" in item else item.get("requirement") if "requirement" in item else item.get("expected")
    actual = item.get("studentDocument") if "studentDocument" in item else item.get("actual")
    if code in {"PARTIAL", "UNVERIFIABLE"}:
        actual_text = "Could not verify from the uploaded document"
        difference = "Evidence was insufficient to verify this requirement."
    else:
        actual_text = _human_value(actual)
        difference = _human_value(item.get("difference"), missing="No difference detected" if code == "PASS" else "The required value or section was not found in the uploaded document.")
    return {
        "id": str(item.get("id") or item.get("issue") or item.get("name") or "compliance-check"),
        "area": str(item.get("category") or category or "Template Compliance"),
        "requirement": _human_value(expected, missing="Requirement not configured"),
        "studentDocument": actual_text,
        "difference": difference,
        "statusCode": code,
        "status": _status_label(code),
        "priority": priority,
        "problem": str(item.get("problem") or item.get("issue") or item.get("name") or "Compliance requirement"),
        "correction": str(item.get("correction") or item.get("requiredAction") or "Review this requirement against the approved university template."),
        "evidence": str(item.get("evidence") or "Evidence was not recorded for this check."),
        "affectedPages": item.get("affectedPages") if isinstance(item.get("affectedPages"), list) else [],
        "severity": severity,
    }


def _raw_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    existing = report.get("comparisonRows")
    if isinstance(existing, list) and existing:
        return [item for item in existing if isinstance(item, dict)]
    existing = report.get("documentDifferenceIssues")
    if isinstance(existing, list) and existing:
        return [item for item in existing if isinstance(item, dict)]
    rows: list[dict[str, Any]] = []
    for category in report.get("categories") or []:
        if not isinstance(category, dict):
            continue
        for item in category.get("checks") or []:
            if isinstance(item, dict):
                rows.append({**item, "category": item.get("category") or category.get("name")})
    return rows


def _priority_key(row: dict[str, Any]) -> tuple[int, int, str]:
    return (0 if row.get("priority") == "High" else 1, 0 if row.get("statusCode") == "FAIL" else 1, str(row.get("problem", "")))


def _academic_flow(report: dict[str, Any]) -> list[dict[str, Any]]:
    existing = report.get("academicFlow")
    if isinstance(existing, list) and existing:
        return [item for item in existing if isinstance(item, dict)]
    flow: list[dict[str, Any]] = []
    for item in report.get("academicConsistency") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "Academic relationship")
        left, separator, right = name.partition(" / ")
        code = _status_code(item)
        flow.append({
            "name": name,
            "from": left if separator else name,
            "to": right if separator else "Verified relationship",
            "statusCode": code,
            "status": _status_label(code),
            "evidence": str(item.get("evidence") or "Evidence was not recorded for this relationship."),
        })
    return flow


def deterministic_report_summary(report: dict[str, Any]) -> str:
    summary = report.get("reportSummary") if isinstance(report.get("reportSummary"), dict) else {}
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    failed = int(metrics.get("failed") or 0)
    partial = int(metrics.get("partial") or 0)
    score = summary.get("score", 0)
    rows = report.get("comparisonRows") if isinstance(report.get("comparisonRows"), list) else []
    problem_rows = [row for row in rows if isinstance(row, dict) and row.get("statusCode") != "PASS"]
    if not failed and not partial:
        return "All configured university requirements were verified successfully."
    opening = "Your proposal currently has major compliance problems." if failed >= 3 or int(score or 0) < 50 else "Your proposal needs a few compliance corrections."
    focus = ""
    if problem_rows:
        focus = " Start with " + "; ".join(
            f"{row.get('problem')}: required {row.get('requirement')}; document shows {row.get('studentDocument')}"
            for row in problem_rows[:3]
        ) + "."
    verification = f" {partial} check{'s' if partial != 1 else ''} require{'s' if partial == 1 else ''} verification because the uploaded document did not provide enough evidence." if partial else ""
    return f"{opening}{focus}{verification} Review the required correction for each failed check before submitting a new version."


def prepare_user_friendly_report(report: dict[str, Any]) -> dict[str, Any]:
    """Add stable, readable fields to both new and previously saved reports."""
    payload = dict(report)
    summary = dict(payload.get("reportSummary") or {})
    metrics = dict(summary.get("metrics") or {})
    rows = [_friendly_row(item) for item in _raw_rows(payload)]
    passed = [row for row in rows if row.get("statusCode") == "PASS"]
    attention = sorted([row for row in rows if row.get("statusCode") != "PASS"], key=_priority_key)
    status = str(summary.get("status") or "Needs Corrections")
    status = {"Rejected": "Needs Major Corrections", "Needs Correction": "Needs Corrections"}.get(status, status)
    summary.update({
        "status": status,
        "result": status,
        "verification": int(metrics.get("partial") or 0),
        "deterministicSummary": summary.get("deterministicSummary") or deterministic_report_summary({**payload, "reportSummary": {**summary, "metrics": metrics}, "comparisonRows": rows}),
    })
    payload["reportSummary"] = summary
    payload["comparisonRows"] = rows
    payload["whatToFixFirst"] = attention[:8]
    payload["passedChecks"] = passed
    payload["academicFlow"] = _academic_flow(payload)
    if isinstance(payload.get("aiSummary"), dict):
        payload["aiSummary"] = None
    payload.setdefault("aiSummary", None)
    payload.setdefault("aiSummaryStatus", "PENDING")
    return payload


def _summary_context(report: dict[str, Any]) -> dict[str, Any]:
    prepared = prepare_user_friendly_report(report)
    summary = prepared.get("reportSummary") or {}
    metrics = summary.get("metrics") or {}
    rows = prepared.get("whatToFixFirst") or []
    return {
        "score": summary.get("score", 0),
        "result": summary.get("status", "Needs Corrections"),
        "passedChecks": metrics.get("passed", 0),
        "failedChecks": metrics.get("failed", 0),
        "checksToVerify": metrics.get("partial", 0),
        "totalChecks": metrics.get("total", 0),
        "priorityCorrections": [{key: row.get(key) for key in ("priority", "problem", "correction", "status")} for row in rows[:8]],
        "academicRelationships": [{key: item.get(key) for key in ("name", "status")} for item in prepared.get("academicFlow", [])],
    }


def _summary_prompt(report: dict[str, Any]) -> str:
    context = _summary_context(report)
    return (
        "Write one concise, plain-language paragraph for a student compliance report. "
        "Use only the verified structured JSON below. Do not invent university rules, scores, detected values, or issues. "
        "Do not mention JSON, parsers, internal fields, models, or unavailable technical evidence. "
        "Explain the most important correction first and distinguish failed checks from checks that require verification. "
        "Return JSON matching the schema.\n" + json.dumps(context, sort_keys=True)
    )


async def generate_report_summary(
    report: dict[str, Any],
    runner: Callable[..., Awaitable[dict[str, Any]]],
    *,
    rate_key: str,
    model_override: str | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"model_kind": "proposal", "rate_key": rate_key}
    if model_override:
        kwargs["model_override"] = model_override
    result = await runner(_summary_prompt(report), ComplianceReportSummaryPayload, **kwargs)
    prepared = prepare_user_friendly_report(report)
    saved: dict[str, Any] = {
        "status": result.get("status", "UNAVAILABLE"),
        "source": result.get("source"),
        "model": result.get("model"),
        "provider": result.get("provider"),
        "generatedAt": result.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        "inputScope": "STRUCTURED_COMPLIANCE_REPORT_V1",
    }
    parsed = result.get("payload") or {}
    if result.get("status") == "COMPLETED" and isinstance(parsed, dict) and isinstance(parsed.get("summary"), str) and parsed["summary"].strip():
        saved["status"] = "COMPLETED"
        saved["summary"] = parsed["summary"].strip()
        return saved
    saved.update({
        "status": "FALLBACK",
        "source": "DETERMINISTIC_COMPLIANCE_SUMMARY",
        "summary": (prepared.get("reportSummary") or {}).get("deterministicSummary") or deterministic_report_summary(prepared),
        "fallbackReason": result.get("fallback_reason") or "AI summary unavailable",
    })
    return saved
