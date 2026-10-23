import unittest
import threading
import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.anonymous_verification import consume_anonymous_proof
from app.auth import utc_now
from app.database import SessionLocal
from app.models import AcademicCycle, ApprovedStudent, RosterImport, User, UserRole, Team, AnonymousVerificationContext, AnonymousVerificationChallenge, AnonymousIdentityProof
from app.security import generate_session_token, hash_session_token
from tests import test_group_channels as fixtures
from tests.test_auth_sessions import request

class AnonymousVerificationTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.GroupChannelTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.GroupChannelTests.tearDownClass.__func__)
    get_test_db = classmethod(fixtures.GroupChannelTests.get_test_db.__func__)
    setUp = fixtures.GroupChannelTests.setUp
    def prepare(self):
        suffix=uuid4().hex
        batch=self.connection.execute(text('insert into roster_imports (academic_cycle_id, imported_by_id, confirmation_hash) values (:cycle,:admin,:hash) returning id'), {'cycle':self.cycle.id,'admin':self.admin.id,'hash':suffix}).scalar_one()
        self.student_id=self.connection.execute(text("insert into approved_students (academic_cycle_id,import_id,name,registration_number,university_email,semester,group_code) values (:c,:b,'Test',:r,:e,7,'X') returning id"), {'c':self.cycle.id,'b':batch,'r':'R'+suffix,'e':suffix+'@example.com'}).scalar_one()
        self.data={'cycle_id':self.cycle.id,'registration_number':'R'+suffix,'university_email':suffix+'@example.com','purpose':'join_request','action':'submit_join_request','target_team_id':self.team_id}
        config=SimpleNamespace(smtp_host='smtp.test',smtp_from='test@example.com',smtp_username='',smtp_password='',smtp_port=587)
        self.config=patch('app.anonymous_verification.settings',config); self.config.start(); self.addCleanup(self.config.stop)
    def call(self,path,data=None,cookie=None,origin=None):
        headers={}
        if cookie: headers['cookie']=cookie
        if origin: headers['origin']=origin
        return request('POST','/api/v1/anonymous-verification/'+path,data,headers=headers)
    def context(self):
        status,headers,_=self.call('context'); self.assertEqual(status,200)
        return headers['set-cookie'].split(';',1)[0]
    def issue(self,cookie):
        with patch('app.anonymous_verification.send_email') as send:
            self.assertEqual(self.call('challenge',self.data,cookie)[0],200)
            return send.call_args.args[1]
    def test_valid_scope_replay_and_rollback(self):
        self.prepare(); cookie=self.context(); code=self.issue(cookie)
        self.assertEqual(self.call('verify',{**self.data,'code':'00000000' if code!='00000000' else '11111111'},cookie)[0],400)
        status,_,result=self.call('verify',{**self.data,'code':code},cookie); self.assertEqual(status,200)
        self.assertEqual(self.call('verify',{**self.data,'code':code},cookie)[0],400)
        token=cookie.split('=',1)[1]; proof=result['proof']; session=Session(bind=self.connection,join_transaction_mode='create_savepoint')
        args={'student_id':self.student_id,'cycle_id':self.cycle.id,'purpose':'join_request','action':'submit_join_request','target_team_id':self.team_id}
        self.assertFalse(consume_anonymous_proof(session,proof,'wrong',**args))
        self.assertFalse(consume_anonymous_proof(session,proof,token,**{**args,'purpose':'invitation'}))
        self.assertFalse(consume_anonymous_proof(session,proof,token,**{**args,'student_id':self.student_id+100}))
        self.assertFalse(consume_anonymous_proof(session,proof,token,**{**args,'cycle_id':self.cycle.id+100}))
        self.assertFalse(consume_anonymous_proof(session,proof,token,**{**args,'target_team_id':self.team_id+100}))
        self.assertFalse(consume_anonymous_proof(session,proof,token,**{**args,'action':'accept_join_request'}))
        self.connection.execute(text('update anonymous_identity_proofs set action=null, target_team_id=null where student_id=:s'), {'s':self.student_id})
        self.assertFalse(consume_anonymous_proof(session,proof,token,**args))
        self.connection.execute(text('update anonymous_identity_proofs set action=:a, target_team_id=:t where student_id=:s'), {'a':'submit_join_request','t':self.team_id,'s':self.student_id})
        self.assertTrue(consume_anonymous_proof(session,proof,token,**args)); session.rollback()
        self.assertTrue(consume_anonymous_proof(session,proof,token,**args)); session.commit()
        self.assertFalse(consume_anonymous_proof(session,proof,token,**args)); session.close()
    def test_mismatch_rate_attempts_and_expiry(self):
        self.prepare(); cookie=self.context()
        with patch('app.anonymous_verification.send_email') as send:
            self.assertEqual(self.call('challenge',{**self.data,'university_email':'wrong@example.com'},cookie)[0],200); send.assert_not_called()
            self.assertEqual(self.call('challenge',{**self.data,'registration_number':'wrong'},cookie)[0],200); send.assert_not_called()
        with patch('app.anonymous_verification.send_email') as send:
            self.assertEqual(self.call('challenge',{**self.data,'target_team_id':self.team_id+99999},cookie)[0],200); send.assert_not_called()
        code=self.issue(cookie)
        self.assertEqual(self.call('verify',{**self.data,'target_team_id':self.team_id+99999,'code':code},cookie)[0],400)
        self.assertEqual(self.call('verify',{**self.data,'action':'accept_join_request','code':code},cookie)[0],422)
        with patch('app.anonymous_verification.send_email') as send:
            self.assertEqual(self.call('challenge',self.data,cookie)[0],200); send.assert_not_called()
        for _ in range(5): self.assertEqual(self.call('verify',{**self.data,'code':'99999999' if code!='99999999' else '00000000'},cookie)[0],400)
        self.assertEqual(self.call('verify',{**self.data,'code':code},cookie)[0],400)
        self.connection.execute(text("update anonymous_verification_challenges set attempts=0, expires_at=now()-interval '1 second' where student_id=:s"),{'s':self.student_id})
        self.assertEqual(self.call('verify',{**self.data,'code':code},cookie)[0],400)
    def test_unavailable_origin_and_delivery_rollback(self):
        self.prepare(); self.assertEqual(self.call('context',origin='http://evil.example')[0],403)
        with patch('app.anonymous_verification.settings',SimpleNamespace(smtp_host='',smtp_from='',smtp_username='',smtp_password='')):
            self.assertEqual(self.call('context')[0],503)
        cookie=self.context()
        with patch('app.anonymous_verification.send_email',side_effect=RuntimeError('secret')):
            status,_,body=self.call('challenge',self.data,cookie); self.assertEqual(status,503); self.assertNotIn('secret',str(body))
        self.assertEqual(self.connection.execute(text('select count(*) from anonymous_verification_challenges where student_id=:s'),{'s':self.student_id}).scalar_one(),0)


class AnonymousProofConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with SessionLocal() as session:
            if session.scalar(text("select current_database()")) != "fyphub_p1":
                raise RuntimeError("Concurrency test requires fyphub_p1.")

    def test_only_one_transaction_consumes_proof(self):
        suffix = uuid4().hex
        token = generate_session_token()
        context_token = generate_session_token()
        ids, results, failures, threads = {}, {}, [], []
        first_done, second_ready, release = threading.Event(), threading.Event(), threading.Event()
        try:
            with SessionLocal() as session:
                admin = User(full_name="Race admin", email=f"race-admin-{suffix}@example.test", password_hash="test", role=UserRole.ADMIN)
                actor = User(full_name="Race student", email=f"race-student-{suffix}@example.test", registration_number=f"P{suffix}", password_hash="test", role=UserRole.STUDENT)
                cycle = AcademicCycle(code=f"RACE-{suffix}", display_name="Proof race")
                session.add_all([admin, actor, cycle]); session.flush()
                team = Team(academic_cycle_id=cycle.id, shared_user_id=actor.id); session.add(team); session.flush()
                batch = RosterImport(academic_cycle_id=cycle.id, imported_by_id=admin.id, confirmation_hash=suffix)
                session.add(batch); session.flush()
                student = ApprovedStudent(academic_cycle_id=cycle.id, import_id=batch.id, name="Race", registration_number=f"R{suffix}", university_email=f"race-{suffix}@example.test", semester=7, group_code="TEST")
                session.add(student); session.flush()
                context = AnonymousVerificationContext(token_hash=hash_session_token(context_token), client_hash=hash_session_token(suffix), expires_at=utc_now()+timedelta(minutes=5))
                session.add(context); session.flush()
                challenge = AnonymousVerificationChallenge(context_id=context.id, student_id=student.id, cycle_id=cycle.id, purpose="join_request", action="submit_join_request", target_team_id=team.id, code_hash="test", expires_at=utc_now()+timedelta(minutes=5))
                session.add(challenge); session.flush()
                proof = AnonymousIdentityProof(context_id=context.id, challenge_id=challenge.id, student_id=student.id, cycle_id=cycle.id, purpose="join_request", action="submit_join_request", target_team_id=team.id, token_hash=hash_session_token(token), expires_at=utc_now()+timedelta(minutes=5))
                session.add(proof); session.flush()
                ids = {"admin":admin.id,"actor":actor.id,"cycle":cycle.id,"batch":batch.id,"student":student.id,"challenge":challenge.id,"proof":proof.id,"context":context.id,"team":team.id}
                session.commit()
            args = {"student_id":ids["student"],"cycle_id":ids["cycle"],"purpose":"join_request","action":"submit_join_request","target_team_id":ids["team"]}
            def worker(label):
                try:
                    with SessionLocal() as session:
                        session.execute(text("SET LOCAL statement_timeout = '4s'"))
                        results[label+"_pid"] = session.scalar(text("select pg_backend_pid()"))
                        if label == "second":
                            if not first_done.wait(3): raise AssertionError("first timed out")
                            second_ready.set()
                        results[label] = consume_anonymous_proof(session, token, context_token, **args)
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
            with SessionLocal() as session: self.assertIsNotNone(session.get(AnonymousIdentityProof,ids["proof"]).consumed_at)
        finally:
            release.set()
            for thread in threads: thread.join(timeout=5)
            if ids and not any(thread.is_alive() for thread in threads):
                with SessionLocal() as session:
                    for table,key in (("anonymous_identity_proofs","proof"),("anonymous_verification_challenges","challenge"),("anonymous_verification_contexts","context"),("approved_students","student"),("roster_imports","batch"),("teams","team"),("academic_cycles","cycle")):
                        session.execute(text(f"delete from {table} where id=:id"),{"id":ids[key]})
                    session.execute(text("delete from users where id in (:admin,:actor)"),ids)
                    session.commit()
