import tempfile
import unittest
from pathlib import Path

import fitz
from docx import Document

from app.document_preview import render_document_preview


class DocumentPreviewTests(unittest.TestCase):
    def test_pdf_preview_returns_original_pdf_pages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "student.pdf"
            document = fitz.open()
            page = document.new_page()
            page.insert_text((72, 72), "Actual student document")
            document.save(source)
            document.close()

            preview = render_document_preview(source, "application/pdf", source.name, root)

            self.assertEqual(preview.content, source.read_bytes())
            self.assertEqual(preview.page_count, 1)
            self.assertEqual(preview.conversion, "original-pdf")

    def test_docx_preview_is_pdf_and_is_cached(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "student.docx"
            document = Document()
            document.add_heading("Actual proposal", level=1)
            document.add_paragraph("This is the uploaded document content.")
            document.save(source)

            preview = render_document_preview(source, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", source.name, root)
            cached = render_document_preview(source, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", source.name, root)

            self.assertTrue(preview.content.startswith(b"%PDF"))
            self.assertGreaterEqual(preview.page_count, 1)
            self.assertEqual(cached.content, preview.content)
            self.assertTrue(list((root / "module-3" / "preview-cache").glob("*.pdf")))


if __name__ == "__main__":
    unittest.main()
