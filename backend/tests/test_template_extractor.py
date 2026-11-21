import io
import unittest

import fitz
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Mm, Pt

from app.modules.module_03_proposal.template_extractor import extract_template_rules, normalize_template_rules


class TemplateExtractorTests(unittest.TestCase):
    def test_pdf_rules_are_measured_by_side_and_do_not_expose_counts(self):
        document = fitz.open()
        page = document.new_page(width=595.28, height=841.89)
        page.insert_text((72, 72), "1. Introduction", fontsize=14, fontname="Times-Bold")
        page.insert_text((72, 110), "This is the official body text for the template.", fontsize=12, fontname="Times-Roman")
        page.insert_text((72, 122), "This second body line verifies PDF line spacing extraction.", fontsize=12, fontname="Times-Roman")
        page.insert_text((72, 145), "2. Methodology", fontsize=14, fontname="Times-Bold")
        page.insert_text((72, 183), "Method details belong here.", fontsize=12, fontname="Times-Roman")
        page.insert_text((72, 220), "References", fontsize=14, fontname="Times-Bold")
        page.insert_text((270, 810), "Page 1", fontsize=10, fontname="Times-Roman")
        data = document.tobytes()
        document.close()

        rules = extract_template_rules(data, "application/pdf", "official.pdf")
        self.assertEqual(rules["page_size"], "A4")
        self.assertEqual(rules["line_spacing"], 1.0)
        self.assertIn("Introduction", "\n".join(rules["required_sections"]))
        self.assertEqual(rules["required_references"], 1)
        self.assertTrue(rules["page_numbering"])
        self.assertIn("left_margin_mm", rules)
        self.assertIn("right_margin_mm", rules)
        self.assertNotEqual(rules["left_margin_mm"], rules["right_margin_mm"])
        self.assertNotIn("table_count", rules)
        self.assertNotIn("figure_count", rules)
        self.assertNotIn("reference_count", rules)
        self.assertNotIn("appendix_count", rules)

    def test_docx_rules_use_explicit_section_settings_and_normalize_fonts(self):
        document = Document()
        section = document.sections[0]
        section.page_width = Mm(210)
        section.page_height = Mm(297)
        section.left_margin = Mm(25.4)
        section.right_margin = Mm(12.7)
        section.top_margin = Mm(20)
        section.bottom_margin = Mm(30)
        normal = document.styles["Normal"]
        normal.font.name = "Times New Roman"
        normal.font.size = Pt(12)
        heading = document.add_paragraph("Introduction", style="Heading 1")
        body = document.add_paragraph("This body paragraph establishes the official formatting.")
        body.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        body.paragraph_format.line_spacing = 1.5
        stream = io.BytesIO()
        document.save(stream)

        rules = extract_template_rules(stream.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "official.docx")
        self.assertEqual(rules["page_size"], "A4")
        self.assertEqual(rules["left_margin_mm"], 25.4)
        self.assertEqual(rules["right_margin_mm"], 12.7)
        self.assertEqual(rules["top_margin_mm"], 20.0)
        self.assertEqual(rules["bottom_margin_mm"], 30.0)
        self.assertEqual(rules["font_family"], "Times New Roman")
        self.assertEqual(rules["font_size_pt"], 12.0)
        self.assertEqual(rules["line_spacing"], 1.5)
        self.assertEqual(rules["alignment"], "JUSTIFY")
        self.assertEqual(rules["heading_style"], "Heading 1")
        self.assertEqual(rules["required_sections"], ["Introduction"])
        self.assertNotIn("table_count", rules)

    def test_normalization_removes_legacy_counts_and_splits_literal_newlines(self):
        rules = normalize_template_rules({"margin_mm": 25.4, "table_count": 4, "required_sections": "Introduction\\nMethodology", "font_family": "TimesNewRomanPSMT"})
        self.assertEqual(rules["required_sections"], ["Introduction", "Methodology"])
        self.assertNotIn("margin_mm", rules)
        self.assertNotIn("table_count", rules)
