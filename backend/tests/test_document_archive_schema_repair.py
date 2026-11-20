"""Regression: document archive schema required by document endpoints must exist."""

from sqlalchemy import inspect, text

from app.database import engine


def test_archive_schema_columns_exist():
    columns = {table: {col["name"] for col in inspect(engine).get_columns(table)} for table in (
        "document_upload_requirements",
        "document_submissions",
        "teams",
    )}
    assert "section_id" in columns["document_upload_requirements"]
    assert "project_id" in columns["document_submissions"]
    assert "requirement_section_id" in columns["document_submissions"]
    assert "group_number" in columns["teams"]
    with engine.connect() as connection:
        assert connection.execute(text("SELECT to_regclass('public.document_requirement_sections')")).scalar()
        assert connection.execute(text("SELECT to_regclass('public.document_submission_review_events')")).scalar()
        assert connection.execute(text("SELECT to_regclass('public.document_archive_review_queue')")).scalar()
        assert connection.execute(text("SELECT COUNT(*) FROM document_upload_requirements WHERE section_id IS NULL")).scalar() == 0
