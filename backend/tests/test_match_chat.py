import unittest
from unittest.mock import patch
from sqlalchemy import text
from tests import test_team_matching as fixture
from tests.test_auth_sessions import request
from app.auth import SESSION_COOKIE_NAME

class MatchChatTests(unittest.TestCase):
    setUpClass=classmethod(fixture.TeamMatchingTests.setUpClass.__func__)
    tearDownClass=classmethod(fixture.TeamMatchingTests.tearDownClass.__func__)
    get_test_db=classmethod(fixture.TeamMatchingTests.get_test_db.__func__)
    setUp=fixture.TeamMatchingTests.setUp
    new_team=fixture.TeamMatchingTests.new_team
    pref=fixture.TeamMatchingTests.call
    def call(self,method,path,token,data=None):
        return request(method,'/api/v1/match-chats'+path,data,headers={'cookie':f'{SESSION_COOKIE_NAME}={token}'} if token else {})
    def setup_pair(self):
        other,team=self.new_team()
        for token in (self.student_token,other): self.pref('PUT','preferences',token,{'opted_in':True,'answers':{'skills':'Python'}})
        return other,team
    def test_access_messages_close_and_retention(self):
        other,team=self.setup_pair(); outsider,_=self.new_team()
        self.assertEqual(self.call('GET','',None)[0],401)
        status,_,chat=self.call('POST','',self.student_token,{'team_id':team});self.assertEqual(status,201); cid=chat['chat']['id']
        self.assertEqual(self.call('GET',f'/{cid}/messages',outsider)[0],403)
        status,_,message=self.call('POST',f'/{cid}/messages',other,{'body':'Hello'});self.assertEqual(status,201);self.assertEqual(message['team_id'],team)
        self.assertEqual(self.call('POST',f'/{cid}/close',self.student_token)[0],200)
        self.assertEqual(self.call('POST',f'/{cid}/messages',other,{'body':'x'})[0],403)
        self.assertEqual(self.call('GET',f'/{cid}/messages',other)[0],403)
        self.assertEqual(self.connection.execute(text('select body from match_messages where chat_id=:id'),{'id':cid}).scalar_one(),'Hello')
        self.assertEqual(self.call('POST','',other,{'team_id':self.team_id})[2]['status'],'awaiting_other_team')
        result=self.call('POST','',self.student_token,{'team_id':team})[2]
        self.assertEqual(result['status'],'open'); self.assertNotEqual(result['chat']['id'],cid)
        self.assertEqual(self.call('GET',f'/{cid}/messages',self.student_token)[0],403)
    def test_ineligible_cycle_match_and_optout(self):
        other,team=self.setup_pair(); cross,cross_id=self.new_team(True); self.pref('PUT','preferences',cross,{'opted_in':True,'answers':{'skills':'Python'}})
        self.assertEqual(self.call('POST','',self.student_token,{'team_id':cross_id})[0],403)
        different,different_id=self.new_team(); self.pref('PUT','preferences',different,{'opted_in':True,'answers':{'skills':'Other'}})
        self.assertEqual(self.call('POST','',self.student_token,{'team_id':different_id})[0],403)
        _,_,chat=self.call('POST','',self.student_token,{'team_id':team});cid=chat['chat']['id']
        result = self.pref('PUT','preferences',other,{'opted_in':False,'answers':{'skills':'Python'}}); self.assertEqual(result[0],200, result)
        self.assertEqual(self.call('GET',f'/{cid}/messages',self.student_token)[0],403)
        self.assertIsNotNone(self.connection.execute(text('select closed_at from match_chats where id=:id'),{'id':cid}).scalar_one())
    def test_optout_invalidates_pending_reconsent(self):
        other, team = self.setup_pair()
        _, _, response = self.call('POST', '', self.student_token, {'team_id': team})
        old = response['chat']['id']
        self.call('POST', f'/{old}/close', self.student_token)
        self.assertEqual(self.call('POST', '', self.student_token, {'team_id': team})[2]['status'], 'awaiting_other_team')
        self.pref('PUT', 'preferences', other, {'opted_in': False, 'answers': {'skills': 'Python'}})
        self.pref('PUT', 'preferences', other, {'opted_in': True, 'answers': {'skills': 'Python'}})
        self.assertEqual(self.call('POST', '', other, {'team_id': self.team_id})[2]['status'], 'awaiting_other_team')
        new = self.call('POST', '', self.student_token, {'team_id': team})[2]
        self.assertEqual(new['status'], 'open')
        self.assertNotEqual(new['chat']['id'], old)
        self.assertEqual(self.call('GET', f'/{old}/messages', other)[0], 403)
    def test_failed_write_rolls_back(self):
        other,team=self.setup_pair();_,_,chat=self.call('POST','',self.student_token,{'team_id':team})
        with patch('app.match_chat.MatchMessage',side_effect=RuntimeError('secret')):
            status,_,body=self.call('POST',f"/{chat['chat']['id']}/messages",other,{'body':'x'})
        self.assertEqual(status,500);self.assertNotIn('secret',str(body))
        self.assertEqual(self.connection.execute(text('select count(*) from match_messages where chat_id=:id'),{'id':chat['chat']['id']}).scalar_one(),0)
