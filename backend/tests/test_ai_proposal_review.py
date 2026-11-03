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

    def test_missing_document_fallback_is_unavailable_and_structured(self):
        row = type("Proposal", (), {"problem_statement": "", "objectives": "", "scope": "", "methodology": ""})()
        result = _ai_fallback(row, None)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["source"], "DETERMINISTIC_FALLBACK")
        self.assertEqual(result["provider"], "ollama")
        self.assertEqual(result["model"], "llama3.1:8b")
        self.assertEqual([item["section"] for item in result["findings"]], ["problem_statement", "objectives", "scope", "methodology", "abstract_purpose", "expected_outcomes", "proposed_solution"])
        self.assertTrue(all(item["source"] == "DETERMINISTIC" for item in result["findings"]))

    def test_fallback_preserves_deterministic_evidence(self):
        row = type("Proposal", (), {"problem_statement": "Students cannot find relevant books.", "objectives": "Recommend relevant books.", "scope": "Library recommendations", "methodology": "Hybrid ranking"})()
        document = type("Document", (), {"extracted_text": "", "extracted_fields": {"purpose": "Improve library discovery", "objectives": "Recommend relevant books", "methodology": "Hybrid ranking", "expected_outcomes": "Faster discovery", "proposed_solution": "Recommendation dashboard"}})()
        result = _ai_fallback(row, document)
        findings = {item["section"]: item for item in result["findings"]}
        self.assertNotEqual(findings["problem_statement"]["evidence"], "No evidence was detected.")
        self.assertNotEqual(findings["objectives"]["evidence"], "No evidence was detected.")
        self.assertNotEqual(findings["methodology"]["evidence"], "No evidence was detected.")
        self.assertNotEqual(findings["abstract_purpose"]["evidence"], "No evidence was detected.")
        self.assertNotEqual(findings["expected_outcomes"]["evidence"], "No evidence was detected.")
        self.assertNotEqual(findings["proposed_solution"]["evidence"], "No evidence was detected.")


if __name__ == "__main__":
    unittest.main()
