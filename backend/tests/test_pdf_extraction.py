import io
import unittest

from docx import Document

from app.pdf_extraction import PdfExtractionError, _extract_fields, _normalize_text, extract_proposal_document


class PdfExtractionFieldTests(unittest.TestCase):
    def test_combined_preview_headings_keep_title_and_purpose_separate(self):
        fields = _extract_fields("Proposal Title\nFYPHub\nTopic / Area\nAcademic automation\nProblem Statement / Purpose\nCentralize FYP activities.\nObjectives\nTrack proposals.\nMethodology / Approach\nModular software.\nScope\nAcademic workflows.")
        self.assertEqual(fields["title"]["value"], "FYPHub")
        self.assertEqual(fields["purpose"]["value"], "Centralize FYP activities.")
        self.assertEqual(fields["topic"]["value"], "Academic automation")
        self.assertEqual(fields["methodology"]["value"], "Modular software.")
        self.assertEqual(fields["missing_required_fields"], [])

    def test_demo_headings_extract_all_sections_until_next_heading(self):
        fields = _extract_fields(
            "Title:\nCampus Safety Study\nPurpose: Improve campus safety.\n"
            "Problem Statement: Students lack clear safety guidance.\n"
            "Objectives:\nMap risks\nPropose controls\n"
            "Methodology: Interviews and observation.\nExpected Outcomes: A safer campus."
        )
        self.assertEqual(fields["title"]["value"], "Campus Safety Study")
        self.assertIn("Improve campus safety.", fields["purpose"]["value"])
        self.assertIn("Students lack clear safety guidance.", fields["purpose"]["value"])
        self.assertEqual(fields["objectives"]["value"], "Map risks Propose controls")
        self.assertEqual(fields["methodology"]["value"], "Interviews and observation.")
        self.assertEqual(fields["expected_outcomes"]["value"], "A safer campus.")
        self.assertEqual(fields["title"]["source_page"], 1)
        self.assertEqual(fields["methodology"]["source"], "page 1")
        self.assertEqual(fields["missing_required_fields"], [])

    def test_labels_are_case_insensitive_and_aliases_are_supported(self):
        fields = _extract_fields(
            "PROJECT TITLE : Alias title\nPROJECT PURPOSE: Alias purpose\n"
            "PROJECT OBJECTIVES: Alias objectives\nMETHOD: Alias method\nOUTCOMES: Alias outcome"
        )
        self.assertEqual(fields["title"]["value"], "Alias title")
        self.assertEqual(fields["purpose"]["value"], "Alias purpose")
        self.assertEqual(fields["objectives"]["value"], "Alias objectives")
        self.assertEqual(fields["methodology"]["value"], "Alias method")
        self.assertEqual(fields["expected_outcomes"]["value"], "Alias outcome")

    def test_missing_field_remains_not_detected_without_fabrication(self):
        fields = _extract_fields("Title: Real title\nObjectives: Real objectives")
        self.assertEqual(fields["title"]["display"], "Real title")
        self.assertEqual(fields["purpose"]["value"], None)
        self.assertEqual(fields["purpose"]["display"], "Not detected in PDF")
        self.assertIn("purpose", fields["missing_required_fields"])

    def test_normalization_preserves_sections_and_colon_spacing(self):
        self.assertEqual(_normalize_text(" Title\r\n :  Value \r\n\r\nPurpose\t:Thing "), "Title\n: Value\nPurpose: Thing")

    def test_docx_upload_extracts_fields_with_immutable_file_metadata(self):
        document = Document()
        document.add_paragraph("Title: DOCX Proposal")
        document.add_paragraph("Purpose: Improve campus safety.")
        payload = io.BytesIO()
        document.save(payload)
        result = extract_proposal_document(
            payload.getvalue(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "proposal.docx",
        )
        self.assertEqual(result.content_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.assertEqual(result.extracted_fields["title"]["value"], "DOCX Proposal")
        self.assertEqual(result.extracted_fields["purpose"]["value"], "Improve campus safety.")
        self.assertEqual(len(result.sha256), 64)

    def test_unsupported_upload_is_rejected(self):
        with self.assertRaises(PdfExtractionError) as error:
            extract_proposal_document(b"plain text", "text/plain", "proposal.txt")
        self.assertEqual(error.exception.code, "invalid_pdf")


if __name__ == "__main__":
    unittest.main()
