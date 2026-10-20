"""Rollback-isolated read-only audit viewer tests."""
import unittest
from datetime import datetime, timezone
from urllib.parse import urlencode
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from app.models import AdminAuditEvent
from tests import test_admin_users as fixtures

class AuditHistoryTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.AdminUserTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.AdminUserTests.tearDownClass.__func__)
    get_test_db = classmethod(fixtures.AdminUserTests.get_test_db.__func__)
    setUp = fixtures.AdminUserTests.setUp

    def add_events(self):
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        stamp = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
        events = [AdminAuditEvent(actor_id=self.admin_id, affected_user_id=None, target_type="ACADEMIC_CYCLE", target_id=987654, action="academic_cycle_updated", created_at=stamp, changed_values={"before": {"code": "OLD", "password_hash": "secret", "nested": {"token": "secret"}}, "after": {"code": "NEW", "session_token": "secret"}, "password": "secret"}), AdminAuditEvent(actor_id=self.admin_id, affected_user_id=self.user_id, target_type="USER", target_id=self.user_id, action="legacy_unknown_action", created_at=stamp, changed_values={"password": "secret", "token": "secret"}), AdminAuditEvent(actor_id=self.admin_id, affected_user_id=self.user_id, target_type="USER", target_id=self.user_id, action="account_created", created_at=stamp, changed_values={"role": "STUDENT", "password_hash": "secret"})]
        session.add_all(events); session.flush(); ids = [event.id for event in events]; session.commit(); session.close(); return ids

    def get(self, path): return fixtures.request("GET", path, token=self.token)
    def test_authorization_and_missing(self):
        self.assertEqual(fixtures.request("GET", "/api/v1/admin/audit-events")[0], 401)
        self.assertEqual(fixtures.request("GET", "/api/v1/admin/audit-events", token=self.student_token)[0], 403)
        self.assertEqual(fixtures.request("GET", "/api/v1/admin/audit-events/1", token=self.student_token)[0], 403)
        self.assertEqual(self.get("/api/v1/admin/audit-events/2147483647")[0], 404)
        self.connection.execute(text("update users set is_active=false where id=:id"), {"id": self.admin_id})
        self.assertEqual(self.get("/api/v1/admin/audit-events")[0], 401)

    def test_filter_pagination_order_and_read_only(self):
        ids = self.add_events()
        before = self.connection.execute(text("select count(*) from admin_audit_events where actor_id=:id"), {"id": self.admin_id}).scalar_one()
        query = urlencode({"actor_id": self.admin_id, "page": 1, "page_size": 2, "from_at": "2026-10-20T17:00:00+05:00", "to_at": "2026-10-20T12:00:00Z"})
        status, body = self.get("/api/v1/admin/audit-events?" + query)
        self.assertEqual(status, 200); self.assertEqual((body["total"], body["total_pages"]), (3, 2)); self.assertEqual([e["id"] for e in body["items"]], [ids[2], ids[1]])
        status, page2 = self.get(f"/api/v1/admin/audit-events?actor_id={self.admin_id}&page_size=2&page=2"); self.assertEqual([e["id"] for e in page2["items"]], [ids[0]])
        status, result = self.get(f"/api/v1/admin/audit-events?actor_id={self.admin_id}&action=academic_cycle_updated&target_type=ACADEMIC_CYCLE&target_id=987654"); self.assertEqual(result["total"], 1); self.assertEqual(result["items"][0]["id"], ids[0])
        self.assertEqual(self.get(f"/api/v1/admin/audit-events/{ids[0]}")[1]["target_id"], 987654)
        self.assertEqual(self.connection.execute(text("select count(*) from admin_audit_events where actor_id=:id"), {"id": self.admin_id}).scalar_one(), before)
        for sql in ("update admin_audit_events set action='changed' where id=:id", "delete from admin_audit_events where id=:id"):
            nested = self.connection.begin_nested()
            try:
                with self.assertRaises(DBAPIError): self.connection.execute(text(sql), {"id": ids[0]})
            finally: nested.rollback()

    def test_legacy_and_sensitive_data_exclusion(self):
        ids = self.add_events()
        _, event = self.get(f"/api/v1/admin/audit-events/{ids[0]}")
        self.assertEqual(event["changed_values"], {"before": {"code": "OLD"}, "after": {"code": "NEW"}})
        self.assertIsNone(event["affected_user_id"]); self.assertEqual(event["actor_id"], self.admin_id)
        _, legacy = self.get(f"/api/v1/admin/audit-events/{ids[1]}"); self.assertEqual(legacy["changed_values"], {})
        _, created = self.get(f"/api/v1/admin/audit-events/{ids[2]}"); self.assertEqual(created["changed_values"], {"role": "STUDENT"})
        self.assertNotIn("secret", str(event) + str(legacy) + str(created))

    def test_strict_filters(self):
        for query in ("page_size=101", "page=0", "actor_id=0", "target_id=-1", "action=", "unknown=x", "page=1&page=2", "from_at=2026-10-20T12:00:00", "from_at=2026-10-21T00:00:00Z&to_at=2026-10-20T00:00:00Z"):
            with self.subTest(query=query): self.assertEqual(self.get("/api/v1/admin/audit-events?" + query)[0], 422)
