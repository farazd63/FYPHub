import threading
import unittest
from unittest.mock import patch
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import engine, SessionLocal
from app.models import AcademicCycle, SupervisorCapacityPolicy, Team, User, UserRole
from app.supervisor_assignments import AssignmentWrite, assign
from tests import test_supervisor_capacity as fixtures

class AssignmentTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.SupervisorCapacityTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.SupervisorCapacityTests.tearDownClass.__func__)
    get_test_db = classmethod(fixtures.SupervisorCapacityTests.get_test_db.__func__)
    setUp = fixtures.SupervisorCapacityTests.setUp
    payload = fixtures.SupervisorCapacityTests.payload
    def make_team(self, cycle=None):
        suffix = uuid4().hex[:12]; session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        user = User(full_name="Team creator", email=f"team-{suffix}@example.com", registration_number=f"T{suffix}".upper(), password_hash="test", role=UserRole.STUDENT); session.add(user); session.flush()
        team = Team(academic_cycle_id=cycle or self.cycle.id, shared_user_id=user.id); session.add(team); session.commit(); result=team.id; session.close(); return result
    def call(self, method, path, data=None, token=None): return fixtures.request(method,path,data,token=token)
    def test_authorization_validation_history_and_capacity(self):
        path='/api/v1/admin/supervisor-assignments'; first=self.make_team(); second=self.make_team(); body={'team_id':first,'supervisor_id':self.supervisor.id,'academic_cycle_id':self.cycle.id,'academic_year':self.year,'session':'FALL'}
        self.assertEqual(self.call('POST',path,body)[0],401); self.assertEqual(self.call('POST',path,body,self.student_token)[0],403)
        self.assertEqual(self.call('POST',path,body,self.token)[1]['detail']['code'],'capacity_policy_missing')
        _, policy=self.call('POST','/api/v1/admin/supervisor-capacities',self.payload(maximum_groups=1),self.token)
        code, created=self.call('POST',path,body,self.token); self.assertEqual(code,201)
        self.assertEqual(self.call('POST',path,body,self.token)[1]['detail']['code'],'team_already_assigned')
        full_status, full_body = self.call('POST',path,{**body,'team_id':second},self.token)
        self.assertEqual((full_status, full_body['detail']['code'], full_body['detail']['message']), (409, 'capacity_full', f'This supervisor has no remaining annual capacity for {self.cycle.academic_year}. Fall and Spring assignments share the same yearly limit.'))
        self.assertEqual(self.call('PUT',f"/api/v1/admin/supervisor-capacities/{policy['id']}",self.payload(supervisor_id=self.student.id),self.token)[0],409)
        _, stats=self.call('GET',f"/api/v1/admin/supervisor-capacities/{policy['id']}",token=self.token); self.assertEqual((stats['assigned'],stats['remaining'],stats['full']),(1,0,True))
        self.assertEqual(self.call('POST',f"{path}/{created['id']}/end",token=self.token)[0],200)
        self.assertEqual(self.call('POST',path,{**body,'team_id':second},self.token)[0],201)
        self.assertEqual(self.connection.execute(text('select count(*) from supervisor_assignments where academic_cycle_id=:id'),{'id':self.cycle.id}).scalar_one(),2)
    def test_wrong_cycle_ineligible_and_audit_rollback(self):
        path='/api/v1/admin/supervisor-assignments'; team=self.make_team(); body={'team_id':team,'supervisor_id':self.supervisor.id,'academic_cycle_id':self.cycle.id,'academic_year':self.year,'session':'FALL'}
        self.call('POST','/api/v1/admin/supervisor-capacities',self.payload(),self.token)
        self.assertEqual(self.call('POST',path,{**body,'supervisor_id':self.inactive.id},self.token)[1]['detail']['code'],'supervisor_ineligible')
        other=AcademicCycle(code=f"OTHER-{uuid4().hex[:8]}",display_name='Other'); session=Session(bind=self.connection,join_transaction_mode='create_savepoint'); session.add(other); session.commit(); other_id=other.id; session.close()
        other_team=self.make_team(other_id)
        self.assertEqual(self.call('POST',path,{**body,'team_id':other_team},self.token)[1]['detail']['code'],'cycle_mismatch')
        with patch('app.main.add_admin_audit_event',side_effect=RuntimeError('secret')):
            status,result=self.call('POST',path,body,self.token)
        self.assertEqual(status,500); self.assertNotIn('secret',str(result)); self.assertEqual(self.connection.execute(text('select count(*) from supervisor_assignments where team_id=:id'),{'id':team}).scalar_one(),0)
    def test_fall_and_spring_share_annual_capacity_and_counts(self):
        session = Session(bind=self.connection, join_transaction_mode='create_savepoint')
        spring = AcademicCycle(code=f'SPRING-{uuid4().hex[:8]}', display_name='Spring', academic_year=self.year, session='SPRING')
        session.add(spring); session.commit(); spring_id = spring.id; session.close()
        first, second, third = self.make_team(), self.make_team(spring_id), self.make_team(spring_id)
        _, policy = self.call('POST', '/api/v1/admin/supervisor-capacities', self.payload(maximum_groups=2), self.token)
        path = '/api/v1/admin/supervisor-assignments'
        fall = {'team_id': first, 'supervisor_id': self.supervisor.id, 'academic_cycle_id': self.cycle.id, 'academic_year': self.year, 'session': 'FALL'}
        spring_payload = {'team_id': second, 'supervisor_id': self.supervisor.id, 'academic_cycle_id': spring_id, 'academic_year': self.year, 'session': 'SPRING'}
        self.assertEqual(self.call('POST', path, fall, self.token)[0], 201)
        self.assertEqual(self.call('POST', path, spring_payload, self.token)[0], 201)
        status, stats = self.call('GET', '/api/v1/admin/supervisor-capacities', token=self.token)
        row = next(item for item in stats if item['id'] == policy['id'])
        self.assertEqual((status, row['fall_assigned'], row['spring_assigned'], row['total_assigned'], row['remaining_capacity'], row['status']), (200, 1, 1, 2, 0, 'FULL'))
        blocked = {**spring_payload, 'team_id': third}
        status, body = self.call('POST', path, blocked, self.token)
        self.assertEqual((status, body['detail']['code']), (409, 'capacity_full'))
    def test_00_concurrent_capacity(self):
        suffix=uuid4().hex[:10]; session=SessionLocal(); admin=User(full_name='Admin',email=f'a-{suffix}@example.com',password_hash='x',role=UserRole.ADMIN); supervisor=User(full_name='Supervisor',email=f's-{suffix}@example.com',password_hash='x',role=UserRole.SUPERVISOR); cycle=AcademicCycle(code=f'RACE-{suffix}',display_name='Race',academic_year=1900 + int(suffix[:8], 16) % 301,session='FALL'); session.add_all([admin,supervisor,cycle]); session.flush(); cycle_year=cycle.academic_year; session.add(SupervisorCapacityPolicy(supervisor_id=supervisor.id,academic_cycle_id=cycle.id,academic_year=cycle_year,max_group_capacity=1)); teams=[]
        for n in range(2):
            user=User(full_name='Student',email=f't{n}-{suffix}@example.com',registration_number=f'R{n}{suffix}'.upper(),password_hash='x',role=UserRole.STUDENT); session.add(user); session.flush(); team=Team(academic_cycle_id=cycle.id,shared_user_id=user.id); session.add(team); session.flush(); teams.append((team.id,user.id))
        session.commit(); aid,sid,cid=admin.id,supervisor.id,cycle.id; session.close(); gate=threading.Barrier(2); results=[]
        def worker(team):
            db=SessionLocal()
            try: gate.wait(timeout=5); assign(AssignmentWrite(team_id=team,supervisor_id=sid,academic_cycle_id=cid,academic_year=cycle_year,session='FALL'),type('Req',(),{'headers':{}})(),db.get(User,aid),db); results.append('ok')
            except HTTPException as exc: results.append(exc.detail['code'])
            except Exception as exc: results.append(str(exc))
            finally: db.close()
        try:
            with patch('app.main.add_admin_audit_event',return_value=None):
                threads=[threading.Thread(target=worker,args=(team_id,)) for team_id,_ in teams]
                for thread in threads: thread.start()
                for thread in threads: thread.join(timeout=10)
                self.assertEqual(sorted(results),['capacity_full','ok'])
        finally:
            db=SessionLocal(); db.execute(text('delete from supervisor_assignments where academic_cycle_id=:id'),{'id':cid}); db.execute(text('delete from supervisor_capacity_policies where academic_cycle_id=:id'),{'id':cid}); db.execute(text('delete from teams where academic_cycle_id=:id'),{'id':cid}); db.execute(text('delete from academic_cycles where id=:id'),{'id':cid}); db.execute(text('delete from users where id in :ids').bindparams(__import__('sqlalchemy').bindparam('ids',expanding=True)),{'ids':[aid,sid,*[u for _,u in teams]]}); db.commit(); db.close()

