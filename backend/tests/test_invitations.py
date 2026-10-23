from types import SimpleNamespace
from unittest.mock import patch
from sqlalchemy import text
from app.auth import SESSION_COOKIE_NAME
from tests.test_anonymous_verification import AnonymousVerificationTests
from tests.test_auth_sessions import request

class InvitationTests(AnonymousVerificationTests):
    def setup_invite(self):
        self.prepare();self.connection.execute(text('insert into academic_group_policies (academic_cycle_id,max_group_size) values (:c,4)'),{'c':self.cycle.id})
        reg=f'CREATOR{self.student_id}';email=f'creator{self.student_id}@example.com'
        self.creator_id=self.connection.execute(text("insert into approved_students (academic_cycle_id,import_id,name,registration_number,university_email,semester,group_code) select academic_cycle_id,import_id,'Creator',:r,:e,7,'X' from approved_students where id=:id returning id"),{'r':reg,'e':email,'id':self.student_id}).scalar_one()
        self.connection.execute(text("insert into team_members (team_id,academic_cycle_id,full_name,registration_number,university_email,is_creator,is_active) values (:t,:c,'Creator',:r,:e,true,true)"),{'t':self.team_id,'c':self.cycle.id,'r':reg,'e':email})
        self.creator={'cycle_id':self.cycle.id,'team_id':self.team_id,'registration_number':reg,'university_email':email,'recipient_registration':self.data['registration_number'],'recipient_email':self.data['university_email'],'action':'send_invitation'}
        self.headers={'cookie':f'{SESSION_COOKIE_NAME}={self.student_token}'}
        cfg=SimpleNamespace(smtp_host='smtp.test',smtp_from='test@example.com',smtp_username='',smtp_password='',smtp_port=587)
        p=patch('app.invitations.settings',cfg);p.start();self.addCleanup(p.stop)
    def call_inv(self,path,data,headers=None): return request('POST','/api/v1/invitations'+path,data,headers=headers or self.headers)
    def creator_proof(self):
        with patch('app.invitations.send_email') as mail:
            self.assertEqual(self.call_inv('/creator/challenge',self.creator)[0],200);code=mail.call_args.args[1]
        self.assertEqual(self.call_inv('/creator/verify',{**self.creator,'code':code,'team_id':self.team_id+100})[0],400)
        status,_,body=self.call_inv('/creator/verify',{**self.creator,'code':code});self.assertEqual(status,200);return body['proof']
    def send_invite(self):
        proof=self.creator_proof()
        self.assertEqual(self.call_inv('',{**self.creator,'proof':proof,'recipient_email':'wrong@example.com'})[0],400)
        with patch('app.invitations.send_invitation_email') as mail:
            status,_,body=self.call_inv('',{**self.creator,'proof':proof});self.assertEqual(status,201);mail.assert_called_once()
        self.assertEqual(self.call_inv('',{**self.creator,'proof':proof})[0],400)
        return body['id']
    def invitee_proof(self,invitation,action):
        cookie=self.context();data={'cycle_id':self.cycle.id,'invitation_id':invitation,'registration_number':self.data['registration_number'],'university_email':self.data['university_email'],'action':action}
        with patch('app.invitations.send_email') as mail:
            self.assertEqual(self.call_inv('/invitee/challenge',data,{'cookie':cookie})[0],200);code=mail.call_args.args[1]
        self.assertEqual(self.call_inv('/invitee/verify',{**data,'code':code,'action':'reject_invitation' if action=='accept_invitation' else 'accept_invitation'},{'cookie':cookie})[0],400)
        status,_,body=self.call_inv('/invitee/verify',{**data,'code':code},{'cookie':cookie});self.assertEqual(status,200)
        return cookie,{**data,'proof':body['proof']}
    def test_accept_and_replay(self):
        self.setup_invite();invitation=self.send_invite();cookie,payload=self.invitee_proof(invitation,'accept_invitation')
        self.assertEqual(self.call_inv('/invitee/decision',{**payload,'invitation_id':invitation+1},{'cookie':cookie})[0],400)
        self.assertEqual(self.call_inv('/invitee/decision',{**payload,'action':'reject_invitation'},{'cookie':cookie})[0],400)
        self.assertEqual(self.call_inv('/invitee/decision',payload,{'cookie':cookie})[0],200)
        self.assertEqual(self.call_inv('/invitee/decision',payload,{'cookie':cookie})[0],400)
        self.assertEqual(self.connection.execute(text('select count(*) from team_members where team_id=:t and lower(registration_number)=lower(:r)'),{'t':self.team_id,'r':self.data['registration_number']}).scalar_one(),1)
        self.assertEqual(self.connection.execute(text("select count(*) from team_invitation_audit where invitation_id=:i and action='accepted' and actor_student_id=:s"),{'i':invitation,'s':self.student_id}).scalar_one(),1)
    def test_reject(self):
        self.setup_invite();invitation=self.send_invite();cookie,payload=self.invitee_proof(invitation,'reject_invitation')
        self.assertEqual(self.call_inv('/invitee/decision',payload,{'cookie':cookie})[0],200)
        self.assertEqual(self.connection.execute(text('select status from team_invitations where id=:i'),{'i':invitation}).scalar_one(),'rejected')
        self.assertEqual(self.connection.execute(text('select count(*) from team_members where team_id=:t and lower(registration_number)=lower(:r)'),{'t':self.team_id,'r':self.data['registration_number']}).scalar_one(),0)
    def test_creator_only_and_smtp_failure_rollback(self):
        self.setup_invite()
        with patch('app.invitations.send_email') as mail:
            status,_,_=self.call_inv('/creator/challenge',{**self.creator,'registration_number':self.data['registration_number'],'university_email':self.data['university_email']});self.assertEqual(status,200);mail.assert_not_called()
        proof=self.creator_proof()
        with patch('app.invitations.send_invitation_email',side_effect=RuntimeError('private')):
            status,_,body=self.call_inv('',{**self.creator,'proof':proof});self.assertEqual(status,201);self.assertEqual(body['delivery'],'failed');self.assertNotIn('private',str(body))
        self.assertEqual(self.connection.execute(text('select count(*) from team_invitations where student_id=:s'),{'s':self.student_id}).scalar_one(),1)
        self.assertEqual(self.call_inv('',{**self.creator,'proof':proof})[0],400)
    def test_capacity_conflict_and_audit_rollback(self):
        self.setup_invite();invitation=self.send_invite();cookie,payload=self.invitee_proof(invitation,'accept_invitation')
        self.connection.execute(text('update academic_group_policies set max_group_size=1 where academic_cycle_id=:c'),{'c':self.cycle.id})
        self.assertEqual(self.call_inv('/invitee/decision',payload,{'cookie':cookie})[0],400)
        self.connection.execute(text('update academic_group_policies set max_group_size=4 where academic_cycle_id=:c'),{'c':self.cycle.id})
        with patch('app.invitations.InvitationAudit',side_effect=RuntimeError('private')):
            self.assertEqual(self.call_inv('/invitee/decision',payload,{'cookie':cookie})[0],500)
        self.assertEqual(self.connection.execute(text('select status from team_invitations where id=:i'),{'i':invitation}).scalar_one(),'pending')
        self.assertEqual(self.call_inv('/invitee/decision',payload,{'cookie':cookie})[0],200)
    def test_duplicate_membership_and_roster_cycle_mismatch(self):
        self.setup_invite();invitation=self.send_invite();cookie,payload=self.invitee_proof(invitation,'accept_invitation')
        self.assertEqual(self.call_inv('/invitee/decision',{**payload,'cycle_id':self.cycle.id+999},{'cookie':cookie})[0],400)
        self.assertEqual(self.call_inv('/invitee/decision',{**payload,'university_email':'wrong@example.com'},{'cookie':cookie})[0],400)
        self.connection.execute(text("insert into team_members (team_id,academic_cycle_id,full_name,registration_number,university_email,is_creator,is_active) values (:t,:c,'Existing',:r,:e,false,true)"),{'t':self.team_id,'c':self.cycle.id,'r':self.data['registration_number'].upper(),'e':self.data['university_email']})
        self.assertEqual(self.call_inv('/invitee/decision',payload,{'cookie':cookie})[0],400)
        self.assertEqual(self.connection.execute(text('select status from team_invitations where id=:i'),{'i':invitation}).scalar_one(),'pending')
        self.assertEqual(self.connection.execute(text("select count(*) from team_invitation_audit where invitation_id=:i and action='accepted'"),{'i':invitation}).scalar_one(),0)
    def test_smtp_unavailable_and_audit_failure_on_send(self):
        self.setup_invite()
        missing=SimpleNamespace(smtp_host='',smtp_from='',smtp_username='',smtp_password='')
        with patch('app.invitations.settings',missing): self.assertEqual(self.call_inv('/creator/challenge',self.creator)[0],503)
        proof=self.creator_proof()
        with patch('app.invitations.InvitationAudit',side_effect=RuntimeError('private')), patch('app.invitations.send_invitation_email') as mail:
            self.assertEqual(self.call_inv('',{**self.creator,'proof':proof})[0],500);mail.assert_not_called()
        self.assertEqual(self.connection.execute(text('select count(*) from team_invitations where student_id=:s'),{'s':self.student_id}).scalar_one(),0)
        with patch('app.invitations.send_invitation_email'): self.assertEqual(self.call_inv('',{**self.creator,'proof':proof})[0],201)

class InvitationConcurrencyTests(__import__('unittest').TestCase):
    def test_two_sessions_accept_once(self):
        import threading,time
        from datetime import timedelta
        from uuid import uuid4
        from fastapi import HTTPException,Request
        from app.auth import utc_now
        from app.database import SessionLocal
        from app.invitations import InviteeDecision,decide
        from app.models import AcademicCycle,AcademicGroupPolicy,ApprovedStudent,AnonymousVerificationContext,AnonymousVerificationChallenge,AnonymousIdentityProof,Invitation,InvitationOutbox,RosterImport,Team,User,UserRole
        from app.security import generate_session_token,hash_session_token
        suffix=uuid4().hex; ids={}; tokens=[generate_session_token(),generate_session_token()]; cookies=[generate_session_token(),generate_session_token()]
        locked=threading.Event();started=threading.Event();release=threading.Event();results={};failures=[];threads=[]
        try:
            with SessionLocal() as s:
                self.assertEqual(s.scalar(text('select current_database()')),'fyphub_p1')
                admin=User(full_name='Race admin',email=f'admin-{suffix}@example.com',password_hash='x',role=UserRole.ADMIN)
                actor=User(full_name='Race team',email=f'team-{suffix}@example.com',registration_number=f'U{suffix}',password_hash='x',role=UserRole.STUDENT)
                cycle=AcademicCycle(code=f'INV-{suffix}',display_name='Invitation race');s.add_all([admin,actor,cycle]);s.flush()
                team=Team(academic_cycle_id=cycle.id,shared_user_id=actor.id);batch=RosterImport(academic_cycle_id=cycle.id,imported_by_id=admin.id,confirmation_hash=suffix);s.add_all([team,batch,AcademicGroupPolicy(academic_cycle_id=cycle.id,max_group_size=4)]);s.flush()
                student=ApprovedStudent(academic_cycle_id=cycle.id,import_id=batch.id,name='Invitee',registration_number=f'R{suffix}',university_email=f'invitee-{suffix}@example.com',semester=7,group_code='X');s.add(student);s.flush()
                inv=Invitation(team_id=team.id,cycle_id=cycle.id,student_id=student.id,status='pending');s.add(inv);s.flush()
                s.add(InvitationOutbox(invitation_id=inv.id,status='smtp_accepted'))
                for token,cookie in zip(tokens,cookies):
                    context=AnonymousVerificationContext(token_hash=hash_session_token(cookie),client_hash=hash_session_token(suffix),expires_at=utc_now()+timedelta(minutes=5));s.add(context);s.flush()
                    challenge=AnonymousVerificationChallenge(context_id=context.id,student_id=student.id,cycle_id=cycle.id,purpose='invitation',action='accept_invitation',target_team_id=team.id,target_invitation_id=inv.id,code_hash='test',expires_at=utc_now()+timedelta(minutes=5));s.add(challenge);s.flush()
                    s.add(AnonymousIdentityProof(challenge_id=challenge.id,context_id=context.id,student_id=student.id,cycle_id=cycle.id,purpose='invitation',action='accept_invitation',target_team_id=team.id,target_invitation_id=inv.id,token_hash=hash_session_token(token),expires_at=utc_now()+timedelta(minutes=5)))
                ids={'cycle':cycle.id,'admin':admin.id,'actor':actor.id,'team':team.id,'batch':batch.id,'student':student.id,'inv':inv.id,'reg':student.registration_number,'email':student.university_email};s.commit()
            def worker(label,token,cookie):
                try:
                    with SessionLocal() as session:
                        session.execute(text("set local statement_timeout='5s'"));results[label+'_pid']=session.scalar(text('select pg_backend_pid()'))
                        if label=='first':
                            original=session.commit
                            def hold():
                                session.flush();locked.set()
                                if not release.wait(4): raise AssertionError('release timeout')
                                original()
                            session.commit=hold
                        else:
                            if not locked.wait(4): raise AssertionError('first timeout')
                            started.set()
                        data=InviteeDecision(cycle_id=ids['cycle'],invitation_id=ids['inv'],registration_number=ids['reg'],university_email=ids['email'],action='accept_invitation',proof=token)
                        req=Request({'type':'http','method':'POST','headers':[(b'cookie',f'fyphub_verification={cookie}'.encode())],'path':'/','query_string':b''})
                        try: results[label]=decide(data,req,session)['status']
                        except HTTPException as exc: results[label]=exc.status_code
                except Exception as exc: failures.append(repr(exc));locked.set();started.set()
            threads=[threading.Thread(target=worker,args=(name,token,cookie),daemon=True) for name,token,cookie in zip(('first','second'),tokens,cookies)]
            for t in threads:t.start()
            self.assertTrue(locked.wait(4));self.assertTrue(started.wait(4));self.assertEqual(failures,[]);self.assertNotEqual(results['first_pid'],results['second_pid'])
            deadline=time.monotonic()+3;blocked=False
            with SessionLocal() as observer:
                while time.monotonic()<deadline:
                    blocked=observer.scalar(text('select :first = any(pg_blocking_pids(:second))'),{'first':results['first_pid'],'second':results['second_pid']})
                    if blocked:break
                    time.sleep(.02)
            self.assertTrue(blocked);release.set()
            for t in threads:t.join(6)
            self.assertFalse(any(t.is_alive() for t in threads));self.assertEqual(failures,[]);self.assertEqual((results['first'],results['second']),('accepted',400))
            with SessionLocal() as s:
                self.assertEqual(s.scalar(text('select count(*) from team_members where team_id=:team and registration_number=upper(:reg)'),ids),1)
                self.assertEqual(s.scalar(text("select count(*) from team_invitation_audit where invitation_id=:inv and action='accepted'"),ids),1)
                self.assertEqual(s.scalar(text('select count(*) from anonymous_identity_proofs where target_invitation_id=:inv and consumed_at is not null'),ids),1)
        finally:
            release.set()
            for t in threads:t.join(6)
            if ids and not any(t.is_alive() for t in threads):
                with SessionLocal() as s:
                    s.execute(text('set local session_replication_role = replica'))
                    for sql in ('delete from team_invitation_audit where invitation_id=:inv','delete from anonymous_identity_proofs where target_invitation_id=:inv','delete from anonymous_verification_challenges where target_invitation_id=:inv','delete from anonymous_verification_contexts where client_hash=:hash','delete from invitation_outbox where invitation_id=:inv','delete from team_invitations where id=:inv','delete from team_members where team_id=:team','delete from approved_students where id=:student','delete from roster_imports where id=:batch','delete from teams where id=:team','delete from academic_group_policies where academic_cycle_id=:cycle','delete from academic_cycles where id=:cycle','delete from users where id in (:actor,:admin)'):
                        s.execute(text(sql),{**ids,'hash':hash_session_token(suffix)})
                    s.commit()
