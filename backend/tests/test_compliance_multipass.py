import unittest


class CompliancePdfTests(unittest.TestCase):
    def test_pdf_includes_unverifiable_findings_even_when_failed_count_is_zero(self):
        import fitz

        from app.modules.module_03_proposal.router import _render_pdf

        report = {
            "reportSummary": {
                "score": 79,
                "status": "Review Required",
                "metrics": {"passed": 19, "failed": 0, "partial": 5, "total": 24},
            },
            "categories": [
                {
                    "name": "Formatting",
                    "checks": [
                        {
                            "name": "Page size",
                            "status": "UNVERIFIABLE",
                            "expected": "A4",
                            "actual": None,
                            "evidence": "Cannot measure page size & margins.",
                        }
                    ],
                }
            ],
            "violations": [],
        }
        with fitz.open(stream=_render_pdf(report), filetype="pdf") as pdf:
            text = "".join(page.get_text() for page in pdf)
        self.assertIn("Page size", text)
        self.assertIn("Could not verify this requirement from the uploaded document.", text)
        self.assertIn("Update the document to match the approved template page size rule.", text)
