"""Rollback-isolated roster import tests."""
import asyncio
import io
import json
import unittest
import threading
from uuid import uuid4
from unittest.mock import patch
from urllib.parse import urlencode
from fastapi import HTTPException
from openpyxl import Workbook
from sqlalchemy import text
from app import student_roster as roster
from app.auth import SESSION_COOKIE_NAME
from app.main import app
from tests import test_admin_users as fixtures

HEADERS = ["name", "registration_number", "university_email", "semester", "academic_cycle", "group_code", "project_topic"]

def workbook(rows, headers=HEADERS):
    book = Workbook(); sheet = book.active; sheet.append(headers)
    for row in rows: sheet.append(row)
    output = io.BytesIO(); book.save(output); book.close(); return output.getvalue()

def request(method, path, data=b"", token=None, origin=None, preview=None):
    async def invoke():
        output = []; done = False
        async def receive():
            nonlocal done
            if done: return {"type": "http.disconnect"}
            done = True; return {"type": "http.request", "body": data, "more_body": False}
        async def send(message): output.append(message)
        headers = [(b"content-type", b"application/octet-stream"), (b"x-file-name", b"roster.xlsx")]
        if token: headers.append((b"cookie", f"{SESSION_COOKIE_NAME}={token}".encode()))
        if origin: headers.append((b"origin", origin.encode()))
        if preview: headers.append((b"x-preview-token", preview.encode()))
        await app({"type":"http", "asgi":{"version":"3.0"}, "http_version":"1.1", "method":method, "scheme":"http", "path":path.split('?')[0], "raw_path":path.split('?')[0].encode(), "query_string":path.partition('?')[2].encode(), "headers":headers, "client":("127.0.0.1",0), "server":("testserver",80)}, receive, send)
        return output
    messages = asyncio.run(invoke()); status = next(m for m in messages if m['type']=='http.response.start')['status']; body = b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body'); return status, json.loads(body) if body else None

class StudentRosterTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.AdminUserTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.AdminUserTests.tearDownClass.__func__)
    get_test_db = classmethod(fixtures.AdminUserTests.get_test_db.__func__)
    setUp = fixtures.AdminUserTests.setUp

    def make_cycle(self):
        code = f"ROSTER-{self.admin_id}"
        cycle = self.connection.execute(text("insert into academic_cycles (code, display_name, registration_open) values (:code, :name, false) returning id"), {"code":code,"name":"Isolated roster"}).scalar_one()
        return cycle, code
    def row(self, code, registration="001a", email="student@example.com", semester=7): return ["Test Student", registration, email, semester, code, "G1", None]
    def endpoint(self, suffix, cycle): return f"/api/v1/admin/student-roster/{suffix}?" + urlencode({"academic_cycle_id":cycle})
    def test_authorization_origin(self):
        cycle, code = self.make_cycle(); data = workbook([self.row(code)])
        self.assertEqual(request('POST', self.endpoint('preview',cycle), data)[0],401)
        self.assertEqual(request('POST', self.endpoint('preview',cycle), data, self.student_token)[0],403)
        self.assertEqual(request('POST', self.endpoint('preview',cycle), data, self.token, 'http://evil.example')[0],403)
        self.assertEqual(request('GET', f'/api/v1/admin/student-roster?academic_cycle_id={cycle}', token=self.student_token)[0],403)
    def test_validation(self):
        cycle, code = self.make_cycle()
        self.assertEqual(request('POST', self.endpoint('preview',cycle), b'bad', self.token)[0],422)
        self.assertEqual(request('POST', self.endpoint('preview',cycle), workbook([self.row(code)], HEADERS[:-2]), self.token)[0],422)
        cases = [[self.row(code,registration=123)], [self.row(code,semester=6)], [self.row('WRONG')], [self.row(code), self.row(code,registration='001A',email='other@example.com')], [self.row(code), self.row(code,registration='other',email='STUDENT@example.com')], [["=1+1", "a", "b@example.com", 7, code, "G", None]]]
        for rows in cases:
            with self.subTest(rows=rows):
                status, body=request('POST',self.endpoint('preview',cycle),workbook(rows),self.token); self.assertEqual(status,200); self.assertGreater(body['invalid_count'],0); self.assertIsNone(body['confirmation_token'])
    def test_confirmation_binding_expiry_replay_and_conflict(self):
        cycle, code=self.make_cycle(); other, other_code=self.make_cycle_other(); data=workbook([self.row(code)])
        status, preview=request('POST',self.endpoint('preview',cycle),data,self.token); self.assertEqual(status,200); self.assertEqual(preview['rows'][0]['registration_number'],'001a'); token=preview['confirmation_token']
        self.assertEqual(request('POST',self.endpoint('confirm',cycle),data+b'x',self.token,preview=token)[0],409)
        self.assertEqual(request('POST',self.endpoint('confirm',other),data,self.token,preview=token)[0],409)
        with self.assertRaises(HTTPException): roster.verify(token, self.student_id, cycle, data)
        with patch.object(roster.time,'time',return_value=int(roster.time.time())+roster.TTL+1): self.assertEqual(request('POST',self.endpoint('confirm',cycle),data,self.token,preview=token)[0],409)
        status, result=request('POST',self.endpoint('confirm',cycle),data,self.token,preview=token); self.assertEqual((status,result['record_count']),(200,1))
        self.assertEqual(request('POST',self.endpoint('confirm',cycle),data,self.token,preview=token)[0],409)
        status, listing=request('GET',f'/api/v1/admin/student-roster?academic_cycle_id={cycle}',token=self.token); self.assertEqual(listing['items'][0]['registration_number'],'001a')
        _, conflict=request('POST',self.endpoint('preview',cycle),workbook([self.row(code,registration='001A',email='other@example.com')]),self.token); self.assertEqual(conflict['invalid_count'],1)
    def make_cycle_other(self):
        code=f"OTHER-{self.admin_id}"; cycle=self.connection.execute(text("insert into academic_cycles(code,display_name,registration_open) values (:code,'Other',false) returning id"),{'code':code}).scalar_one(); return cycle,code
    def test_audit_failure_rolls_back(self):
        cycle,code=self.make_cycle(); data=workbook([self.row(code)]); _,preview=request('POST',self.endpoint('preview',cycle),data,self.token)
        with patch.object(roster, 'AdminAuditEvent', side_effect=RuntimeError('failure')): self.assertEqual(request('POST',self.endpoint('confirm',cycle),data,self.token,preview=preview['confirmation_token'])[0],500)
        self.assertEqual(self.connection.execute(text('select count(*) from approved_students where academic_cycle_id=:id'),{'id':cycle}).scalar_one(),0)
        self.assertEqual(self.connection.execute(text('select count(*) from roster_imports where academic_cycle_id=:id'),{'id':cycle}).scalar_one(),0)
    def test_concurrent_imports_serialize_on_cycle(self):
        from app.database import engine
        from app.models import AcademicCycle, User, UserRole
        from sqlalchemy.orm import Session
        suffix = uuid4().hex[:10]; setup = Session(engine, expire_on_commit=False)
        actor = User(full_name="Roster concurrency", email=f"roster-{suffix}@example.com", password_hash="test", role=UserRole.ADMIN)
        cycle = AcademicCycle(code=f"ROSTER-{suffix}", display_name="Roster concurrency")
        setup.add_all([actor, cycle]); setup.commit(); actor_id, cycle_id, code = actor.id, cycle.id, cycle.code; setup.close()
        data = workbook([self.row(code)]); token1 = roster.sign(actor_id, cycle_id, data); token2 = roster.sign(actor_id, cycle_id, data)
        first_done, release, second_done = threading.Event(), threading.Event(), threading.Event()
        results, failures = [], []
        class FakeRequest:
            def __init__(self, token): self.headers = {"x-file-name": "roster.xlsx", "x-preview-token": token}
            async def stream(self): yield data
        def worker(token, first):
            connection = engine.connect(); transaction = connection.begin()
            session = Session(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
            try:
                user = session.get(User, actor_id)
                result = asyncio.run(roster.confirm(FakeRequest(token), cycle_id, user, session))
                results.append(result["record_count"])
                if first: first_done.set(); release.wait(timeout=5)
            except Exception as error: failures.append(error); first_done.set()
            finally:
                session.close(); transaction.rollback(); connection.close()
                if not first: second_done.set()
        first = threading.Thread(target=worker, args=(token1, True)); second = threading.Thread(target=worker, args=(token2, False))
        try:
            first.start(); self.assertTrue(first_done.wait(timeout=5)); second.start()
            self.assertFalse(second_done.wait(timeout=0.3), "Second importer must wait for the cycle lock")
            release.set(); first.join(timeout=5); second.join(timeout=5)
            self.assertFalse(first.is_alive() or second.is_alive()); self.assertEqual(failures, []); self.assertEqual(results, [1, 1])
        finally:
            release.set(); first.join(timeout=5)
            if second.ident: second.join(timeout=5)
            cleanup = Session(engine); cleanup.execute(text("delete from academic_cycles where id=:id"), {"id":cycle_id}); cleanup.execute(text("delete from users where id=:id"), {"id":actor_id}); cleanup.commit(); cleanup.close()
    def test_import_serializes_with_team_registration(self):
        from app.database import engine
        from app.main import register_team
        from app.models import AcademicCycle, AcademicGroupPolicy, User, UserRole
        from app.schemas.team_registration import TeamRegistrationRequest
        from sqlalchemy.orm import Session
        suffix = uuid4().hex[:10]
        setup = Session(engine, expire_on_commit=False)
        self.assertEqual(setup.execute(text("SELECT current_database()")).scalar_one(), "fyphub_p1")
        actor = User(full_name="Roster race", email=f"roster-race-{suffix}@example.com", password_hash="test", role=UserRole.ADMIN)
        cycle = AcademicCycle(code=f"RACE-{suffix}", display_name="Roster race", registration_open=True)
        setup.add_all([actor, cycle]); setup.flush()
        setup.add(AcademicGroupPolicy(academic_cycle_id=cycle.id, max_group_size=2))
        setup.commit(); actor_id, cycle_id, code = actor.id, cycle.id, cycle.code; setup.close()
        email = f"student-{suffix}@example.com"
        data = workbook([self.row(code, registration="001A", email=email)])
        token = roster.sign(actor_id, cycle_id, data)
        payload = TeamRegistrationRequest.model_validate({"academic_cycle_id": cycle_id, "shared_login_email": f"team-{suffix}@example.com", "password": "ValidPassword1!", "creator": {"full_name": "Test", "registration_number": "001A", "university_email": email}, "members": []})
        entered, release, registration_done = threading.Event(), threading.Event(), threading.Event()
        failures, result = [], []
        class FakeRequest:
            headers = {"x-file-name": "roster.xlsx", "x-preview-token": token}
            async def stream(self): yield data
        def importer():
            connection = engine.connect(); transaction = connection.begin()
            session = Session(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
            try:
                asyncio.run(roster.confirm(FakeRequest(), cycle_id, session.get(User, actor_id), session))
                entered.set(); release.wait(timeout=5)
            except Exception as error: failures.append(error); entered.set()
            finally: session.close(); transaction.rollback(); connection.close()
        def registration():
            session = Session(engine)
            try: register_team(payload, session); result.append("unexpected success")
            except HTTPException as error: result.append((error.status_code, error.detail["code"]))
            except Exception as error: failures.append(error)
            finally: session.close(); registration_done.set()
        first = threading.Thread(target=importer); second = threading.Thread(target=registration)
        try:
            first.start(); self.assertTrue(entered.wait(timeout=5)); self.assertEqual(failures, [])
            second.start(); self.assertFalse(registration_done.wait(timeout=0.3), "Registration must wait for the import cycle lock")
            release.set(); first.join(timeout=5); second.join(timeout=5)
            self.assertFalse(first.is_alive() or second.is_alive()); self.assertEqual(failures, [])
            self.assertEqual(result, [(422, "student_not_eligible")])
            with Session(engine) as check:
                self.assertEqual(check.execute(text("SELECT count(*) FROM teams WHERE academic_cycle_id=:id"), {"id": cycle_id}).scalar_one(), 0)
        finally:
            release.set(); first.join(timeout=5)
            if second.ident: second.join(timeout=5)
            cleanup = Session(engine)
            cleanup.execute(text("DELETE FROM academic_group_policies WHERE academic_cycle_id=:id"), {"id": cycle_id})
            cleanup.execute(text("DELETE FROM academic_cycles WHERE id=:id"), {"id": cycle_id})
            cleanup.execute(text("DELETE FROM users WHERE id=:id"), {"id": actor_id})
            cleanup.commit(); cleanup.close()
