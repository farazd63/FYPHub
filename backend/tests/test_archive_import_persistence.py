"""Confirm and edit flexible imports inside a rolled-back database transaction."""
import asyncio
from io import BytesIO
import unittest
from pathlib import Path
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request
from app.database import engine
from app.models import AcademicCycle, ArchivedProject, User, UserRole
from app.archived_projects import ArchiveUpdate, archive_import_confirm, update_archive, search_archives
import test_archive_import

class ArchiveImportPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        self.actor = self.session.scalar(select(User).where(User.role == UserRole.ADMIN))
        self.cycle = self.session.scalar(select(AcademicCycle).where(AcademicCycle.academic_year.is_not(None), AcademicCycle.session.is_not(None)))
        if self.actor is None or self.cycle is None:
            self.skipTest("An admin and academic cycle are required for persistence checks")
        self.request = Request({"type": "http", "method": "POST", "path": "/", "headers": [(b"origin", b"http://localhost:5173"), (b"host", b"localhost:8010")], "client": ("127.0.0.1", 1)})

    def tearDown(self):
        self.session.close()
        self.transaction.rollback()
        self.connection.close()

    def test_confirm_and_edit_only_original_columns(self):
        content = test_archive_import.ArchiveImportValidationTests().workbook([["Member", "Member", "Extra"], ["Ali", "Sara", "Only original content"], ["Ali", "Sara", "Only original content"]])
        result = asyncio.run(archive_import_confirm(request=self.request, academic_cycle_id=self.cycle.id,
            file=UploadFile(filename="arbitrary.xlsx", file=BytesIO(content)), header_row=None, has_headers=True, actor=self.actor, session=self.session))
        self.assertEqual(result["imported_count"], 2)
        project = result["projects"][0]
        self.assertEqual(project["source_metadata"]["cells"], {"A": "Ali", "B": "Sara", "C": "Only original content"})
        self.assertEqual(project["project_scope"], "")
        updated = update_archive(project["id"], ArchiveUpdate(source_metadata={"cells": {"A": "Updated", "B": "", "C": "New text"}}), self.request, self.actor, self.session)
        self.assertEqual(updated["source_metadata"]["cells"], {"A": "Updated", "B": "", "C": "New text"})
        self.assertEqual(updated["source_metadata"]["columns"], project["source_metadata"]["columns"])
        self.session.expire_all()
        stored = self.session.get(ArchivedProject, project["id"])
        self.assertEqual(stored.source_metadata["cells"]["C"], "New text")
        self.assertEqual(stored.title, "Updated")
        found = search_archives(q="Updated", academic_year=None, session_name=None, department=None, supervisor=None, technology=None, project_scope=None, completion_stage=None, _=self.actor, session=self.session)
        self.assertIn(project["id"], [row["id"] for row in found["results"]])
        with self.assertRaises(HTTPException):
            update_archive(project["id"], ArchiveUpdate(source_metadata={"cells": {"A": "Lost columns"}}), self.request, self.actor, self.session)

    def test_http_preview_and_confirm_use_flexible_columns(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.auth import get_current_user
        from app.database import get_db
        def database():
            yield self.session
        app.dependency_overrides[get_current_user] = lambda: self.actor
        app.dependency_overrides[get_db] = database
        try:
            with TestClient(app) as client:
                for filename in ("sample.xlsx", "sample.xls"):
                    content = test_archive_import.ArchiveImportValidationTests().workbook([["Custom column"], ["Original value"]]) if filename.endswith(".xlsx") else Path(__file__).with_name("fixtures").joinpath("archive-flexible.xls").read_bytes()
                    arguments = {"data": {"academic_cycle_id": str(self.cycle.id), "has_headers": "true"}, "files": {"file": (filename, content)}, "headers": {"Origin": "http://localhost:5173"}}
                    preview = client.post("/api/v1/admin/archive/import/preview", **arguments)
                    self.assertEqual(preview.status_code, 200, preview.text)
                    self.assertEqual(preview.json()["total_rows"], 1)
                    confirmed = client.post("/api/v1/admin/archive/import/confirm", **arguments)
                    self.assertEqual(confirmed.status_code, 200, confirmed.text)
                    self.assertEqual(confirmed.json()["imported_count"], 1)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
