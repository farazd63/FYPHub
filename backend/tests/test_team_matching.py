import unittest
from uuid import uuid4
from sqlalchemy.orm import Session
from app.auth import SESSION_COOKIE_NAME, utc_now
from app.models import AuthSession, AcademicCycle, Team, User, UserRole
from app.security import generate_session_token, hash_session_token
from tests import test_group_channels as fixture
from tests.test_auth_sessions import request

class TeamMatchingTests(unittest.TestCase):
    setUpClass = classmethod(fixture.GroupChannelTests.setUpClass.__func__)
    tearDownClass = classmethod(fixture.GroupChannelTests.tearDownClass.__func__)
    get_test_db = classmethod(fixture.GroupChannelTests.get_test_db.__func__)
    setUp = fixture.GroupChannelTests.setUp
    def new_team(self, other_cycle=False):
        suffix=uuid4().hex; session=Session(bind=self.connection,expire_on_commit=False,join_transaction_mode='create_savepoint')
        cycle=self.cycle.id
        if other_cycle:
            c=AcademicCycle(code=f'MATCH-{suffix[:8]}',display_name='Match'); session.add(c); session.flush(); cycle=c.id
        user=User(full_name='Team',email=f'match-{suffix}@example.com',registration_number=f'M{suffix[:12]}'.upper(),password_hash='x',role=UserRole.STUDENT); session.add(user); session.flush()
        team=Team(academic_cycle_id=cycle,shared_user_id=user.id); session.add(team); session.flush(); token=generate_session_token(); session.add(AuthSession(user_id=user.id,token_hash=hash_session_token(token),expires_at=utc_now().replace(year=utc_now().year+1))); session.commit(); team_id=team.id; session.close(); return token,team_id
    def call(self, method, path, token, data=None): return request(method,'/api/v1/team-matching/'+path,data,headers={'cookie':f'{SESSION_COOKIE_NAME}={token}'})
    def test_opt_in_same_cycle_comparison_and_withdraw(self):
        other, other_id=self.new_team(); cross, _=self.new_team(True); payload={'opted_in':True,'answers':{'skills':'Python','domain':'Web','commitment':'High'}}
        self.assertEqual(self.call('PUT','preferences',self.student_token,payload)[0],200)
        self.assertEqual(self.call('PUT','preferences',other,{'opted_in':True,'answers':{'skills':' python ','domain':'Mobile'}})[0],200)
        self.call('PUT','preferences',cross,payload)
        _,_,body=self.call('GET','suggestions',self.student_token); self.assertEqual(len(body),1); self.assertEqual(body[0]['team_id'],other_id); self.assertEqual(body[0]['categories'],{'skills':True,'domain':False}); self.assertEqual((body[0]['matched'],body[0]['answered'],body[0]['fraction']),(1,2,0.5))
        self.call('PUT','preferences',other,{'opted_in':False,'answers':{'skills':'python'}})
        self.assertEqual(self.call('GET','suggestions',self.student_token)[2],[])
    def test_authorization_validation_and_unanswered(self):
        self.assertEqual(self.call('GET','preferences',self.supervisor_token)[0],403)
        self.assertEqual(self.call('PUT','preferences',self.student_token,{'opted_in':True,'answers':{'performance':'x'}})[0],422)
        other,_=self.new_team(); self.call('PUT','preferences',self.student_token,{'opted_in':True,'answers':{}}); self.call('PUT','preferences',other,{'opted_in':True,'answers':{}})
        self.assertEqual(self.call('GET','suggestions',self.student_token)[2],[])
