"""Pure validation tests for the historical XLSX archive importer."""

from io import BytesIO
import unittest

from openpyxl import Workbook

from app.archived_projects import ARCHIVE_COLUMNS, parse_archive_workbook
from app.models import AcademicCycle


class ArchiveImportValidationTests(unittest.TestCase):
    def workbook(self, values: dict[str, object]) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append([label for label, _, _ in ARCHIVE_COLUMNS])
        sheet.append([values.get(key, "x") for _, key, _ in ARCHIVE_COLUMNS])
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()

    def cycle(self) -> AcademicCycle:
        return AcademicCycle(id=1, code="FYP-2026-FALL", display_name="FYP 2026 Fall", academic_year=2026, session="FALL", registration_open=True)

    def test_valid_row_is_previewable(self):
        result = parse_archive_workbook(self.workbook({"title": "Old FYP", "academic_year": "2026", "session_name": "FALL", "completion_percentage": "85"}), self.cycle())
        self.assertEqual((len(result["valid_rows"]), len(result["invalid_rows"])), (1, 0))

    def test_cycle_mismatch_is_invalid(self):
        result = parse_archive_workbook(self.workbook({"academic_year": "2025", "session_name": "SPRING"}), self.cycle())
        self.assertEqual(len(result["valid_rows"]), 0)
        self.assertTrue(any("does not match" in error for error in result["invalid_rows"][0]["errors"]))

    def test_formula_cells_are_rejected(self):
        result = parse_archive_workbook(self.workbook({"title": "=HYPERLINK(\"http://evil\")"}), self.cycle())
        self.assertEqual(len(result["valid_rows"]), 0)
        self.assertIn("Formula cells are not allowed", result["invalid_rows"][0]["errors"])


if __name__ == "__main__":
    unittest.main()
