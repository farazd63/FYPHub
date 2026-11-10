from types import SimpleNamespace

from app.modules.module_03_proposal.compliance_engine import build_change_summary, build_compliance_report
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


def test_compliance_report_checks_structure_and_academic_consistency():
    submission = SimpleNamespace(
        id=42,
        proposal_key="proposal-42",
        title="Library Recommendation",
        proposal_type="SHORT",
        version=1,
        processing_status="COMPLETED",
        filename="proposal.docx",
        page_count=4,
        extracted_text="Problem Statement\nStudents cannot find books.\nObjectives\nRecommend books.\nMethodology\nHybrid ranking.",
        extracted_fields={
            "purpose": {"value": "Students cannot find relevant books."},
            "objectives": {"value": "Recommend relevant books to students."},
            "methodology": {"value": "Hybrid ranking evaluates relevant books."},
            "proposed_solution": {"value": "A book recommendation service."},
            "scope": {"value": "University library books."},
            "expected_outcomes": {"value": "Faster book discovery."},
            "alignment": "JUSTIFY",
            "heading_style": "Heading 1",
            "reference_count": 1,
            "appendix_count": 0,
            "caption_count": 2,
            "detected_headings": [{"name": "Problem Statement", "page": 1}],
        },
        template_reference_version_id=10,
    )
    report = build_compliance_report(
        submission=submission,
        rules={"alignment": "JUSTIFY", "heading_style": "Heading 1", "required_references": 1, "required_captions": 2, "required_sections": ["Problem Statement"]},
    )
    assert "Academic Consistency" in {category["name"] for category in report["categories"]}
    assert report["academicConsistency"]
    assert not any(item["title"] == "References" and item["status"] == "Non-Compliant" for item in report["violations"])


def test_version_change_summary_is_structured_and_advisory():
    summary = build_change_summary(
        {"purpose": {"value": "Find books"}, "objectives": {"value": "Search books"}},
        {"purpose": {"value": "Find and recommend books"}, "objectives": {"value": "Rank books"}},
        1,
        2,
    )
    assert summary["source"] == "AI_ASSISTED_DETERMINISTIC"
    assert summary["fromVersion"] == 1
    assert summary["toVersion"] == 2
    assert summary["changedSections"]


def test_module3_lifecycle_and_review_routes_are_exposed():
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/proposal-compliance/submissions/{submission_id}/withdraw" in paths
    assert "/api/v1/proposal-compliance/submissions/{submission_id}/status" in paths
    assert "/api/v1/proposal-compliance/submissions/{submission_id}" in paths
