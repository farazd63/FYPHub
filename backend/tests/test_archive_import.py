"""Excel imports preserve source columns without an archive schema."""
from io import BytesIO
from pathlib import Path
import unittest
from openpyxl import Workbook
from app.archived_projects import parse_archive_workbook, _archive_import_project
from app.models import AcademicCycle

class ArchiveImportValidationTests(unittest.TestCase):
    def cycle(self):
        return AcademicCycle(id=1, code="FYP-2026-FALL", display_name="FYP 2026 Fall", academic_year=2026, session="FALL", registration_open=True)

    def workbook(self, rows, extra_sheet=None):
        workbook = Workbook()
        for row in rows:
            workbook.active.append(row)
        if extra_sheet:
            sheet = workbook.create_sheet("Other")
            for row in extra_sheet:
                sheet.append(row)
        output = BytesIO(); workbook.save(output)
        return output.getvalue()

    def test_arbitrary_columns_and_values_are_preserved(self):
        result = parse_archive_workbook(self.workbook([["Student", "Custom detail"], ["Ayesha", "Original content"]]), self.cycle())
        item = result["valid_rows"][0]
        self.assertEqual(item["data"], {"A": "Ayesha", "B": "Original content"})
        self.assertEqual([column["label"] for column in item["columns"]], ["Student", "Custom detail"])
        project = _archive_import_project(item, self.cycle())
        self.assertEqual(project.source_metadata["cells"], item["data"])
        self.assertEqual(project.project_scope, "")
        self.assertIsNone(project.project_code)

    def test_legacy_xls_keeps_columns_values_and_dates(self):
        content = Path(__file__).with_name("fixtures").joinpath("archive-flexible.xls").read_bytes()
        result = parse_archive_workbook(content, self.cycle())
        item = result["valid_rows"][0]
        self.assertEqual([column["label"] for column in item["columns"]], ["Topic", "Member", "Member", "Date"])
        self.assertEqual(item["data"], {"A": "Original XLS", "B": "Ali", "C": "Sara", "D": "2025-04-03 00:00:00"})

    def test_no_required_fields_or_cycle_matching(self):
        result = parse_archive_workbook(self.workbook([["Academic Year", "Completion Percentage"], ["2025", "unfinished"]]), self.cycle())
        self.assertEqual(result["invalid_rows"], [])
        self.assertEqual(result["valid_rows"][0]["data"]["B"], "unfinished")

    def test_duplicate_and_blank_headers_and_blank_cells(self):
        result = parse_archive_workbook(self.workbook([["Member", "Member", None], ["Ali", None, "Extra"]]), self.cycle())
        item = result["valid_rows"][0]
        self.assertEqual([column["label"] for column in item["columns"]], ["Member", "Member", ""])
        self.assertEqual(item["data"], {"A": "Ali", "B": "", "C": "Extra"})

    def test_all_worksheets_and_repeated_rows_are_kept(self):
        result = parse_archive_workbook(self.workbook([["Name"], ["Same"], ["Same"]], [["Topic", "Details"], ["Other", "Text"]]), self.cycle())
        self.assertEqual(result["total_rows"], 3)
        self.assertEqual(len(result["sheets"]), 2)
        projects = [_archive_import_project(item, self.cycle()) for item in result["valid_rows"]]
        self.assertEqual(len({project.normalized_title for project in projects}), 3)

    def test_headerless_and_explicit_heading_row(self):
        content = self.workbook([["Report heading"], ["Name", "Details"], ["Ali", "Text"]])
        result = parse_archive_workbook(content, self.cycle(), header_row=2)
        self.assertEqual(result["valid_rows"][0]["data"], {"A": "Ali", "B": "Text"})
        result = parse_archive_workbook(content, self.cycle(), header_row=2, has_headers=False)
        self.assertEqual(result["total_rows"], 2)
        self.assertEqual(result["sheets"][0]["columns"][0]["label"], "")

    def test_formulas_and_excel_errors_are_not_imported_as_content(self):
        result = parse_archive_workbook(self.workbook([["Calculation", "Error"], ["=1+2", "#REF!"]]), self.cycle())
        self.assertEqual(result["total_rows"], 0)
        self.assertEqual(result["skipped_rows"], 1)

    def test_stops_after_last_email_and_ignores_trailing_formula_or_spacing_rows(self):
        rows = [
            ["Name", "Email", "Detail"],
            ["Ali", "ali@example.com", "Real row"],
            ["Sara", "sara@example.com", "Real row"],
            ["   ", "   ", "   "],
            ["=A4", "=B4", "Displayed formula value"],
            ["Tail", "not-an-email", "Must not be imported"],
        ]
        result = parse_archive_workbook(self.workbook(rows), self.cycle())
        self.assertEqual(result["total_rows"], 2)
        self.assertEqual([row["data"]["B"] for row in result["valid_rows"]], ["ali@example.com", "sara@example.com"])
        self.assertEqual(result["valid_rows"][-1]["row"], 3)

    def test_whitespace_only_cells_are_blank(self):
        result = parse_archive_workbook(self.workbook([["Name", "Email"], ["  ", "person@example.com"]]), self.cycle())
        self.assertEqual(result["valid_rows"][0]["data"], {"A": "", "B": "person@example.com"})

if __name__ == "__main__":
    unittest.main()
