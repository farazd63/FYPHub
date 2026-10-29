"""Focused logical archive, versioning, ranking, and role-isolation tests."""

import asyncio
from io import BytesIO
import json
import unittest
from datetime import timedelta
from uuid import uuid4
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE_NAME, utc_now
from app.database import engine, get_db
from app.main import app
from app.archived_projects import ArchiveCreate, ArchiveUpdate, admin_archive_list, create_archive, read_archive, rollback_archive_metadata, search_archives, set_archive_active, update_archive, upload_archive_document, archive_document_history
from app.models import AdminAuditEvent, ArchivedProject, ArchivedProjectDocument, AuthSession, User, UserRole
from app.security import generate_session_token, hash_session_token


class ArchivedProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = engine.connect()
        cls.transaction = cls.connection.begin()
        if cls.connection.execute(text("SELECT current_database()")).scalar_one() != "fyphub_p1":
            raise RuntimeError("Archive tests require fyphub_p1.")
        app.dependency_overrides[get_db] = cls.get_test_db

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.pop(get_db, None)
        cls.transaction.rollback(); cls.connection.close()

    @classmethod
    def get_test_db(cls):
        session = Session(bind=cls.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try: yield session
        finally: session.close()

    def setUp(self) -> None:
        suffix = uuid4().hex[:10]
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        self.admin = User(full_name="Archive Admin", email=f"archive-admin-{suffix}@example.com", password_hash="test", role=UserRole.ADMIN)
        self.student = User(full_name="Archive Student", email=f"archive-student-{suffix}@example.com", registration_number=f"ARC{suffix}", password_hash="test", role=UserRole.STUDENT)
        self.panel = User(full_name="Archive Panel", email=f"archive-panel-{suffix}@example.com", password_hash="test", role=UserRole.PANEL_MEMBER)
        session.add_all([self.admin, self.student, self.panel]); session.flush()
        self.tokens = {}
        for name, user in (("admin", self.admin), ("student", self.student), ("panel", self.panel)):
            token = generate_session_token(); self.tokens[name] = token
            session.add(AuthSession(user_id=user.id, token_hash=hash_session_token(token), expires_at=utc_now() + timedelta(hours=1)))
        session.commit(); session.close()

    def call(self, method: str, path: str, payload=None, token: str | None = None, *, body: bytes | None = None, content_type: str = "application/json"):
        parsed = urlsplit(path)
        async def invoke():
            messages = []; received = False
            request_body = body if body is not None else (json.dumps(payload).encode() if payload is not None else b"")
            async def receive():
                nonlocal received
                if not received:
                    received = True; return {"type": "http.request", "body": request_body, "more_body": False}
                return {"type": "http.disconnect"}
            headers = [(b"host", b"testserver"), (b"content-type", content_type), (b"content-length", str(len(request_body)).encode()), (b"origin", b"http://localhost:5173")]
            if token: headers.append((b"cookie", f"{SESSION_COOKIE_NAME}={token}".encode()))
            async def send(message): messages.append(message)
            await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "http", "path": parsed.path, "raw_path": parsed.path.encode(), "query_string": parsed.query.encode(), "headers": headers, "client": ("127.0.0.1", 0), "server": ("127.0.0.1", 80)}, receive, send)
            return messages
        messages = asyncio.run(invoke()); start = next(item for item in messages if item["type"] == "http.response.start"); raw = b"".join(item.get("body", b"") for item in messages if item["type"] == "http.response.body")
        return start["status"], json.loads(raw) if raw else None

    def multipart(self, fields: dict[str, str], filename: str, content: bytes) -> tuple[bytes, str]:
        boundary = "----FYPHubArchiveBoundary"
        parts = []
        for key, value in fields.items(): parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode())
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{filename}\"\r\nContent-Type: application/pdf\r\n\r\n".encode() + content + b"\r\n")
        return b"".join(parts) + f"--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"

    def test_admin_create_search_detail_and_panel_denial(self):
        payload = {"title": "Campus Safety Archive", "abstract_summary": "A campus safety project for search.", "keywords": ["safety", "mapping"], "academic_year": "2026", "department_program": "Computing", "project_scope": "Safety", "completion_stage": "Completed", "implemented_scope": "Risk map", "remaining_gaps": "Needs live deployment", "future_work": "Add sensor feeds", "source_label": "ADMIN_CURATED"}
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        request = __import__("starlette.requests", fromlist=["Request"]).Request({"type": "http", "headers": [(b"origin", b"http://localhost:5173")]})
        created = create_archive(ArchiveCreate(**payload), request, self.admin, session)
        self.assertEqual(created["documents"], [])
        status, search = self.call("GET", "/api/v1/archived-projects/search?q=Campus%20Safety", token=self.tokens["student"])
        self.assertEqual((status, search["results"][0]["match_reason"]), (200, "normalized title match"))
        self.assertEqual(read_archive(created["id"], self.student, session)["title"], payload["title"])
        self.assertEqual(self.call("GET", "/api/v1/archived-projects/search?q=Campus", token=self.tokens["panel"])[0], 403)
        session.close()

    def test_pdf_versions_are_separate_and_student_read_only(self):
        payload = {"title": "Versioned Archive", "abstract_summary": "Versioning test.", "keywords": ["version"], "academic_year": "2026", "department_program": "Computing", "project_scope": "Documents", "completion_stage": "Draft", "implemented_scope": "Metadata", "remaining_gaps": "Upload pending", "future_work": "Add report", "source_label": "ADMIN_CURATED"}
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        request = __import__("starlette.requests", fromlist=["Request"]).Request({"type": "http", "headers": [(b"origin", b"http://localhost:5173")]})
        project = create_archive(ArchiveCreate(**payload), request, self.admin, session)
        pdf = b"%PDF-1.4 sample archive"; body, content_type = self.multipart({"document_type": "SHORT_PROPOSAL"}, "short.pdf", pdf)
        from starlette.datastructures import Headers, UploadFile
        file = UploadFile(file=BytesIO(pdf), filename="short.pdf", headers=Headers({"content-type": "application/pdf"}))
        first = asyncio.run(upload_archive_document(project["id"], request, "SHORT_PROPOSAL", None, file, self.admin, session))
        self.assertEqual(first["version"], 1)
        pdf2 = pdf + b" v2"; file = UploadFile(file=BytesIO(pdf2), filename="short-v2.pdf", headers=Headers({"content-type": "application/pdf"}))
        second = asyncio.run(upload_archive_document(project["id"], request, "SHORT_PROPOSAL", None, file, self.admin, session))
        self.assertEqual(second["version"], 2)
        detail = read_archive(project["id"], self.student, session)
        self.assertEqual((len(detail["documents"]), detail["documents"][0]["version"]), (1, 2))
        history = archive_document_history(project["id"], self.admin, session)
        self.assertEqual([item["version"] for item in history], [2, 1])
        session.close()

    def test_metadata_refresh_duplicate_protection_and_inactive_filtering(self):
        payload = {"title": "Searchable Archive", "abstract_summary": "Original summary.", "keywords": ["robotics"], "academic_year": "2026", "department_program": "Computing", "project_scope": "Robotics", "completion_stage": "Completed", "implemented_scope": "Prototype", "remaining_gaps": "Field testing", "future_work": "Deploy sensors", "source_label": "ADMIN_CURATED"}
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        request = __import__("starlette.requests", fromlist=["Request"]).Request({"type": "http", "headers": [(b"origin", b"http://localhost:5173")]})
        project = create_archive(ArchiveCreate(**payload), request, self.admin, session)
        with self.assertRaises(HTTPException):
            create_archive(ArchiveCreate(**payload), request, self.admin, session)
        updated = update_archive(project["id"], ArchiveUpdate(title="Updated Searchable Archive", abstract_summary="Updated summary."), request, self.admin, session)
        self.assertEqual(updated["normalized_title"], "updated searchable archive")
        self.assertEqual(search_archives(q="Updated Searchable", academic_year=None, project_scope=None, completion_stage=None, session=session, _=self.student)["results"][0]["title"], "Updated Searchable Archive")
        self.assertEqual(search_archives(q="Field testing", academic_year=None, project_scope=None, completion_stage=None, session=session, _=self.student)["results"][0]["match_reason"], "remaining gaps match")
        set_archive_active(project["id"], request, False, self.admin, session)
        self.assertEqual(search_archives(q="Updated Searchable", academic_year=None, project_scope=None, completion_stage=None, session=session, _=self.student)["results"], [])
        admin_rows = admin_archive_list(self.admin, session)
        self.assertTrue(any(row["id"] == project["id"] and row["is_active"] is False for row in admin_rows))
        session.close()

    def test_metadata_audit_snapshot_can_be_rolled_back(self):
        payload = {"title": "Rollback Archive", "abstract_summary": "Before rollback.", "keywords": ["history"], "academic_year": "2026", "department_program": "Computing", "project_scope": "Audit", "completion_stage": "Completed", "implemented_scope": "Snapshot", "remaining_gaps": "None", "future_work": "Maintain", "source_label": "ADMIN_CURATED"}
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        request = __import__("starlette.requests", fromlist=["Request"]).Request({"type": "http", "headers": [(b"origin", b"http://localhost:5173")]})
        project = create_archive(ArchiveCreate(**payload), request, self.admin, session)
        update_archive(project["id"], ArchiveUpdate(title="Rollback Archive Changed", abstract_summary="After rollback."), request, self.admin, session)
        event = session.scalar(select(AdminAuditEvent).where(AdminAuditEvent.target_type == "ARCHIVED_PROJECT", AdminAuditEvent.target_id == project["id"], AdminAuditEvent.action == "archived_project_updated").order_by(AdminAuditEvent.id.desc()))
        restored = rollback_archive_metadata(project["id"], event.id, request, self.admin, session)
        self.assertEqual((restored["title"], restored["abstract_summary"]), (payload["title"], payload["abstract_summary"]))
        session.close()


if __name__ == "__main__":
    unittest.main()
