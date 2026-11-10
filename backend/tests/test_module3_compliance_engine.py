from types import SimpleNamespace

from app.modules.module_03_proposal.compliance_engine import build_compliance_report
from app.modules.module_03_proposal.router import _allowed_template_upload


def test_template_upload_contract_only_accepts_pdf_and_docx():
    assert _allowed_template_upload("baseline.pdf", "application/pdf")
    assert _allowed_template_upload(
        "baseline.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert not _allowed_template_upload("baseline.txt", "text/plain")


def test_compliance_report_reconciles_findings_and_locations():
    submission = SimpleNamespace(
        id=41,
        proposal_key="proposal-41",
        title="Campus Safety Study",
        proposal_type="LONG",
        version=1,
        processing_status="COMPLETED",
        filename="proposal.pdf",
        page_count=3,
        extracted_text="Introduction\nMethodology",
        extracted_fields={
            "page_size": "A4",
            "margin_mm": 25.4,
            "detected_headings": [
                {"name": "Introduction", "page": 1},
                {"name": "Methodology", "page": 2},
            ],
        },
        template_reference_version_id=9,
    )
    report = build_compliance_report(
        submission=submission,
        rules={"page_size": "A4", "margin_mm": 38.1, "required_sections": ["Introduction", "Methodology", "References"]},
        previous_versions=[{"version": 0, "filename": "old.pdf", "score": 50}],
    )

    assert report["reportSummary"]["metrics"]["total"] == report["finalResults"]["totalChecks"]
    assert report["reportSummary"]["metrics"]["failed"] == report["finalResults"]["failed"]
    assert report["versionHistory"] == [{"version": 0, "filename": "old.pdf", "score": 50}]
    assert any(item["issue"] == "Missing Section" and item["details"] == "References" for item in report["missingSections"])
    margin = next(item for item in report["violations"] if item["title"] == "Left Margin")
    assert margin["pageNumber"] == 1
    assert margin["difference"] == 12.7
