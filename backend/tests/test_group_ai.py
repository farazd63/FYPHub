import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import URLError
from sqlalchemy import text
from app.auth import SESSION_COOKIE_NAME
from tests import test_group_channels as fixtures
from tests.test_auth_sessions import request

class GroupAITests(unittest.TestCase):
    setUpClass = classmethod(fixtures.GroupChannelTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.GroupChannelTests.tearDownClass.__func__)
    get_test_db = classmethod(fixtures.GroupChannelTests.get_test_db.__func__)
    setUp = fixtures.GroupChannelTests.setUp
    def call(self, token, team=None, data=None):
        return request('POST' if data is not None else 'GET', f'/api/v1/group-ai/{team or self.team_id}', data, headers={'cookie':f'{SESSION_COOKIE_NAME}={token}'} if token else {})
    def count(self): return self.connection.execute(text("select count(*) from group_messages where team_id=:id and channel='group_ai'"),{'id':self.team_id}).scalar_one()
    def test_authorization_and_team_isolation(self):
        self.assertEqual(self.call(None)[0],401)
        self.assertEqual(self.call(self.supervisor_token)[0],403)
        self.assertEqual(self.call(self.student_token,team=999999999)[0],403)
        self.assertEqual(self.call(self.other_token,data={'body':'x'})[0],403)
    def test_configured_model_and_history(self):
        settings=SimpleNamespace(ollama_url='http://127.0.0.1:11434',ollama_model='fixture-model')
        response=io.BytesIO(json.dumps({'message':{'content':'advisory response'}}).encode())
        with patch('app.group_ai.settings',settings), patch('app.group_ai.build_opener') as opener:
            opener.return_value.open.return_value=response
            status,_,body=self.call(self.student_token,data={'body':'team question'})
            self.assertEqual(status,201); self.assertEqual(body['question']['author_kind'],'TEAM'); self.assertEqual(body['answer']['author_kind'],'AI')
            sent=json.loads(opener.return_value.open.call_args.args[0].data); self.assertEqual(sent['model'],'fixture-model'); self.assertEqual(sent['messages'][-1]['content'],'team question')
        _,_,history=self.call(self.student_token); self.assertEqual([m['author_kind'] for m in history],['TEAM','AI']); self.assertEqual(self.count(),2)
    def test_missing_configuration_timeout_and_runtime_error(self):
        for settings,exception in [(SimpleNamespace(ollama_url='',ollama_model=''),None),(SimpleNamespace(ollama_url='http://127.0.0.1:11434',ollama_model=''),None),(SimpleNamespace(ollama_url='http://127.0.0.1:11434',ollama_model='fixture'),TimeoutError()),(SimpleNamespace(ollama_url='http://127.0.0.1:11434',ollama_model='fixture'),URLError('private failure'))]:
            with self.subTest(exception=exception),patch('app.group_ai.settings',settings),patch('app.group_ai.build_opener') as opener:
                if exception: opener.return_value.open.side_effect=exception
                code,_,body=self.call(self.student_token,data={'body':'question'}); self.assertEqual(code,503); self.assertNotIn('private failure',str(body)); self.assertEqual(self.count(),0)
