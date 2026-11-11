import asyncio
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from starlette.requests import Request
from app.modules.module_03_proposal.router import generate_compliance_summary, _report_fingerprint


class ComplianceAiSummaryTests(unittest.TestCase):
    def setUp(self):
        self.actor = SimpleNamespace(id=7)
        self.row = SimpleNamespace(id=4, extracted_text="An accessible campus safety proposal.", extracted_fields={"scope": "Full scope"}, sha256="source-hash")
        self.original = {"reportSummary": {"score": 65, "status": "Review Required"}, "violations": [], "missingSections": []}
        self.report = SimpleNamespace(report=copy.deepcopy(self.original))
        self.db = Mock()
        self.db.get.return_value = self.row
        self.db.scalar.return_value = self.report
        self.request = Request({"type": "http", "method": "POST", "headers": []})
        from app.modules.module_03_proposal.ai_report import MISSING
        self.narrative = {"proposal_title": MISSING, "project_purpose": MISSING, "problem_statement": MISSING, "objectives": [], "methodology": MISSING, "expected_outcomes": MISSING, "overall_assessment": "Review the recorded findings.", "detailed_narrative": "The proposal addresses campus safety. Its recorded compliance findings require further review."}

    def run_summary(self, result, allowed=True):
        with patch("app.modules.module_03_proposal.router._can_view", return_value=allowed), patch("app.modules.module_03_proposal.router.run_ai_json", new_callable=AsyncMock, return_value=result) as provider:
            output = asyncio.run(generate_compliance_summary(4, self.request, self.actor, self.db))
            return output, provider

    def test_generation_preserves_compliance_score_and_caches_result(self):
        output, provider = self.run_summary({"status": "COMPLETED", "model": "llama3.1:8b", "payload": {"summary": self.narrative}})
        self.assertEqual(output["summary"]["detailed_narrative"], self.narrative["detailed_narrative"])
        self.assertEqual(output["summary"]["recorded_compliance_score"], "65")
        self.assertEqual(output["summary"]["recorded_compliance_status"], "Review Required")
        self.assertEqual(self.report.report["reportSummary"], self.original["reportSummary"])
        self.assertEqual(output["source_sha256"], "source-hash")
        cached, provider = self.run_summary({})
        self.assertEqual(cached, output)
        provider.assert_not_awaited()

    def test_unavailable_model_does_not_fabricate_summary_or_change_results(self):
        output, _ = self.run_summary({"status": "UNAVAILABLE", "model": "llama3.1:8b"})
        self.assertEqual(output["status"], "UNAVAILABLE")
        self.assertNotIn("summary", output)
        self.assertEqual(self.report.report["reportSummary"], self.original["reportSummary"])

    def test_complete_proposal_and_report_reach_provider_without_slicing(self):
        import json
        self.row.extracted_text = "Proposal content " * 2000 + "END_OF_PROPOSAL"
        self.report.report["violations"] = [{"title": f"Finding {i}", "severity": "Major", "evidence": "Evidence " * 100, "requirement": "Original requirement", "location": f"Page {i}"} for i in range(20)]
        self.report.report["missingSections"] = [{"issue": f"Section {i}", "details": "Complete detail " * 100} for i in range(20)]
        self.report.report["categories"] = [{"name": "All checks", "checks": list(range(30))}]
        from app.modules.module_03_proposal.ai_report import report_prompt
        prompt = report_prompt({"proposal_text": self.row.extracted_text, "proposal_fields": self.row.extracted_fields, "compliance_report": self.report.report})
        proposal = json.loads(prompt.split("<PROPOSAL_DATA>\n", 1)[1].split("\n</PROPOSAL_DATA>", 1)[0])
        report = json.loads(prompt.split("<COMPLIANCE_FINDINGS>\n", 1)[1].split("\n</COMPLIANCE_FINDINGS>", 1)[0])
        self.assertEqual(proposal["proposal_text"], self.row.extracted_text)
        self.assertEqual(proposal["proposal_fields"], self.row.extracted_fields)
        self.assertEqual(report, self.original | {"violations": self.report.report["violations"], "missingSections": self.report.report["missingSections"], "categories": self.report.report["categories"]})

    def test_detailed_report_preserves_every_source_entry_and_priority(self):
        from app.modules.module_03_proposal.ai_report import assemble_report, MISSING
        report = {"reportSummary": {"score": 23, "status": "Not Compliant"}, "categories": [{"name": "Layout", "checks": [
            {"status": "PASS", "category": "Layout", "severity": "Info", "evidence": "Exact passed message."},
            {"status": "PARTIAL", "category": "Layout", "severity": "Minor", "evidence": "Exact partial message."},
            {"status": "FAIL", "category": "Layout", "severity": "Major", "evidence": "Exact FAILED message — unchanged!", "expected": "A4"},
            {"status": "FAIL", "category": "Document Structure", "name": "Missing section: Methods", "evidence": "Methods missing."}]}],
            "violations": [{"affectedArea": "Layout", "severity": "Major", "evidence": "Separate recorded violation."}],
            "missingSections": [{"issue": "Missing Section", "details": "References"}],
            "academicConsistency": [{"status": "UNVERIFIABLE", "category": "Academic Consistency", "evidence": "Not measurable."}],
            "sectionCompliance": [{"name": "Introduction", "check1": "Pass", "check2": "Partial"}]}
        result = assemble_report({"summary": self.narrative}, {"compliance_report": report})
        findings = result["compliance_findings"]
        self.assertEqual(len(findings), 9)
        self.assertEqual([int(item["priority"]) for item in findings], sorted(int(item["priority"]) for item in findings))
        exact = next(item for item in findings if item["finding"] == "Exact FAILED message — unchanged!")
        self.assertEqual((exact["category"], exact["status"], exact["severity"]), ("Layout", "FAIL", "Major"))
        self.assertEqual(result["recorded_compliance_score"], "23")
        self.assertEqual(result["objectives"], [MISSING])
        self.assertTrue(all(item["recommended_action"] for item in findings if item["priority"] != "4"))
        self.assertEqual(set(result), {"proposal_title", "project_purpose", "problem_statement", "objectives", "methodology", "expected_outcomes", "recorded_compliance_score", "recorded_compliance_status", "overall_assessment", "compliance_findings", "passed_checks", "priority_actions", "detailed_narrative"})

    def test_old_excerpt_summary_is_not_reused(self):
        self.report.report["aiSummary"] = {"status": "COMPLETED", "summary": "Old excerpt summary", "report_fingerprint": _report_fingerprint(self.report.report)}
        _, provider = self.run_summary({"status": "UNAVAILABLE"})
        provider.assert_awaited_once()

    def test_unauthorized_user_cannot_generate_summary(self):
        with self.assertRaises(HTTPException) as error:
            self.run_summary({}, allowed=False)
        self.assertEqual(error.exception.status_code, 404)

    def test_fingerprint_ignores_summary_but_detects_changed_findings(self):
        with_summary = {**self.original, "aiSummary": {"summary": "Old summary"}}
        self.assertEqual(_report_fingerprint(self.original), _report_fingerprint(with_summary))
        with_summary["violations"] = [{"title": "New finding"}]
        self.assertNotEqual(_report_fingerprint(self.original), _report_fingerprint(with_summary))
