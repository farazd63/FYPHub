import unittest
import threading
import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.auth import SESSION_COOKIE_NAME, utc_now
from app.individual_verification import consume_creator_proof, consume_identity_proof
from app.database import SessionLocal
from app.models import AcademicCycle, ApprovedStudent, IdentityChallenge, IdentityProof, RosterImport, User, UserRole
from app.security import generate_session_token, hash_session_token
from tests import test_group_channels as fixture
from tests.test_auth_sessions import request

class IdentityVerificationTests(unittest.TestCase):
    setUpClass = classmethod(fixture.GroupChannelTests.setUpClass.__func__)
    tearDownClass = classmethod(fixture.GroupChannelTests.tearDownClass.__func__)
    get_test_db = classmethod(fixture.GroupChannelTests.get_test_db.__func__)
    setUp = fixture.GroupChannelTests.setUp
    def prepare(self):
        suffix = uuid4().hex
        batch = self.connection.execute(text('insert into roster_imports (academic_cycle_id,imported_by_id,confirmation_hash) values (:c,:a,:h) returning id'), {'c':self.cycle.id,'a':self.admin.id,'h':suffix}).scalar_one()
        self.student_id = self.connection.execute(text("insert into approved_students (academic_cycle_id,import_id,name,registration_number,university_email,semester,group_code) values (:c,:b,'test',:r,:e,7,'x') returning id"), {'c':self.cycle.id,'b':batch,'r':'R'+suffix,'e':suffix+'@example.com'}).scalar_one()
        self.payload = {'cycle_id':self.cycle.id,'registration_number':'R'+suffix,'university_email':suffix+'@example.com','purpose':'invitation'}
        self.settings_patch = patch('app.individual_verification.settings', SimpleNamespace(smtp_host='test',smtp_from='test@example.com',smtp_username='',smtp_password='',smtp_port=587))
        self.settings_patch.start(); self.addCleanup(self.settings_patch.stop)
    def call(self, path, data, token=None, origin=None):
        headers = {'cookie':f'{SESSION_COOKIE_NAME}={token or self.student_token}'}
        if origin: headers['origin']=origin
        return request('POST','/api/v1/individual-verification/'+path,data,headers=headers)
    def issue(self):
        with patch('app.individual_verification.send_email') as sender:
            self.assertEqual(self.call('challenge',self.payload)[0],200)
            return sender.call_args.args[1]
    def test_authorization_and_unconfigured_and_rollback(self):
        self.prepare()
        self.assertEqual(self.call('challenge',self.payload,token=self.supervisor_token)[0],403)
        self.assertEqual(self.call('challenge',self.payload,origin='http://evil.example')[0],403)
        with patch('app.individual_verification.settings', SimpleNamespace(smtp_host='',smtp_from='',smtp_username='',smtp_password='')):
            self.assertEqual(self.call('challenge',self.payload)[0],503)
        with patch('app.individual_verification.send_email', side_effect=RuntimeError('secret')):
            self.assertEqual(self.call('challenge',self.payload)[0],503)
        self.assertEqual(self.connection.execute(text('select count(*) from identity_challenges where student_id=:s'),{'s':self.student_id}).scalar_one(),0)
    def test_mismatch_expiry_attempt_limit_and_rate(self):
        self.prepare()
        with patch('app.individual_verification.send_email') as sender:
            self.assertEqual(self.call('challenge',{**self.payload,'registration_number':'wrong'})[0],200); sender.assert_not_called()
            self.assertEqual(self.call('challenge',{**self.payload,'university_email':'wrong@example.com'})[0],200); sender.assert_not_called()
        code=self.issue()
        with patch('app.individual_verification.send_email') as sender:
            self.assertEqual(self.call('challenge',self.payload)[0],200); sender.assert_not_called()
        for _ in range(5): self.assertEqual(self.call('verify',{**self.payload,'code':'99999999' if code!='99999999' else '00000000'})[0],400)
        self.assertEqual(self.call('verify',{**self.payload,'code':code})[0],400)
        self.connection.execute(text("update identity_challenges set attempts=0, expires_at=now()-interval '1 second' where student_id=:s"),{'s':self.student_id})
        self.assertEqual(self.call('verify',{**self.payload,'code':code})[0],400)
    def test_creator_proof_requires_matching_active_recorded_creator(self):
        self.prepare()
        self.connection.execute(text("insert into team_members (team_id, academic_cycle_id, full_name, registration_number, university_email, is_creator, is_active) values (:team, :cycle, 'Creator', :reg, :email, true, true)"), {"team": self.team_id, "cycle": self.cycle.id, "reg": self.payload["registration_number"].upper(), "email": self.payload["university_email"]})
        code = self.issue()
        status, _, result = self.call('verify', {**self.payload, 'code': code})
        self.assertEqual(status, 200)
        session = Session(bind=self.connection, join_transaction_mode='create_savepoint')
        token = result['proof']
        self.assertFalse(consume_creator_proof(session, token, team_id=self.team_id, actor_id=self.other_id, purpose='invitation'))
        self.assertFalse(consume_creator_proof(session, token, team_id=self.team_id, actor_id=self.student.id, purpose='join_request'))
        self.assertTrue(consume_creator_proof(session, token, team_id=self.team_id, actor_id=self.student.id, purpose='invitation'))
        session.rollback()
        self.connection.execute(text("update team_members set is_creator=false where team_id=:team"), {"team": self.team_id})
        self.assertFalse(consume_creator_proof(session, token, team_id=self.team_id, actor_id=self.student.id, purpose='invitation'))
        session.close()

    def test_success_proof_scope_rollback_reuse_expiry(self):
        self.prepare(); code=self.issue()
        status,_,result=self.call('verify',{**self.payload,'code':code}); self.assertEqual(status,200)
        self.assertEqual(self.call('verify',{**self.payload,'code':code})[0],400)
        token=result['proof']; session=Session(bind=self.connection,join_transaction_mode='create_savepoint')
        args={'student_id':self.student_id,'cycle_id':self.cycle.id,'actor_id':self.student.id,'purpose':'invitation'}
        self.assertFalse(consume_identity_proof(session,token,**{**args,'purpose':'join_request'}))
        self.assertFalse(consume_identity_proof(session,token,**{**args,'cycle_id':self.cycle.id+1000}))
        self.assertFalse(consume_identity_proof(session,token,**{**args,'student_id':self.student_id+1000}))
        self.assertFalse(consume_identity_proof(session,token,**{**args,'actor_id':self.student.id+1000}))
        self.assertTrue(consume_identity_proof(session,token,**args)); session.rollback()
        self.assertTrue(consume_identity_proof(session,token,**args)); session.commit()
        self.assertFalse(consume_identity_proof(session,token,**args)); session.rollback()
        self.connection.execute(text("update identity_proofs set consumed_at=null, expires_at=now()-interval '1 second' where student_id=:s"),{'s':self.student_id})
        self.assertFalse(consume_identity_proof(session,token,**args)); session.close()


class IdentityProofConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with SessionLocal() as session:
            if session.scalar(text("select current_database()")) != "fyphub_p1":
                raise RuntimeError("Concurrency test requires fyphub_p1.")

    def test_only_one_transaction_consumes_proof(self):
        suffix = uuid4().hex
        token = generate_session_token()
        ids, results, failures, threads = {}, {}, [], []
        first_done, second_ready, release = threading.Event(), threading.Event(), threading.Event()
        try:
            with SessionLocal() as session:
                admin = User(full_name="Race admin", email=f"race-admin-{suffix}@example.test", password_hash="test", role=UserRole.ADMIN)
                actor = User(full_name="Race student", email=f"race-student-{suffix}@example.test", registration_number=f"P{suffix}", password_hash="test", role=UserRole.STUDENT)
                cycle = AcademicCycle(code=f"RACE-{suffix}", display_name="Proof race")
                session.add_all([admin, actor, cycle]); session.flush()
                batch = RosterImport(academic_cycle_id=cycle.id, imported_by_id=admin.id, confirmation_hash=suffix)
                session.add(batch); session.flush()
                student = ApprovedStudent(academic_cycle_id=cycle.id, import_id=batch.id, name="Race", registration_number=f"R{suffix}", university_email=f"race-{suffix}@example.test", semester=7, group_code="TEST")
                session.add(student); session.flush()
                challenge = IdentityChallenge(student_id=student.id, cycle_id=cycle.id, actor_id=actor.id, purpose="invitation", code_hash="test", expires_at=utc_now()+timedelta(minutes=5))
                session.add(challenge); session.flush()
                proof = IdentityProof(challenge_id=challenge.id, student_id=student.id, cycle_id=cycle.id, actor_id=actor.id, purpose="invitation", token_hash=hash_session_token(token), expires_at=utc_now()+timedelta(minutes=5))
                session.add(proof); session.flush()
                ids = {"admin":admin.id,"actor":actor.id,"cycle":cycle.id,"batch":batch.id,"student":student.id,"challenge":challenge.id,"proof":proof.id}
                session.commit()
            args = {"student_id":ids["student"],"cycle_id":ids["cycle"],"actor_id":ids["actor"],"purpose":"invitation"}
            def worker(label):
                try:
                    with SessionLocal() as session:
                        session.execute(text("SET LOCAL statement_timeout = '4s'"))
                        results[label+"_pid"] = session.scalar(text("select pg_backend_pid()"))
                        if label == "second":
                            if not first_done.wait(3): raise AssertionError("first timed out")
                            second_ready.set()
                        results[label] = consume_identity_proof(session, token, **args)
                        if label == "first":
                            first_done.set()
                            if not release.wait(3): raise AssertionError("release timed out")
                        session.commit()
                except Exception as exc:
                    failures.append(exc); first_done.set(); second_ready.set()
            threads = [threading.Thread(target=worker,args=(label,),daemon=True) for label in ("first","second")]
            for thread in threads: thread.start()
            self.assertTrue(first_done.wait(3)); self.assertTrue(second_ready.wait(3))
            self.assertTrue(results.get("first")); self.assertNotEqual(results.get("first_pid"), results.get("second_pid"))
            deadline, blocked = time.monotonic()+2, False
            with SessionLocal() as observer:
                while time.monotonic() < deadline:
                    blocked = observer.scalar(text("select :first = any(pg_blocking_pids(:second))"), {"first":results["first_pid"],"second":results["second_pid"]})
                    if blocked: break
                    time.sleep(0.02)
            self.assertTrue(blocked, "second transaction did not wait on first")
            release.set()
            for thread in threads: thread.join(timeout=4)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(failures, [])
            self.assertEqual((results.get("first"),results.get("second")),(True,False))
            with SessionLocal() as session: self.assertIsNotNone(session.get(IdentityProof,ids["proof"]).consumed_at)
        finally:
            release.set()
            for thread in threads: thread.join(timeout=5)
            if ids and not any(thread.is_alive() for thread in threads):
                with SessionLocal() as session:
                    for table,key in (("identity_proofs","proof"),("identity_challenges","challenge"),("approved_students","student"),("roster_imports","batch"),("academic_cycles","cycle")):
                        session.execute(text(f"delete from {table} where id=:id"),{"id":ids[key]})
                    session.execute(text("delete from users where id in (:admin,:actor)"),ids)
                    session.commit()
