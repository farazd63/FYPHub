import unittest

from app.supervisor_requests import _ai_fallback


class AiProposalReviewTests(unittest.TestCase):
    def test_deterministic_fallback_returns_structured_findings(self):
        row = type("Proposal", (), {"problem_statement": "", "objectives": "", "scope": "", "methodology": ""})()
        document = type("Document", (), {"extracted_text": "", "extracted_fields": {}})()
        result = _ai_fallback(row, document)
        findings = result["findings"]
        self.assertTrue(findings)
        for finding in findings:
            self.assertIn(finding["status"], {"PASS", "WARNING", "FAIL"})
            self.assertIn(finding["source"], {"AI", "DETERMINISTIC"})
            self.assertIn("section", finding)
            self.assertIn("feedback", finding)
            self.assertIn("suggestion", finding)
            self.assertIn("confidence", finding)


if __name__ == "__main__":
    unittest.main()
