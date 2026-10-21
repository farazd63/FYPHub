import threading
import unittest
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import text
from app import main
from app.database import SessionLocal
from app.models import User, UserRole
from app.models.workflow_policy import WorkflowPolicy, WorkflowPolicyVersion
from app.schemas.workflow_policy import PolicyWrite
from app.workflow_policy import create_version
from tests.test_auth_sessions import request
from tests import test_evaluation_rubrics as fixtures

class WorkflowPolicyTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.EvaluationRubricTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.EvaluationRubricTests.tearDownClass.__func__)
    db = classmethod(fixtures.EvaluationRubricTests.db.__func__)
    setUp = fixtures.EvaluationRubricTests.setUp
    headers = fixtures.EvaluationRubricTests.headers
    path = "/api/v1/admin/workflow-policies"
    def payload(self): return {"name": "Draft", "states": ["A", "B"], "transitions": [{"label": "Move", "source": "A", "destination": "B"}]}
    def test_access_origin(self):
        self.assertEqual(request("GET", self.path)[0], 401)
        self.assertEqual(request("GET", self.path, headers=self.headers(self.student_token))[0], 403)
        self.assertEqual(request("POST", self.path, self.payload(), headers=self.headers(self.student_token))[0], 403)
        self.assertEqual(request("POST", self.path, self.payload(), headers=self.headers(self.admin_token, "http://evil.example"))[0], 403)
        self.assertEqual(request("GET", self.path + "/99999999", headers=self.headers(self.admin_token))[0], 404)
    def test_validation(self):
        cases = [{**self.payload(), "name": " "}, {**self.payload(), "states": []}, {**self.payload(), "states": ["A", " a "]}, {**self.payload(), "transitions": [{"label":"X", "source":"A", "destination":"missing"}]}, {**self.payload(), "transitions": [{"label":" ", "source":"A", "destination":"B"}]}, {**self.payload(), "extra": 1}, {**self.payload(), "states": [1]}]
        for value in cases:
            with self.subTest(value=value): self.assertEqual(request("POST", self.path, value, headers=self.headers(self.admin_token))[0], 422)
    def test_history_and_audit_rollback(self):
        code, _, initial = request("POST", self.path, self.payload(), headers=self.headers(self.admin_token)); self.assertEqual(code, 201)
        policy_id = initial["id"]; revised = {"name":"Revised", "states":["C"], "transitions":[]}
        self.assertEqual(request("POST", f"{self.path}/{policy_id}/versions", revised, headers=self.headers(self.admin_token))[0], 201)
        with patch.object(main, "add_admin_audit_event", side_effect=RuntimeError("secret")):
            code, _, body = request("POST", f"{self.path}/{policy_id}/versions", revised, headers=self.headers(self.admin_token))
        self.assertEqual(code, 500); self.assertNotIn("secret", str(body))
        _, _, history = request("GET", f"{self.path}/{policy_id}", headers=self.headers(self.admin_token))
        self.assertEqual([v["version_number"] for v in history["versions"]], [1, 2]); self.assertEqual(history["versions"][0]["states"], ["A", "B"]); self.assertEqual(history["versions"][0]["transitions"], self.payload()["transitions"])
        self.assertEqual(self.connection.execute(text("select count(*) from admin_audit_events where target_type='WORKFLOW_POLICY' and target_id=:id"), {"id":policy_id}).scalar_one(), 2)
    def test_concurrent_versions(self):
        suffix = uuid4().hex; setup = SessionLocal(); actor = User(full_name="Race", email=f"workflow-{suffix}@example.com", password_hash="test", role=UserRole.ADMIN); policy = WorkflowPolicy(); setup.add_all([actor, policy]); setup.flush()
        setup.add(WorkflowPolicyVersion(policy_id=policy.id, version_number=1, name="Initial", states=["A"], transitions=[], created_by_id=actor.id)); setup.commit(); actor_id, policy_id = actor.id, policy.id; setup.close()
        barrier = threading.Barrier(2); results = []; errors = []
        def worker():
            session = SessionLocal()
            try:
                actor = session.get(User, actor_id); barrier.wait(timeout=5)
                result = create_version(policy_id, PolicyWrite(name="Next", states=["A"], transitions=[]), type("Request", (), {"headers": {}})(), actor, session)
                results.append(result["version_number"])
            except Exception as exc: errors.append(exc)
            finally: session.close()
        try:
            with patch.object(main, "add_admin_audit_event", return_value=None):
                threads = [threading.Thread(target=worker) for _ in range(2)]
                for thread in threads: thread.start()
                for thread in threads: thread.join(timeout=10)
                self.assertTrue(all(not thread.is_alive() for thread in threads)); self.assertEqual(errors, []); self.assertEqual(sorted(results), [2, 3])
        finally:
            cleanup = SessionLocal(); cleanup.execute(text("delete from workflow_policy_versions where policy_id=:id"), {"id":policy_id}); cleanup.execute(text("delete from workflow_policies where id=:id"), {"id":policy_id}); cleanup.execute(text("delete from users where id=:id"), {"id":actor_id}); cleanup.commit(); cleanup.close()
