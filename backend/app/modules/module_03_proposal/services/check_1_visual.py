"""Deterministic visual/layout comparison against a dynamic baseline."""

from typing import Any


def _finding(check: str, severity: str, rule: str, student: Any, baseline: Any, evidence: dict, remediation: str, confidence: str = "MEDIUM") -> dict:
    return {"check_name": check, "severity": severity, "rule_reference": rule, "student_value": student, "baseline_value": baseline, "evidence": evidence, "remediation": remediation, "confidence": confidence}


def run_visual_check(ast: dict, baseline: dict) -> dict:
    findings: list[dict] = []
    rules = baseline.get("rules", {})
    for key, label in (("default_font_family", "default font family"), ("default_font_size_pt", "default font size"), ("margins", "margins"), ("line_spacing", "line spacing"), ("paragraph_spacing", "paragraph spacing")):
        expected = rules.get(key, "unknown")
        if expected == "unknown" or expected == {}:
            findings.append(_finding("CHECK_1_VISUAL", "INFO", f"template.{key}", "unknown", expected, {"pages": []}, f"Review {label} manually; the baseline did not expose a safe value.", "UNKNOWN"))
            continue
        student = ast.get("margins") if key == "margins" else next((item.get("font_family" if key == "default_font_family" else "font_size" if key == "default_font_size_pt" else key) for item in ast.get("paragraphs", []) if item.get("font_family" if key == "default_font_family" else "font_size" if key == "default_font_size_pt" else key) is not None), "unknown")
        if student != "unknown" and student != expected:
            findings.append(_finding("CHECK_1_VISUAL", "WARNING", f"template.{key}", student, expected, {"pages": [item.get("page") for item in ast.get("paragraphs", [])[:5]]}, f"Align the document with the detected baseline {label}.", "MEDIUM"))
    return {"status": "PASS_WITH_WARNINGS" if findings else "PASS", "findings": findings, "warnings": ast.get("warnings", [])}
