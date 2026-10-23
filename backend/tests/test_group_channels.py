import unittest
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.auth import utc_now, SESSION_COOKIE_NAME
from app.models import AuthSession, SupervisorAssignment, Team, User, UserRole
from app.security import generate_session_token, hash_session_token
from tests import test_supervisor_capacity as fixtures
from tests.test_auth_sessions import request

class GroupChannelTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.SupervisorCapacityTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.SupervisorCapacityTests.tearDownClass.__func__)
    get_test_db = classmethod(fixtures.SupervisorCapacityTests.get_test_db.__func__)
    def setUp(self):
        fixtures.SupervisorCapacityTests.setUp(self)
        session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        team = Team(academic_cycle_id=self.cycle.id, shared_user_id=self.student.id); session.add(team); session.flush(); self.team_id = team.id
        assignment = SupervisorAssignment(team_id=team.id, academic_cycle_id=self.cycle.id, supervisor_id=self.supervisor.id, assigned_by_id=self.admin.id); session.add(assignment)
        other = User(full_name="Other supervisor", email=f"other-{uuid4().hex}@example.com", password_hash="test", role=UserRole.SUPERVISOR); session.add(other); session.flush(); self.other_id = other.id
        self.supervisor_token = generate_session_token(); self.other_token = generate_session_token()
        for user, token in ((self.supervisor, self.supervisor_token),(other,self.other_token)):
            session.add(AuthSession(user_id=user.id, token_hash=hash_session_token(token), expires_at=utc_now().replace(year=utc_now().year+1)))
        session.commit(); self.assignment_id = assignment.id; session.close()
    def call(self, method, channel, token, payload=None, team=None, origin=None):
        headers = {"cookie":f"{SESSION_COOKIE_NAME}={token}"} if token else {}
        if origin: headers['origin']=origin
        return request(method, f"/api/v1/group-channels/{team or self.team_id}/{channel}", payload, headers=headers)
    def test_permissions_all_channels(self):
        allowed=['proposal','research','supervisor_discussion','tasks_progress','files_resources']
        for channel in ['general',*allowed,'announcements_deadlines']:
            with self.subTest(channel=channel):
                self.assertEqual(self.call('POST',channel,self.student_token,{'body':'team message'})[0],201)
                self.assertEqual(self.call('GET',channel,self.student_token)[0],200)
                self.assertEqual(self.call('GET',channel,self.other_token)[0],403)
                self.assertEqual(self.call('GET',channel,self.supervisor_token)[0],403 if channel=='general' else 200)
                self.assertEqual(self.call('POST',channel,self.supervisor_token,{'body':'supervisor'})[0],201 if channel in allowed else 403)
        self.assertEqual(self.call('GET','proposal',None)[0],401)
        self.assertEqual(self.call('POST','proposal',self.student_token,{'body':'x'},origin='http://evil.example')[0],403)
        self.assertEqual(self.call('POST','proposal',self.student_token,{'body':' ', 'extra': 1})[0],422)
    def test_history_reassignment_and_safe_rollback(self):
        status,_,message=self.call('POST','proposal',self.student_token,{'body':'shared message'}); self.assertEqual(status,201); self.assertEqual(message['author_kind'],'TEAM'); self.assertEqual(message['author_id'],self.student.id)
        self.connection.execute(text('update supervisor_assignments set ended_at=now(), ended_by_id=:admin where id=:id'),{'admin':self.admin.id,'id':self.assignment_id})
        self.assertEqual(self.call('GET','proposal',self.supervisor_token)[0],403)
        self.connection.execute(text('insert into supervisor_assignments (team_id,academic_cycle_id,supervisor_id,assigned_by_id) values (:team,:cycle,:supervisor,:admin)'),{'team':self.team_id,'cycle':self.cycle.id,'supervisor':self.other_id,'admin':self.admin.id})
        code,_,history=self.call('GET','proposal',self.other_token); self.assertEqual(code,200); self.assertEqual(history[0]['body'],'shared message')
        with patch('app.group_channels.GroupMessage', side_effect=RuntimeError('secret')):
            code,_,body=self.call('POST','proposal',self.student_token,{'body':'fail'})
        self.assertEqual(code,500); self.assertNotIn('secret',str(body))
        self.assertEqual(self.connection.execute(text('select count(*) from group_messages where team_id=:id'),{'id':self.team_id}).scalar_one(),1)
