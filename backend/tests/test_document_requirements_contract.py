from app.document_requirements import MIMES, SECTION_STATUS, router, student_router
from app.models import DocumentSubmission, DocumentSubmissionVersion, DocumentUploadRequirement
from app.main import app
from app.document_requirements import _stored_path
from app.schemas.document_requirements import RequirementWrite

def test_document_requirement_models_and_routes_exist():
    assert {DocumentUploadRequirement.__tablename__, DocumentSubmission.__tablename__, DocumentSubmissionVersion.__tablename__} == {"document_upload_requirements", "document_submissions", "document_submission_versions"}
    paths = {route.path for route in router.routes}
    assert "/api/v1/document-requirements/{requirement_id}/upload" in paths
    assert "/api/v1/document-requirements/{requirement_id}/submission/versions" in paths
    assert any(route.path == "/api/v1/student/document-requirements" for route in student_router.routes)

def test_supported_file_mimes_and_states():
    assert MIMES["pdf"] == "application/pdf"
    assert MIMES["doc"] == "application/msword"
    assert MIMES["docx"].endswith("wordprocessingml.document")
    assert SECTION_STATUS == {"DRAFT", "ACTIVE", "ARCHIVED"}

def test_exact_document_requirement_paths_are_registered_in_openapi():
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/document-requirements",
        "/api/v1/document-requirements/{requirement_id}",
        "/api/v1/document-requirements/{requirement_id}/publish",
        "/api/v1/document-requirements/{requirement_id}/archive",
        "/api/v1/document-requirements/{requirement_id}/reopen",
    }
    assert expected.issubset(paths)
    assert "get" in paths["/api/v1/document-requirements"]
    assert "post" in paths["/api/v1/document-requirements"]
    assert "patch" in paths["/api/v1/document-requirements/{requirement_id}"]

def test_storage_reference_is_relative_and_path_traversal_is_rejected():
    assert _stored_path("document-requirements/1/2/file.pdf").name == "file.pdf"
    import pytest
    with pytest.raises(Exception):
        _stored_path("../../outside.pdf")

def test_file_format_adapter_preserves_single_and_combined_formats():
    from datetime import datetime, timezone
    for selected, expected in ((["PDF"], ["pdf"]), (["DOC"], ["doc"]), (["DOCX"], ["docx"]), (["PDF", "DOC", "DOCX"], ["pdf", "doc", "docx"])):
        value = RequirementWrite(title="Document", due_date=datetime.now(timezone.utc), assigned_to="ALL_STUDENTS", allowed_file_types=selected)
        assert value.allowed_file_types == expected
    all_formats = ["PDF", "DOC", "DOCX", "TEX", "TXT", "MD", "JPG", "JPEG", "PNG", "GIF", "WEBP", "SVG", "MP4", "MOV", "AVI", "MKV", "WEBM", "MP3", "WAV", "M4A", "OGG", "XLS", "XLSX", "CSV", "PPT", "PPTX", "ZIP", "RAR", "7Z"]
    assert set(RequirementWrite(title="All", due_date=datetime.now(timezone.utc), assigned_to="ALL_STUDENTS", allowed_file_types=all_formats).allowed_file_types) == {x.lower() for x in all_formats}
