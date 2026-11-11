import asyncio
import unittest

from app.modules.module_03_proposal.ai_report import (
    ComplianceNarrativePayload, generate_full_report, report_prompt, source_parts,
)


class MultipassTests(unittest.TestCase):
    def test_pdf_includes_unverifiable_findings_even_when_failed_count_is_zero(self):
        import fitz
        from app.modules.module_03_proposal.router import _render_pdf
        report = {"reportSummary": {"score": 79, "status": "Review Required", "metrics": {"passed": 19, "failed": 0, "partial": 5, "total": 24}},
                  "categories": [{"name": "Formatting", "checks": [{"name": "Page size", "status": "UNVERIFIABLE", "expected": "A4", "actual": None, "evidence": "Cannot measure page size & margins."}]}], "violations": []}
        with fitz.open(stream=_render_pdf(report), filetype="pdf") as pdf:
            text = "".join(page.get_text() for page in pdf)
        self.assertIn("79%", text)
        self.assertIn("UNVERIFIABLE", text)
        self.assertIn("Cannot measure page size & margins.", text)

    def test_unicode_partition_is_lossless(self):
        text = "شروع🙂 end\n" * 10000
        parts = source_parts(text)
        self.assertEqual("".join(parts), text)
        self.assertTrue(all(len(part.encode("utf-8")) <= 8000 for part in parts))

    def test_every_part_of_large_source_is_processed_before_final_synthesis(self):
        context = {"proposal_text": "Full proposal🙂 " * 12000 + "END_OF_PROPOSAL", "proposal_fields": {},
                   "compliance_report": {"reportSummary": {"score": 79}, "categories": []}}
        calls = []
        async def runner(prompt, schema, **kwargs):
            calls.append((prompt, schema))
            return {"status": "COMPLETED", "payload": {"summary": "Grounded factual notes."}}
        result = asyncio.run(generate_full_report(context, runner, rate_key="test"))
        source_calls = [prompt for prompt, schema in calls if schema is not ComplianceNarrativePayload]
        recovered = "".join(prompt.split("<SOURCE_SEGMENT>\n", 1)[1].rsplit("\n</SOURCE_SEGMENT>", 1)[0] for prompt in source_calls)
        self.assertEqual(recovered, report_prompt(context))
        self.assertIs(calls[-1][1], ComplianceNarrativePayload)
        self.assertEqual(result["processed_parts"], len(source_calls))
        self.assertTrue(all(len(prompt.encode("utf-8")) < 12000 for prompt, _ in calls))

    def test_failed_segment_does_not_return_partial_completed_report(self):
        context = {"proposal_text": "Source " * 6000, "proposal_fields": {}, "compliance_report": {}}
        calls = []
        async def runner(prompt, schema, **kwargs):
            calls.append(prompt)
            return {"status": "UNAVAILABLE", "fallback_reason": "provider_unavailable"}
        result = asyncio.run(generate_full_report(context, runner, rate_key="test"))
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["processed_parts"], 0)
        self.assertNotIn("payload", result)

    def test_large_intermediate_notes_are_reduced_before_final_request(self):
        context = {"proposal_text": "Source " * 14000, "proposal_fields": {}, "compliance_report": {}}
        calls = []
        async def runner(prompt, schema, **kwargs):
            calls.append(prompt)
            notes = "Facts " * 300 if "synthesis" not in prompt else "Condensed facts."
            return {"status": "COMPLETED", "payload": {"summary": notes}}
        result = asyncio.run(generate_full_report(context, runner, rate_key="test"))
        self.assertEqual(result["status"], "COMPLETED")
        self.assertTrue(any("Segment synthesis" in prompt for prompt in calls))
        self.assertLess(len(calls[-1].encode("utf-8")), 12000)
