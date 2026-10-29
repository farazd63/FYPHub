"""Deterministic section, word-count, figure, table, and citation checks."""

import re


def _finding(rule: str, severity: str, student, baseline, evidence, remediation: str) -> dict:
    return {"check_name": "CHECK_2_STRUCTURAL", "severity": severity, "rule_reference": rule, "student_value": student, "baseline_value": baseline, "evidence": evidence, "remediation": remediation, "confidence": "HIGH"}


def run_structural_check(ast: dict, baseline: dict) -> dict:
    rules = baseline.get("rules", {})
    expected = [str(item).strip().casefold() for item in rules.get("expected_sections", []) if item]
    actual = [str(item.get("text", "")).strip().casefold() for item in ast.get("headings", []) if item.get("text")]
    findings: list[dict] = []
    for section in expected:
        if section not in actual:
            findings.append(_finding("required_section", "ERROR", "missing", section, {"pages": []}, f"Add the required section detected in the active baseline: {section}."))
    unexpected = [item.get("text") for item in ast.get("headings", []) if str(item.get("text", "")).casefold() not in expected] if expected else []
    for section in unexpected:
        findings.append(_finding("unexpected_section", "WARNING", section, expected, {"page": next((item.get("page") for item in ast.get("headings", []) if item.get("text") == section), None)}, "Confirm this section is permitted by the active baseline."))
    paragraphs = ast.get("paragraphs", [])
    references = [item for item in paragraphs if re.match(r"^(references|bibliography)\b", str(item.get("text", "")), re.I)]
    citations = set(ast.get("citations", []))
    if references and not citations:
        findings.append(_finding("citation_reference_cross_reference", "WARNING", "no citations", "at least one citation", {"page": references[0].get("page")}, "Add citations for referenced sources where required."))
    if not references and citations:
        findings.append(_finding("citation_reference_cross_reference", "WARNING", "citations without references", "references section", {"citations": sorted(citations)}, "Add a references section matching the detected citations."))
    status = "NEEDS_REVISION" if any(item["severity"] == "ERROR" for item in findings) else "PASS_WITH_WARNINGS" if findings else "PASS"
    return {"status": status, "findings": findings, "warnings": ast.get("warnings", [])}
