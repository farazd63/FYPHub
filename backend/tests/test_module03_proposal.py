"""Focused Module 03 parser, deterministic audit, and Ollama safety tests."""

import asyncio
import io
import importlib.util
import unittest
from unittest.mock import MagicMock

from app.modules.module_03_proposal.models import M03ReferenceTemplate
from app.modules.module_03_proposal.schemas_baseline import TemplateRuleSet
from app.modules.module_03_proposal.services.admin_template_extractor import extract_baseline_rules
from app.modules.module_03_proposal.router import _baseline_assessment
from app.modules.module_03_proposal.services.ast_parser import parse_document
from app.modules.module_03_proposal.services.template_repository import rule_content_hash, save_rules
from app.modules.module_03_proposal.services.check_1_visual import run_visual_check
from app.modules.module_03_proposal.services.check_2_structural import run_structural_check
from app.modules.module_03_proposal.services.check_3_semantic_llm import run_semantic_check
from app.modules.module_03_proposal.services.compliance_aggregator import aggregate_report


class Module03ServiceTests(unittest.TestCase):
    def test_unsupported_document_is_explicit(self):
        ast = parse_document(b"not a document", "notes.txt", "text/plain")
        self.assertEqual(ast["format"], "TXT")
        self.assertEqual(ast["warnings"][0]["code"], "unsupported_format")

    def test_dynamic_template_rules_have_unknowns_without_invention(self):
        ast = {"pages": [{"page": 1, "width": 595, "height": 842}], "paragraphs": [{"text": "1 Introduction", "page": 1, "font_family": "Arial", "font_size": 12, "line_spacing": 1.15, "paragraph_spacing": 6}], "headings": [{"text": "1 Introduction", "level": 1, "page": 1}], "citations": [], "warnings": []}
        extracted = extract_baseline_rules(ast)
        self.assertEqual(extracted["rules"]["default_font_family"], "Arial")
        self.assertEqual(extracted["rules"]["default_font_size_pt"], 12)
        self.assertEqual(extracted["rules"]["heading_order"], ["1 Introduction"])
        self.assertEqual(extracted["rules"]["caption_style"], "Not detected in reference template")
        TemplateRuleSet(proposal_type="SHORT", confidence=extracted["confidence"], warnings=[item["message"] for item in extracted["warnings"]], runtime_metadata={})

    def test_reference_template_missing_proposal_fields_are_informational(self):
        ast = {
            "pages": [{"page": 1, "width": 595, "height": 842}],
            "paragraphs": [{"text": "1 Introduction", "page": 1, "font_family": "Arial", "font_size": 12}],
            "headings": [{"text": "1 Introduction", "level": 1, "page": 1}],
            "citations": [],
            "warnings": [{"code": "pymupdf_unavailable", "message": "Optional parser unavailable."}],
        }
        extracted = extract_baseline_rules(ast)
        self.assertEqual(extracted["rules"]["reference_template_fields"]["purpose"], "Not specified in reference template")
        self.assertEqual(extracted["rules"]["reference_template_fields"]["objectives"], "Not specified in reference template")
        self.assertFalse(any(item["code"] == "pymupdf_unavailable" for item in extracted["warnings"]))
        self.assertEqual(extracted["confidence"], "MEDIUM")

    @unittest.skipUnless(importlib.util.find_spec("fitz"), "PyMuPDF is not installed in this test environment")
    def test_structured_a4_pdf_extracts_geometry_fonts_spacing_and_headings(self):
        import fitz
        document = fitz.open()
        for _ in range(2):
            page = document.new_page(width=595.276, height=841.89)
            y = 72
            for text in ["1. Introduction", "2. Problem Statement", "3. Objectives", "4. Scope", "5. Methodology", "6. Expected Outcomes", "7. References"]:
                page.insert_text((72, y), text, fontname="Times-Roman", fontsize=12)
                y += 24
        ast = parse_document(document.tobytes(), "approved-template.pdf", "application/pdf")
        extracted = extract_baseline_rules(ast)
        self.assertEqual(ast["page_geometry"]["size"], "A4")
        self.assertAlmostEqual(extracted["rules"]["margins"]["left_mm"], 25.4, delta=2)
        self.assertEqual(extracted["rules"]["default_font_family"], "Times-Roman")
        self.assertEqual(extracted["rules"]["default_font_size_pt"], 12)
        self.assertTrue(extracted["rules"]["line_spacing"] != "unknown")
        self.assertEqual(extracted["rules"]["heading_hierarchy"][0]["level"], 1)
        self.assertIn("1. Introduction", extracted["rules"]["expected_sections"])
        self.assertNotEqual(extracted["confidence"], "LOW")

    @unittest.skipUnless(importlib.util.find_spec("docx"), "python-docx is not installed in this test environment")
    def test_docx_extracts_section_settings_styles_and_captions(self):
        from docx import Document
        from docx.shared import Inches, Pt
        document = Document()
        section = document.sections[0]
        section.top_margin = Inches(1); section.bottom_margin = Inches(1); section.left_margin = Inches(1); section.right_margin = Inches(1)
        style = document.styles["Normal"]; style.font.name = "Times New Roman"; style.font.size = Pt(12)
        heading_style = document.styles["Heading 1"]; heading_style.font.name = "Times New Roman"; heading_style.font.size = Pt(12)
        for heading in ["1. Introduction", "2. Problem Statement", "3. Objectives", "4. Scope", "5. Methodology", "6. Expected Outcomes", "7. References"]:
            paragraph = document.add_paragraph(heading, style="Heading 1")
            paragraph.paragraph_format.space_after = Pt(6)
            paragraph.paragraph_format.line_spacing = 1.5
        document.add_paragraph("Figure 1: System architecture")
        stream = io.BytesIO(); document.save(stream)
        ast = parse_document(stream.getvalue(), "approved-template.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        extracted = extract_baseline_rules(ast)
        self.assertEqual(ast["page_geometry"]["size"], "Letter")
        self.assertEqual(extracted["rules"]["default_font_size_pt"], 12)
        self.assertEqual(extracted["rules"]["margins"]["left_mm"], 25.4)
        self.assertTrue(ast["captions"])
        self.assertNotEqual(extracted["confidence"], "LOW")

    def test_incomplete_template_is_low_or_medium_with_clear_warning(self):
        extracted = extract_baseline_rules({"pages": [{"page": 1}], "paragraphs": [{"text": "Title"}], "headings": [], "warnings": []})
        self.assertIn(extracted["confidence"], {"LOW", "MEDIUM"})
        self.assertTrue(any("complete structured official template" in item["message"] for item in extracted["warnings"]))

    def test_duplicate_rule_values_are_not_written_without_confirmation(self):
        session = MagicMock()
        session.scalar.side_effect = [1, 42]
        template = M03ReferenceTemplate(id=7, template_type="SHORT", extracted_rules={"margins": {"left_mm": 25.4}}, confidence="MEDIUM")
        version, created = save_rules(session, template)
        self.assertEqual((version, created), (1, False))
        session.add.assert_not_called()
        self.assertEqual(rule_content_hash(template.extracted_rules), rule_content_hash({"margins": {"left_mm": 25.4}}))

    def test_empty_reference_template_reports_only_structural_failure(self):
        extracted = extract_baseline_rules({"pages": [], "paragraphs": [], "headings": [], "warnings": []})
        self.assertEqual(extracted["confidence"], "LOW")
        self.assertEqual(extracted["warnings"][0]["code"], "structural_baseline_insufficient")
        self.assertNotIn("required_fields_missing", {item["code"] for item in extracted["warnings"]})

    def test_complete_baseline_is_activation_ready(self):
        row = M03ReferenceTemplate(
            extraction_status="EXTRACTED",
            confidence="HIGH",
            extracted_rules={
                "baseline_status": "COMPLETE",
                "expected_sections": ["Introduction"],
                "heading_order": ["Introduction"],
                "heading_hierarchy": [{"text": "Introduction", "level": 1}],
                "margins": {"left_mm": 25.4, "right_mm": 25.4, "top_mm": 25.4, "bottom_mm": 25.4},
                "default_font_family": "Times-Roman",
                "default_font_size_pt": 12,
                "line_spacing": 24,
                "paragraph_spacing": 6,
            },
        )
        assessment = _baseline_assessment(row)
        self.assertEqual(assessment, {"status": "COMPLETE", "missing_fields": []})

    def test_incomplete_baseline_requires_partial_activation(self):
        row = M03ReferenceTemplate(extraction_status="EXTRACTED", confidence="MEDIUM", extracted_rules={"baseline_status": "INCOMPLETE", "missing_fields": ["Margins", "Expected section: Methodology"]})
        assessment = _baseline_assessment(row)
        self.assertEqual(assessment["status"], "INCOMPLETE")
        self.assertIn("Margins", assessment["missing_fields"])
        self.assertIn("Confidence MEDIUM", assessment["missing_fields"])

    def test_activation_mode_is_represented_on_template_history_rows(self):
        row = M03ReferenceTemplate(activation_mode="PARTIAL")
        self.assertEqual(row.activation_mode, "PARTIAL")

    def test_tier_one_and_two_findings_are_advisory_and_evidenced(self):
        baseline = {"rules": {"default_font_family": "Arial", "default_font_size_pt": 12, "expected_sections": ["Introduction", "Methodology"]}}
        ast = {"paragraphs": [{"text": "Introduction", "page": 1, "font_family": "Calibri", "font_size": 11}], "headings": [{"text": "Introduction", "page": 1}], "citations": [], "warnings": []}
        visual = run_visual_check(ast, baseline)
        structural = run_structural_check(ast, baseline)
        self.assertTrue(visual["findings"])
        self.assertTrue(any(item["rule_reference"] == "required_section" for item in structural["findings"]))
        report = aggregate_report("SHORT", {"id": 1}, {"proposal_id": "p", "extraction_status": "EXTRACTED"}, visual, structural, {"status": "UNAVAILABLE", "runtime": "ollama-local"})
        self.assertEqual(report["status"], "NEEDS_REVISION")
        self.assertIn("advisory", report["advisory_summary"].casefold())

    def test_ollama_unavailable_does_not_fabricate(self):
        result = asyncio.run(run_semantic_check({"paragraphs": []}, model=""))
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["supported_links"], [])
        self.assertEqual(result["missing_links"], [])
        self.assertTrue(result["advisory"])


if __name__ == "__main__":
    unittest.main()
