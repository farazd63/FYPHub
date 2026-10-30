import unittest

from app.pdf_extraction import _extract_fields, _normalize_text


class PdfExtractionFieldTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
