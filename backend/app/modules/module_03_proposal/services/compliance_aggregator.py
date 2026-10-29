"""Versioned advisory report aggregation."""

from collections import Counter


def aggregate_report(proposal_type: str, baseline: dict, proposal: dict, check_1: dict, check_2: dict, check_3: dict) -> dict:
    findings = list(check_1.get("findings", [])) + list(check_2.get("findings", []))
    counts = Counter(item.get("severity", "INFO") for item in findings)
    if any(item.get("severity") == "ERROR" for item in findings):
        status = "NEEDS_REVISION"
    elif check_3.get("status") == "UNAVAILABLE" and not findings:
        status = "UNAVAILABLE"
    elif findings:
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"
    return {"proposal_type": proposal_type, "baseline_template": baseline, "proposal_document": proposal, "extraction_status": proposal.get("extraction_status", "UNKNOWN"), "check_1": check_1, "check_2": check_2, "check_3": check_3, "status": status, "total_findings": len(findings), "severity_counts": dict(counts), "remediation": [item.get("remediation") for item in findings if item.get("remediation")], "advisory_summary": "AI findings are advisory only and do not replace Supervisor, Coordinator, or Admin approval.", "runtime_metadata": {"check_3_runtime": check_3.get("runtime"), "check_3_model": check_3.get("model")}}
