import asyncio
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from starlette.requests import Request

from app.modules.module_03_proposal.ai_report import REPORT_VERSION, report_prompt
from app.modules.module_03_proposal.router import _report_fingerprint, _summary_source_fingerprint, generate_compliance_summary


class ComplianceAiSummaryTests(unittest.TestCase):
    def setUp(self):
        self.actor = SimpleNamespace(id=7)
        self.row = SimpleNamespace(
            id=4,
            extracted_text="The report evaluates an accessible campus safety intervention and records its measured outcomes.",
            extracted_fields={"scope": "Full scope", "template": "University template content"},
            sha256="source-hash",
        )
        self.original = {"reportSummary": {"score": 65, "status": "Review Required"}, "violations": [], "missingSections": []}
        self.report = SimpleNamespace(report=copy.deepcopy(self.original))
        self.db = Mock()
        self.db.get.return_value = self.row
        self.db.scalar.return_value = self.report
        self.request = Request({"type": "http", "method": "POST", "headers": []})
        self.summary = " ".join(f"word{index}" for index in range(220))

    def run_summary(self, result, allowed=True):
        with patch("app.modules.module_03_proposal.router._can_view", return_value=allowed), patch("app.modules.module_03_proposal.router.run_ai_json", new_callable=AsyncMock, return_value=result) as provider:
            output = asyncio.run(generate_compliance_summary(4, self.request, self.actor, self.db))
            return output, provider

    def test_generation_sends_only_report_text_and_returns_final_summary(self):
        output, provider = self.run_summary({"status": "COMPLETED", "model": "llama3.1:8b", "payload": {"summary": self.summary}})
        prompt = provider.await_args.args[0]
        self.assertEqual(output["summary"], self.summary)
        self.assertEqual(output["input_scope"], "STUDENT_REPORT_TEXT_V2")
        self.assertEqual(output["report_format"], REPORT_VERSION)
        self.assertEqual(output["source_sha256"], "source-hash")
        self.assertIn(self.row.extracted_text, prompt)
        self.assertNotIn("compliance_report", prompt)
        self.assertNotIn("proposal_fields", prompt)
        self.assertNotIn("University template content", prompt)
        self.assertNotIn("<COMPLIANCE_FINDINGS>", prompt)
        self.assertEqual(self.report.report["reportSummary"], self.original["reportSummary"])

    def test_completed_summary_is_cached_by_report_text_fingerprint(self):
        output, _ = self.run_summary({"status": "COMPLETED", "model": "llama3.1:8b", "payload": {"summary": self.summary}})
        cached, provider = self.run_summary({})
        self.assertEqual(cached, output)
        provider.assert_not_awaited()

    def test_unavailable_model_returns_grounded_fallback_without_changing_results(self):
        output, _ = self.run_summary({"status": "UNAVAILABLE", "model": "llama3.1:8b"})
        self.assertEqual(output["status"], "COMPLETED")
        self.assertEqual(output["source"], "DETERMINISTIC_FALLBACK")
        self.assertGreaterEqual(output["summary_word_count"], 200)
        self.assertLessEqual(output["summary_word_count"], 300)
        self.assertNotIn("\n", output["summary"])
        self.assertEqual(self.report.report["reportSummary"], self.original["reportSummary"])

    def test_prompt_ignores_legacy_context_keys(self):
        prompt = report_prompt({
            "student_report_text": self.row.extracted_text,
            "proposal_fields": {"secret": "should not be sent"},
            "compliance_report": {"secret": "should not be sent"},
            "template": "should not be sent",
        })
        self.assertIn(self.row.extracted_text, prompt)
        self.assertNotIn("should not be sent", prompt)
        self.assertNotIn("<PROPOSAL_DATA>", prompt)
        self.assertNotIn("<COMPLIANCE_FINDINGS>", prompt)

    def test_old_full_document_cache_is_not_reused(self):
        self.report.report["aiSummary"] = {"status": "COMPLETED", "summary": "Old summary", "report_fingerprint": _report_fingerprint(self.report.report), "input_scope": "FULL_DOCUMENT_AND_REPORT_V1"}
        _, provider = self.run_summary({"status": "UNAVAILABLE"})
        provider.assert_awaited_once()

    def test_previous_summary_format_is_not_reused(self):
        self.report.report["aiSummary"] = {"status": "COMPLETED", "summary": "Old labeled summary", "source_fingerprint": _summary_source_fingerprint(self.row.extracted_text), "input_scope": "STUDENT_REPORT_TEXT_V2", "report_format": "STUDENT_REPORT_SUMMARY_V1"}
        _, provider = self.run_summary({"status": "UNAVAILABLE"})
        provider.assert_awaited_once()

    def test_unauthorized_user_cannot_generate_summary(self):
        with self.assertRaises(HTTPException) as error:
            self.run_summary({}, allowed=False)
        self.assertEqual(error.exception.status_code, 404)

    def test_report_fingerprint_ignores_summary_but_detects_changed_findings(self):
        with_summary = {**self.original, "aiSummary": {"summary": "Old summary"}}
        self.assertEqual(_report_fingerprint(self.original), _report_fingerprint(with_summary))
        with_summary["violations"] = [{"title": "New finding"}]
        self.assertNotEqual(_report_fingerprint(self.original), _report_fingerprint(with_summary))
