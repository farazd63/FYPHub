"""Isolated non-operational reminder configuration coverage."""
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import text
from app import main
from app.auth import utc_now
from app.database import SessionLocal
from app.models import AcademicCycle, AcademicDeadline, AcademicDeadlineVersion, User, UserRole
from app.models.reminder_rule import ReminderRule, ReminderRuleVersion
from app.schemas.reminder_rules import RuleWrite
from tests import test_academic_deadlines as deadline_tests
from tests.test_auth_sessions import request

class ReminderTests(unittest.TestCase):
    setUpClass = classmethod(deadline_tests.AcademicDeadlineTests.setUpClass.__func__)
    tearDownClass = classmethod(deadline_tests.AcademicDeadlineTests.tearDownClass.__func__)
    db = classmethod(deadline_tests.AcademicDeadlineTests.db.__func__)
    setUp = deadline_tests.AcademicDeadlineTests.setUp
    headers = deadline_tests.AcademicDeadlineTests.headers
    deadline_payload = deadline_tests.AcademicDeadlineTests.payload

    def deadline(self, **changes):
        code, _, body = request("POST", "/api/v1/admin/academic-deadlines", {**self.deadline_payload(), **changes}, headers=self.headers(self.admin_token))
        self.assertEqual(code, 201)
        return body

    def payload(self, deadline_id):
        return {"academic_cycle_id": self.cycle_id, "deadline_version_id": deadline_id, "name": "Test rule", "description": None, "category": "REMINDER", "direction": "BEFORE", "elapsed_minutes": 60}

    def test_auth_origin_and_validation(self):
        self.assertEqual(request("GET", "/api/v1/admin/reminder-rules")[0], 401)
        self.assertEqual(request("GET", "/api/v1/admin/reminder-rules", headers=self.headers(self.student_token))[0], 403)
        deadline = self.deadline(); payload = self.payload(deadline["versions"][0]["id"])
        self.assertEqual(request("POST", "/api/v1/admin/reminder-rules", payload, headers=self.headers(self.admin_token, "http://evil.example"))[0], 403)
        self.assertEqual(request("POST", "/api/v1/admin/reminder-rules/preview", {k: payload[k] for k in ("deadline_version_id", "direction", "elapsed_minutes")}, headers=self.headers(self.admin_token, "http://evil.example"))[0], 403)
        for update in ({"elapsed_minutes": 0}, {"elapsed_minutes": True}, {"elapsed_minutes": 1.5}, {"direction": "AT"}, {"category": "OTHER"}, {"extra": "x"}, {"name": " "}):
            self.assertEqual(request("POST", "/api/v1/admin/reminder-rules", {**payload, **update}, headers=self.headers(self.admin_token))[0], 422)
        self.assertEqual(request("POST", "/api/v1/admin/reminder-rules", {**payload, "deadline_version_id": 2147483647}, headers=self.headers(self.admin_token))[0], 404)

    def test_dst_exact_link_history_and_cross_cycle(self):
        deadline = self.deadline(local_due_at="2026-03-08T03:30", time_zone="America/New_York", utc_offset="-04:00", due_at_utc="2026-03-08T07:30:00Z")
        version_id = deadline["versions"][0]["id"]; payload = self.payload(version_id)
        code, _, preview = request("POST", "/api/v1/admin/reminder-rules/preview", {k: payload[k] for k in ("deadline_version_id", "direction", "elapsed_minutes")}, headers=self.headers(self.admin_token))
        self.assertEqual(code, 200); self.assertEqual(preview["calculated_at_utc"], "2026-03-08T06:30:00+00:00"); self.assertTrue(preview["calculated_local"].startswith("2026-03-08T01:30:00-05:00"))
        code, _, rule = request("POST", "/api/v1/admin/reminder-rules", payload, headers=self.headers(self.admin_token)); self.assertEqual(code, 201)
        next_deadline = {k: v for k, v in self.deadline_payload().items() if k != "academic_cycle_id"}
        self.assertEqual(request("POST", f"/api/v1/admin/academic-deadlines/{deadline['id']}/versions", next_deadline, headers=self.headers(self.admin_token))[0], 201)
        code, _, history = request("GET", f"/api/v1/admin/reminder-rules/{rule['id']}", headers=self.headers(self.admin_token)); self.assertEqual(history["versions"][0]["deadline_version_id"], version_id)
        other = AcademicCycle(code=f"other-{uuid4().hex[:8]}", display_name="Other cycle"); self.connection.execute(text("insert into academic_cycles (code, display_name, registration_open) values (:code, :name, false)"), {"code": other.code, "name": other.display_name})
        other_id = self.connection.execute(text("select id from academic_cycles where code=:code"), {"code": other.code}).scalar_one()
        foreign = self.deadline(academic_cycle_id=other_id); next_rule = {k:v for k,v in payload.items() if k != "academic_cycle_id"}; next_rule["deadline_version_id"] = foreign["versions"][0]["id"]
        self.assertEqual(request("POST", f"/api/v1/admin/reminder-rules/{rule['id']}/versions", next_rule, headers=self.headers(self.admin_token))[0], 422)
        next_rule["deadline_version_id"] = version_id; next_rule["name"] = "Second"; self.assertEqual(request("POST", f"/api/v1/admin/reminder-rules/{rule['id']}/versions", next_rule, headers=self.headers(self.admin_token))[0], 201)
        _, _, history = request("GET", f"/api/v1/admin/reminder-rules/{rule['id']}", headers=self.headers(self.admin_token)); self.assertEqual([v["version_number"] for v in history["versions"]], [1, 2]); self.assertEqual(history["versions"][0]["name"], "Test rule")

    def test_overflow_and_atomic_audit(self):
        deadline = self.deadline(); payload = self.payload(deadline["versions"][0]["id"])
        self.assertEqual(request("POST", "/api/v1/admin/reminder-rules/preview", {"deadline_version_id": payload["deadline_version_id"], "direction": "BEFORE", "elapsed_minutes": 2147483647}, headers=self.headers(self.admin_token))[0], 422)
        count_before = self.connection.execute(text("select count(*) from reminder_rules where academic_cycle_id=:id"), {"id": self.cycle_id}).scalar_one()
        audit_before = self.connection.execute(text("select count(*) from admin_audit_events where actor_id=:id"), {"id": self.admin_id}).scalar_one()
        with patch.object(main, "add_admin_audit_event", side_effect=RuntimeError("failure")):
            self.assertEqual(request("POST", "/api/v1/admin/reminder-rules", payload, headers=self.headers(self.admin_token))[0], 500)
        self.assertEqual(self.connection.execute(text("select count(*) from reminder_rules where academic_cycle_id=:id"), {"id": self.cycle_id}).scalar_one(), count_before)
        self.assertEqual(self.connection.execute(text("select count(*) from admin_audit_events where actor_id=:id"), {"id": self.admin_id}).scalar_one(), audit_before)
        code, _, rule = request("POST", "/api/v1/admin/reminder-rules", payload, headers=self.headers(self.admin_token)); self.assertEqual(code, 201)
        before = self.connection.execute(text("select count(*) from admin_audit_events where actor_id=:id"), {"id": self.admin_id}).scalar_one()
        next_rule = {k:v for k,v in payload.items() if k != "academic_cycle_id"}
        with patch.object(main, "add_admin_audit_event", side_effect=RuntimeError("failure")):
            self.assertEqual(request("POST", f"/api/v1/admin/reminder-rules/{rule['id']}/versions", next_rule, headers=self.headers(self.admin_token))[0], 500)
        self.assertEqual(self.connection.execute(text("select count(*) from reminder_rule_versions where rule_id=:id"), {"id": rule["id"]}).scalar_one(), 1)
        self.assertEqual(self.connection.execute(text("select count(*) from admin_audit_events where actor_id=:id"), {"id": self.admin_id}).scalar_one(), before)

    def test_concurrent_allocation(self):
        suffix = uuid4().hex[:10]; setup = SessionLocal(); ids = None
        try:
            actor = User(full_name="Rule race", email=f"rule-{suffix}@example.com", password_hash="test", role=UserRole.ADMIN); cycle = AcademicCycle(code=f"RR-{suffix}", display_name="Rule race"); setup.add_all([actor, cycle]); setup.flush()
            deadline = AcademicDeadline(academic_cycle_id=cycle.id); setup.add(deadline); setup.flush(); dv = AcademicDeadlineVersion(academic_deadline_id=deadline.id, version_number=1, name="Race", due_at_utc=utc_now(), time_zone="UTC", created_by_id=actor.id); setup.add(dv); setup.flush(); rule = ReminderRule(academic_cycle_id=cycle.id); setup.add(rule); setup.flush(); setup.add(ReminderRuleVersion(rule_id=rule.id, version_number=1, deadline_version_id=dv.id, name="Base", category="REMINDER", direction="BEFORE", elapsed_minutes=1, created_by_id=actor.id)); setup.commit(); ids = (actor.id, cycle.id, deadline.id, dv.id, rule.id)
            gate = threading.Barrier(2); results = []; errors = []
            def run():
                session = SessionLocal()
                try:
                    user = session.get(User, ids[0]); gate.wait(timeout=5); result = main.create_reminder_rule_version(ids[4], RuleWrite(deadline_version_id=ids[3], name="Next", category="REMINDER", direction="BEFORE", elapsed_minutes=1), type("Request", (), {"headers": {}})(), user, session); results.append(result["version_number"])
                except Exception as e: errors.append(e)
                finally: session.close()
            with patch.object(main, "add_admin_audit_event", return_value=None):
                threads = [threading.Thread(target=run) for _ in range(2)]
                for thread in threads: thread.start()
                for thread in threads: thread.join(timeout=5)
            self.assertFalse(any(t.is_alive() for t in threads)); self.assertEqual(errors, []); self.assertEqual(sorted(results), [2, 3])
        finally:
            setup.close()
            if ids:
                cleanup = SessionLocal()
                for sql, value in (("delete from reminder_rule_versions where rule_id=:id", ids[4]), ("delete from reminder_rules where id=:id", ids[4]), ("delete from academic_deadline_versions where academic_deadline_id=:id", ids[2]), ("delete from academic_deadlines where id=:id", ids[2]), ("delete from academic_cycles where id=:id", ids[1]), ("delete from users where id=:id", ids[0])): cleanup.execute(text(sql), {"id": value})
                cleanup.commit(); cleanup.close()
