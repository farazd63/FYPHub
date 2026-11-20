import asyncio
import unittest

from app.modules.module_03_proposal.ai_report import (
    ComplianceNarrativePayload,
    SUMMARY_MAX_WORDS,
    SUMMARY_MIN_WORDS,
    generate_full_report,
    report_prompt,
    source_parts,
)


class SummaryGenerationTests(unittest.TestCase):
    def setUp(self):
        self.report_text = "The report evaluates an accessible campus safety intervention and records measured outcomes."
        self.summary = " ".join(f"word{index}" for index in range(220))

    def test_pdf_includes_unverifiable_findings_even_when_failed_count_is_zero(self):
        import fitz

        from app.modules.module_03_proposal.router import _render_pdf

        report = {"reportSummary": {"score": 79, "status": "Review Required", "metrics": {"passed": 19, "failed": 0, "partial": 5, "total": 24}}, "categories": [{"name": "Formatting", "checks": [{"name": "Page size", "status": "UNVERIFIABLE", "expected": "A4", "actual": None, "evidence": "Cannot measure page size & margins."}]}], "violations": []}
        with fitz.open(stream=_render_pdf(report), filetype="pdf") as pdf:
            text = "".join(page.get_text() for page in pdf)
        self.assertIn("Page size", text)
        self.assertIn("Could not verify this requirement from the uploaded document.", text)
        self.assertIn("Update the document to match the approved template page size rule.", text)

    def test_unicode_partition_is_lossless(self):
        text = "Ø´Ø±ÙˆØ¹ðŸ™‚ end\n" * 10000
        parts = source_parts(text)
        self.assertEqual("".join(parts), text)
        self.assertTrue(all(len(part.encode("utf-8")) <= 8000 for part in parts))

    def test_single_pass_uses_only_student_report_text(self):
        context = {
            "student_report_text": self.report_text,
            "proposal_fields": {"secret": "must not be sent"},
            "compliance_report": {"secret": "must not be sent"},
            "template": "must not be sent",
        }
        calls = []

        async def runner(prompt, schema, **kwargs):
            calls.append((prompt, schema, kwargs))
            return {"status": "COMPLETED", "payload": {"summary": self.summary}}

        result = asyncio.run(generate_full_report(context, runner, rate_key="test"))
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][1], ComplianceNarrativePayload)
        self.assertIn(self.report_text, calls[0][0])
        self.assertNotIn("must not be sent", calls[0][0])
        self.assertNotIn("<PROPOSAL_DATA>", calls[0][0])
        self.assertNotIn("<COMPLIANCE_FINDINGS>", calls[0][0])
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["summary_word_count"], 220)
        self.assertEqual(result["generation_mode"], "STUDENT_REPORT_TEXT_SINGLE_PASS")

    def test_short_summary_gets_one_length_repair_pass(self):
        calls = []
        short_summary = " ".join(f"short{index}" for index in range(123))

        async def runner(prompt, schema, **kwargs):
            calls.append(prompt)
            return {"status": "COMPLETED", "payload": {"summary": short_summary if len(calls) == 1 else self.summary}}

        result = asyncio.run(generate_full_report({"student_report_text": self.report_text}, runner, rate_key="test-repair"))

        self.assertEqual(len(calls), 2)
        self.assertIn("length-correction pass", calls[1])
        self.assertIn(self.report_text, calls[1])
        self.assertNotIn("short0", calls[1])
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["summary_word_count"], 220)
        self.assertEqual(result["generation_mode"], "STUDENT_REPORT_TEXT_LENGTH_REPAIR")

    def test_prompt_contains_only_the_report_delimiter_and_text(self):
        prompt = report_prompt({"student_report_text": self.report_text, "proposal_text": "legacy source", "template": "legacy template"})
        self.assertTrue(prompt.startswith("You write concise academic report summaries for a university review system."))
        self.assertIn("<STUDENT_REPORT_TEXT>\n" + self.report_text, prompt)
        self.assertTrue(prompt.endswith("\n</STUDENT_REPORT_TEXT>"))
        self.assertNotIn("legacy source", prompt)
        self.assertNotIn("legacy template", prompt)

    def test_legacy_proposal_text_cannot_be_used_as_summary_source(self):
        async def runner(prompt, schema, **kwargs):
            self.fail("The legacy proposal_text key must not reach the model")

        result = asyncio.run(generate_full_report({"proposal_text": "legacy source"}, runner, rate_key="test"))
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["fallback_reason"], "empty_report_text")

    def test_failed_provider_does_not_return_partial_completed_report(self):
        async def runner(prompt, schema, **kwargs):
            return {"status": "UNAVAILABLE", "fallback_reason": "provider_unavailable"}

        result = asyncio.run(generate_full_report({"student_report_text": self.report_text}, runner, rate_key="test"))
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["source"], "DETERMINISTIC_FALLBACK")
        self.assertGreaterEqual(result["summary_word_count"], SUMMARY_MIN_WORDS)
        self.assertLessEqual(result["summary_word_count"], SUMMARY_MAX_WORDS)
        self.assertNotIn("\n", result["payload"]["summary"])

    def test_provider_exception_returns_grounded_fallback(self):
        async def runner(prompt, schema, **kwargs):
            raise RuntimeError("provider connection failed")

        result = asyncio.run(generate_full_report({"student_report_text": self.report_text}, runner, rate_key="test-exception"))
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["fallback_reason"], "provider_exception")
        self.assertGreaterEqual(result["summary_word_count"], SUMMARY_MIN_WORDS)
        self.assertLessEqual(result["summary_word_count"], SUMMARY_MAX_WORDS)

    def test_rejects_summary_outside_word_range(self):
        async def runner(prompt, schema, **kwargs):
            return {"status": "COMPLETED", "payload": {"summary": "Too brief " * 25}}

        result = asyncio.run(generate_full_report({"student_report_text": self.report_text}, runner, rate_key="test"))
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["source"], "DETERMINISTIC_FALLBACK")
        self.assertEqual(result["fallback_reason"], "summary_word_count_out_of_range")
        self.assertGreaterEqual(result["summary_word_count"], SUMMARY_MIN_WORDS)
        self.assertLessEqual(result["summary_word_count"], SUMMARY_MAX_WORDS)
        self.assertEqual(result["processed_parts"], 1)
        self.assertEqual((SUMMARY_MIN_WORDS, SUMMARY_MAX_WORDS), (200, 300))

    def test_completed_provider_summary_is_normalized_to_one_paragraph(self):
        async def runner(prompt, schema, **kwargs):
            return {"status": "COMPLETED", "payload": {"summary": " ".join(["word"] * 220) + "\n\nMore evidence."}}

        result = asyncio.run(generate_full_report({"student_report_text": self.report_text}, runner, rate_key="test-one-paragraph"))
        self.assertEqual(result["status"], "COMPLETED")
        self.assertNotIn("\n", result["payload"]["summary"])

    def test_provider_section_labels_are_removed_from_final_summary(self):
        labeled = "Main findings: " + " ".join(["word"] * 220) + " Important compliance issues: More evidence."

        async def runner(prompt, schema, **kwargs):
            return {"status": "COMPLETED", "payload": {"summary": labeled}}

        result = asyncio.run(generate_full_report({"student_report_text": self.report_text}, runner, rate_key="test-label-cleanup"))
        self.assertEqual(result["status"], "COMPLETED")
        self.assertNotIn("Main findings:", result["payload"]["summary"])
        self.assertNotIn("Important compliance issues:", result["payload"]["summary"])
