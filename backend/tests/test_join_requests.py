from unittest.mock import patch
from sqlalchemy import text
from tests.test_anonymous_verification import AnonymousVerificationTests
from tests.test_auth_sessions import request

class JoinSubmissionTests(AnonymousVerificationTests):
    def test_submission_and_audit_rollback(self):
        self.prepare()
        self.connection.execute(text('insert into academic_group_policies (academic_cycle_id,max_group_size) values (:cycle,4)'), {'cycle': self.cycle.id})
        cookie = self.context(); code = self.issue(cookie)
        status, _, result = self.call('verify', {**self.data, 'code': code}, cookie)
        self.assertEqual(status, 200)
        payload = {**self.data, 'proof': result['proof']}
        with patch('app.join_requests.JoinRequestAudit', side_effect=RuntimeError('private')):
            status, _, body = request('POST', '/api/v1/join-requests', payload, headers={'cookie': cookie})
        self.assertEqual(status, 500); self.assertNotIn('private', str(body))
        self.assertEqual(self.connection.execute(text('select count(*) from join_requests where student_id=:id'), {'id': self.student_id}).scalar_one(), 0)
        status, _, body = request('POST', '/api/v1/join-requests', payload, headers={'cookie': cookie})
        self.assertEqual(status, 201)
        self.assertEqual(self.connection.execute(text('select actor_student_id from join_request_audit where request_id=:id'), {'id': body['id']}).scalar_one(), self.student_id)
        self.assertEqual(request('POST', '/api/v1/join-requests', payload, headers={'cookie': cookie})[0], 400)
    def test_creator_targeted_accept_and_replay(self):
        self.prepare()
        self.connection.execute(text('insert into academic_group_policies (academic_cycle_id,max_group_size) values (:cycle,4)'), {'cycle': self.cycle.id})
        cookie = self.context(); code = self.issue(cookie)
        _, _, result = self.call('verify', {**self.data, 'code': code}, cookie)
        status, _, body = request('POST', '/api/v1/join-requests', {**self.data, 'proof': result['proof']}, headers={'cookie': cookie})
        self.assertEqual(status, 201); request_id = body['id']
        creator_reg = 'CREATOR' + str(self.student_id)
        creator_email = f'creator{self.student_id}@example.com'
        self.connection.execute(text("insert into approved_students (academic_cycle_id,import_id,name,registration_number,university_email,semester,group_code) select academic_cycle_id,import_id,'Creator',:reg,:email,7,'X' from approved_students where id=:id"), {'reg':creator_reg,'email':creator_email,'id':self.student_id})
        self.connection.execute(text("insert into team_members (team_id,academic_cycle_id,full_name,registration_number,university_email,is_creator,is_active) values (:team,:cycle,'Creator',:reg,:email,true,true)"), {'team':self.team_id,'cycle':self.cycle.id,'reg':creator_reg,'email':creator_email})
        from app.auth import SESSION_COOKIE_NAME
        from types import SimpleNamespace
        headers={'cookie':f'{SESSION_COOKIE_NAME}={self.student_token}'}
        data={'cycle_id':self.cycle.id,'registration_number':creator_reg,'university_email':creator_email,'purpose':'join_request','action':'accept_join_request'}
        config=SimpleNamespace(smtp_host='smtp.test',smtp_from='test@example.com',smtp_username='',smtp_password='',smtp_port=587)
        with patch('app.join_requests.settings',config), patch('app.join_requests.send_email') as send:
            self.assertEqual(request('POST', f'/api/v1/join-requests/{request_id}/creator/challenge',data,headers=headers)[0],200)
            creator_code=send.call_args.args[1]
        status,_,verified=request('POST',f'/api/v1/join-requests/{request_id}/creator/verify',{**data,'code':creator_code},headers=headers)
        self.assertEqual(status,200)
        payload={**data,'proof':verified['proof']}
        self.assertEqual(request('POST',f'/api/v1/join-requests/{request_id}/decision',{**payload,'action':'reject_join_request'},headers=headers)[0],400)
        self.assertEqual(request('POST',f'/api/v1/join-requests/{request_id}/decision',payload,headers=headers)[0],200)
        self.assertEqual(request('POST',f'/api/v1/join-requests/{request_id}/decision',payload,headers=headers)[0],400)
        self.assertEqual(self.connection.execute(text('select count(*) from team_members where team_id=:t and registration_number=:r'),{'t':self.team_id,'r':self.data['registration_number'].upper()}).scalar_one(),1)

class JoinDecisionTests(AnonymousVerificationTests):
    def setup_decision(self, action='accept_join_request'):
        from app.auth import SESSION_COOKIE_NAME
        from app.security import generate_session_token, hash_session_token
        self.prepare()
        self.connection.execute(text('insert into academic_group_policies (academic_cycle_id,max_group_size) values (:c,4)'), {'c':self.cycle.id})
        reg,email=f'CREATOR{self.student_id}',f'creator{self.student_id}@example.com'
        creator=self.connection.execute(text("insert into approved_students (academic_cycle_id,import_id,name,registration_number,university_email,semester,group_code) select academic_cycle_id,import_id,'Creator',:r,:e,7,'X' from approved_students where id=:id returning id"),{'r':reg,'e':email,'id':self.student_id}).scalar_one()
        self.connection.execute(text("insert into team_members (team_id,academic_cycle_id,full_name,registration_number,university_email,is_creator,is_active) values (:t,:c,'Creator',:r,:e,true,true)"),{'t':self.team_id,'c':self.cycle.id,'r':reg,'e':email})
        self.rid=self.connection.execute(text("insert into join_requests (team_id,cycle_id,student_id,status) values (:t,:c,:s,'pending') returning id"),{'t':self.team_id,'c':self.cycle.id,'s':self.student_id}).scalar_one()
        params={'s':creator,'c':self.cycle.id,'a':self.student.id,'act':action,'r':self.rid,'t':self.team_id}
        ch=self.connection.execute(text("insert into identity_challenges (student_id,cycle_id,actor_id,purpose,action,target_request_id,target_team_id,code_hash,expires_at) values (:s,:c,:a,'join_request',:act,:r,:t,'hash',now()+interval '5 minutes') returning id"),params).scalar_one()
        token=generate_session_token();params.update(ch=ch,hash=hash_session_token(token))
        self.pid=self.connection.execute(text("insert into identity_proofs (challenge_id,student_id,cycle_id,actor_id,purpose,action,target_request_id,target_team_id,token_hash,expires_at) values (:ch,:s,:c,:a,'join_request',:act,:r,:t,:hash,now()+interval '5 minutes') returning id"),params).scalar_one()
        self.payload={'cycle_id':self.cycle.id,'registration_number':reg,'university_email':email,'purpose':'join_request','action':action,'proof':token}
        self.headers={'cookie':f'{SESSION_COOKIE_NAME}={self.student_token}'}
    def decide(self,data=None,headers=None):
        return request('POST',f'/api/v1/join-requests/{self.rid}/decision',data or self.payload,headers=headers or self.headers)
    def snapshot(self):
        return (self.connection.execute(text('select status from join_requests where id=:id'),{'id':self.rid}).scalar_one(),self.connection.execute(text('select count(*) from team_members where academic_cycle_id=:c and lower(registration_number)=lower(:r) and is_active'),{'c':self.cycle.id,'r':self.data['registration_number']}).scalar_one(),self.connection.execute(text('select consumed_at from identity_proofs where id=:id'),{'id':self.pid}).scalar_one(),self.connection.execute(text('select count(*) from join_request_audit where request_id=:id'),{'id':self.rid}).scalar_one())
    def test_noncreator_cannot_accept_or_reject(self):
        self.setup_decision()
        from app.auth import SESSION_COOKIE_NAME
        for action in ('accept_join_request','reject_join_request'):
            self.assertEqual(self.decide({**self.payload,'registration_number':self.data['registration_number'],'university_email':self.data['university_email'],'action':action})[0],400)
            self.assertEqual(self.decide({**self.payload,'action':action},{'cookie':f'{SESSION_COOKIE_NAME}={self.other_token}'})[0],403)
        self.assertEqual(self.snapshot(),('pending',0,None,0))
    def test_rejection_has_no_membership(self):
        self.setup_decision('reject_join_request');self.assertEqual(self.decide()[0],200)
        status,count,consumed,audit=self.snapshot();self.assertEqual((status,count,audit),('rejected',0,1));self.assertIsNotNone(consumed);self.assertEqual(self.decide()[0],400)
    def test_capacity_and_duplicate_conflicts(self):
        self.setup_decision()
        self.connection.execute(text('update academic_group_policies set max_group_size=1 where academic_cycle_id=:c'),{'c':self.cycle.id})
        self.assertEqual(self.decide()[0],400);self.assertEqual(self.snapshot(),('pending',0,None,0))
        self.connection.execute(text('update academic_group_policies set max_group_size=4 where academic_cycle_id=:c'),{'c':self.cycle.id})
        self.connection.execute(text("insert into team_members (team_id,academic_cycle_id,full_name,registration_number,university_email,is_creator,is_active) values (:t,:c,'Existing',:r,:e,false,true)"),{'t':self.team_id,'c':self.cycle.id,'r':self.data['registration_number'].upper(),'e':self.data['university_email']})
        self.assertEqual(self.decide()[0],400);self.assertEqual(self.snapshot(),('pending',1,None,0))
    def test_decision_audit_failure_rolls_back(self):
        self.setup_decision()
        with patch('app.join_requests.JoinRequestAudit',side_effect=RuntimeError('sensitive')): status,_,body=self.decide()
        self.assertEqual(status,500);self.assertNotIn('sensitive',str(body));self.assertEqual(self.snapshot(),('pending',0,None,0));self.assertEqual(self.decide()[0],200)

class JoinAcceptanceConcurrencyTests(__import__('unittest').TestCase):
    def test_concurrent_acceptance_commits_once(self):
        import threading, time
        from datetime import timedelta
        from uuid import uuid4
        from fastapi import HTTPException, Request
        from app.auth import utc_now
        from app.database import SessionLocal
        from app.join_requests import DecisionProof, decide
        from app.models import AcademicCycle, AcademicGroupPolicy, ApprovedStudent, IdentityChallenge, IdentityProof, JoinRequest, RosterImport, Team, TeamMember, User, UserRole
        from app.security import generate_session_token, hash_session_token
        suffix=uuid4().hex; ids={}; tokens=[generate_session_token(),generate_session_token()]
        first_locked=threading.Event(); second_started=threading.Event(); release=threading.Event(); results={}; failures=[]; threads=[]
        try:
            with SessionLocal() as s:
                self.assertEqual(s.scalar(text('select current_database()')),'fyphub_p1')
                admin=User(full_name='Race admin',email=f'admin-{suffix}@example.com',password_hash='x',role=UserRole.ADMIN)
                actor=User(full_name='Race team',email=f'team-{suffix}@example.com',registration_number=f'USER{suffix}',password_hash='x',role=UserRole.STUDENT)
                cycle=AcademicCycle(code=f'JOIN-{suffix}',display_name='Join race');s.add_all([admin,actor,cycle]);s.flush()
                team=Team(academic_cycle_id=cycle.id,shared_user_id=actor.id);batch=RosterImport(academic_cycle_id=cycle.id,imported_by_id=admin.id,confirmation_hash=suffix)
                s.add_all([team,batch,AcademicGroupPolicy(academic_cycle_id=cycle.id,max_group_size=4)]);s.flush()
                creator=ApprovedStudent(academic_cycle_id=cycle.id,import_id=batch.id,name='Creator',registration_number=f'C{suffix}',university_email=f'creator-{suffix}@example.com',semester=7,group_code='X')
                applicant=ApprovedStudent(academic_cycle_id=cycle.id,import_id=batch.id,name='Applicant',registration_number=f'A{suffix}',university_email=f'applicant-{suffix}@example.com',semester=8,group_code='X')
                s.add_all([creator,applicant]);s.flush()
                s.add(TeamMember(team_id=team.id,academic_cycle_id=cycle.id,full_name=creator.name,registration_number=creator.registration_number.upper(),university_email=creator.university_email,is_creator=True,is_active=True))
                row=JoinRequest(team_id=team.id,cycle_id=cycle.id,student_id=applicant.id);s.add(row);s.flush()
                for token in tokens:
                    challenge=IdentityChallenge(student_id=creator.id,cycle_id=cycle.id,actor_id=actor.id,purpose='join_request',action='accept_join_request',target_request_id=row.id,target_team_id=team.id,code_hash='test',expires_at=utc_now()+timedelta(minutes=5));s.add(challenge);s.flush()
                    s.add(IdentityProof(challenge_id=challenge.id,student_id=creator.id,cycle_id=cycle.id,actor_id=actor.id,purpose='join_request',action='accept_join_request',target_request_id=row.id,target_team_id=team.id,token_hash=hash_session_token(token),expires_at=utc_now()+timedelta(minutes=5)))
                ids={'cycle':cycle.id,'actor':actor.id,'admin':admin.id,'team':team.id,'batch':batch.id,'creator':creator.id,'applicant':applicant.id,'request':row.id,'reg':creator.registration_number,'email':creator.university_email,'appreg':applicant.registration_number}
                s.commit()
            def worker(label,token):
                try:
                    with SessionLocal() as session:
                        session.execute(text("SET LOCAL statement_timeout = '5s'"));results[label+'_pid']=session.scalar(text('select pg_backend_pid()'))
                        actor=session.get(User,ids['actor'])
                        if label=='first':
                            original=session.commit
                            def hold_commit():
                                session.flush();first_locked.set()
                                if not release.wait(4): raise AssertionError('release timeout')
                                original()
                            session.commit=hold_commit
                        else:
                            if not first_locked.wait(4): raise AssertionError('first timeout')
                            second_started.set()
                        data=DecisionProof(cycle_id=ids['cycle'],registration_number=ids['reg'],university_email=ids['email'],purpose='join_request',action='accept_join_request',proof=token)
                        req=Request({'type':'http','method':'POST','headers':[],'path':'/','query_string':b''})
                        try: results[label]=decide(ids['request'],data,req,actor,session)['status']
                        except HTTPException as exc: results[label]=exc.status_code
                except Exception as exc:
                    failures.append(repr(exc));first_locked.set();second_started.set()
            threads=[threading.Thread(target=worker,args=(name,token),daemon=True) for name,token in zip(('first','second'),tokens)]
            for thread in threads: thread.start()
            self.assertTrue(first_locked.wait(4));self.assertTrue(second_started.wait(4));self.assertEqual(failures,[])
            self.assertNotEqual(results.get('first_pid'),results.get('second_pid'))
            blocked=False;deadline=time.monotonic()+3
            with SessionLocal() as observer:
                while time.monotonic()<deadline:
                    blocked=observer.scalar(text('select :first = any(pg_blocking_pids(:second))'),{'first':results['first_pid'],'second':results['second_pid']})
                    if blocked: break
                    time.sleep(.02)
            self.assertTrue(blocked,'second transaction did not wait for first')
            release.set()
            for thread in threads: thread.join(6)
            self.assertFalse(any(t.is_alive() for t in threads));self.assertEqual(failures,[])
            self.assertEqual((results.get('first'),results.get('second')),('accepted',400))
            with SessionLocal() as s:
                self.assertEqual(s.scalar(text('select status from join_requests where id=:id'),{'id':ids['request']}),'accepted')
                self.assertEqual(s.scalar(text('select count(*) from team_members where team_id=:team and registration_number=upper(:reg)'),{'team':ids['team'],'reg':ids['appreg']}),1)
                self.assertEqual(s.scalar(text('select count(*) from join_request_audit where request_id=:id and action=\'accepted\''),{'id':ids['request']}),1)
                self.assertEqual(s.scalar(text('select count(*) from identity_proofs where target_request_id=:id and consumed_at is not null'),{'id':ids['request']}),1)
        finally:
            release.set()
            for thread in threads: thread.join(6)
            if ids and not any(t.is_alive() for t in threads):
                with SessionLocal() as s:
                    # Local to this cleanup transaction; only this test's rows are removed.
                    s.execute(text('SET LOCAL session_replication_role = replica'))
                    for sql in ('delete from join_request_audit where request_id=:request','delete from identity_proofs where target_request_id=:request','delete from identity_challenges where target_request_id=:request','delete from join_requests where id=:request','delete from team_members where team_id=:team','delete from approved_students where id in (:creator,:applicant)','delete from roster_imports where id=:batch','delete from teams where id=:team','delete from academic_group_policies where academic_cycle_id=:cycle','delete from academic_cycles where id=:cycle','delete from users where id in (:actor,:admin)'):
                        s.execute(text(sql),ids)
                    s.commit()
