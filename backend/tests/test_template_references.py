"""Rollback-isolated regression coverage for internal template references."""
import threading
import unittest
from collections.abc import Iterator
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.auth import SESSION_COOKIE_NAME, utc_now
from app.database import SessionLocal, engine, get_db
from app import main
from app.main import app, create_template_version
from app.models import AcademicRuleVersion, AuthSession, TemplateReference, TemplateReferenceVersion, TemplateType, User, UserRole
from app.security import generate_session_token, hash_session_token
from app.schemas.templates import TemplateVersionCreate
from tests.test_auth_sessions import request

class TemplateReferenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.connection=engine.connect(); cls.transaction=cls.connection.begin()
  if cls.connection.execute(text("select current_database()")).scalar_one()!="fyphub_p1": raise RuntimeError("requires fyphub_p1")
  app.dependency_overrides[get_db]=cls.db
 @classmethod
 def tearDownClass(cls): app.dependency_overrides.pop(get_db,None); cls.transaction.rollback(); cls.connection.close()
 @classmethod
 def db(cls)->Iterator[Session]:
  s=Session(bind=cls.connection,expire_on_commit=False,join_transaction_mode="create_savepoint")
  try: yield s
  finally: s.close()
 def setUp(self):
  s=Session(bind=self.connection,expire_on_commit=False,join_transaction_mode="create_savepoint"); a=User(full_name="Template Admin",email=f"template-{uuid4().hex}@example.com",registration_number=None,password_hash="test",role=UserRole.ADMIN); n=User(full_name="Student",email=f"student-{uuid4().hex}@example.com",registration_number=f"T{uuid4().hex[:9]}",password_hash="test",role=UserRole.STUDENT); s.add_all([a,n]); s.flush(); self.admin_id=a.id; self.token=generate_session_token(); s.add(AuthSession(user_id=a.id,token_hash=hash_session_token(self.token),expires_at=utc_now().replace(year=utc_now().year+1))); self.student=generate_session_token(); s.add(AuthSession(user_id=n.id,token_hash=hash_session_token(self.student),expires_at=utc_now().replace(year=utc_now().year+1))); s.commit(); s.close()
 def headers(self,token=None,origin=None):
  h={} if token is None else {"cookie":f"{SESSION_COOKIE_NAME}={token}"}
  if origin: h["origin"]=origin
  return h
 def payload(self): return {"template_type":"SHORT","title":"Reference","provenance":"OBSERVED_REFERENCE","source_note":"Filled example","rules":{"page_size":"A4"}}
 def baseline_reference(self):
  """Create a test-local lineage without creating an audit record."""
  s=Session(bind=self.connection,expire_on_commit=False,join_transaction_mode="create_savepoint")
  root=TemplateReference(template_type=TemplateType.LONG); s.add(root); s.flush()
  version=TemplateReferenceVersion(template_reference_id=root.id,version_number=1,title="Baseline",provenance="OBSERVED_REFERENCE",source_note="Test baseline",created_by_id=self.admin_id); s.add(version); s.flush()
  rule=AcademicRuleVersion(template_reference_version_id=version.id,version_number=1,provenance="OBSERVED_REFERENCE",rules={"page_size":"A4"},created_by_id=self.admin_id); s.add(rule); s.commit(); s.close()
  return root.id,version.id
 def cleanup_baseline(self,root_id,version_id):
  # These rows are test fixtures; audit rows are never deleted.
  s=Session(bind=self.connection,expire_on_commit=False,join_transaction_mode="create_savepoint")
  s.execute(text("delete from academic_rule_versions where template_reference_version_id=:id"),{"id":version_id}); s.execute(text("delete from template_reference_versions where id=:id"),{"id":version_id}); s.execute(text("delete from template_references where id=:id"),{"id":root_id}); s.commit(); s.close()
 def snapshot(self,root_id,version_id):
  return {"versions":self.connection.execute(text("select id, version_number, title, provenance, source_note from template_reference_versions where template_reference_id=:id order by version_number"),{"id":root_id}).mappings().all(),"rules":self.connection.execute(text("select id, version_number, provenance, rules from academic_rule_versions where template_reference_version_id=:id order by version_number"),{"id":version_id}).mappings().all(),"audit_ids":self.connection.execute(text("select id from admin_audit_events order by id")).scalars().all()}
 def test_access_validation_and_history(self):
  self.assertEqual(request("GET","/api/v1/admin/template-references")[0],401); self.assertEqual(request("GET","/api/v1/admin/template-references",headers=self.headers(self.student))[0],403)
  self.assertEqual(request("GET","/api/v1/admin/template-references/999999",headers=self.headers(self.token))[0],404)
  self.assertEqual(request("POST","/api/v1/admin/template-references",{**self.payload(),"rules":{"bad":1}},headers=self.headers(self.token))[0],422)
  status,_,body=request("POST","/api/v1/admin/template-references",self.payload(),headers=self.headers(self.token)); self.assertEqual(status,201); root=body["reference_id"]; version=body["versions"][0]["template"]["id"]
  self.assertEqual(request("POST",f"/api/v1/admin/template-references/{root}/versions",{"title":"Second","provenance":"OBSERVED_REFERENCE","source_note":"Later"},headers=self.headers(self.token))[0],201)
  self.assertEqual(request("POST",f"/api/v1/admin/template-reference-versions/{version}/rules",{"provenance":"OBSERVED_REFERENCE","rules":{}},headers=self.headers(self.token))[0],201)
  status,_,listed=request("GET","/api/v1/admin/template-references",headers=self.headers(self.token)); self.assertEqual(status,200); self.assertEqual([item["reference_id"] for item in listed if item["id"] in {version}], [root])
  status,_,history=request("GET",f"/api/v1/admin/template-references/{root}",headers=self.headers(self.token)); self.assertEqual(status,200); self.assertEqual([v["template"]["version_number"] for v in history["versions"]],[1,2]); self.assertEqual(history["versions"][0]["rules"][0]["rules"],{"page_size":"A4"})
 def test_origin_and_numeric_rule_validation(self):
  self.assertEqual(request("POST","/api/v1/admin/template-references",self.payload(),headers=self.headers(self.token,"http://evil.example"))[0],403)
  self.assertEqual(request("POST","/api/v1/admin/template-references",{**self.payload(),"rules":{"margin_mm":0}},headers=self.headers(self.token))[0],422)
  self.assertEqual(request("POST","/api/v1/admin/template-references",{**self.payload(),"rules":{"font_size_pt":"large"}},headers=self.headers(self.token))[0],422)
 def test_audit_failure_rolls_back_initial_reference(self):
  original=main.add_admin_audit_event
  def fail(*_args,**_kwargs): raise RuntimeError("test audit failure")
  main.add_admin_audit_event=fail
  try:
   status,_,_=request("POST","/api/v1/admin/template-references",{**self.payload(),"template_type":"LONG"},headers=self.headers(self.token))
  finally: main.add_admin_audit_event=original
  self.assertEqual(status,500)
  self.assertEqual(self.connection.execute(text("select count(*) from template_references where template_type='LONG'")).scalar_one(),0)
 def test_audit_failure_rolls_back_metadata_version(self):
  root,version=self.baseline_reference(); before=self.snapshot(root,version)
  original=main.add_admin_audit_event; main.add_admin_audit_event=lambda *_a,**_k: (_ for _ in ()).throw(RuntimeError("audit"))
  try: status,_,body=request("POST",f"/api/v1/admin/template-references/{root}/versions",{"title":"Nope","provenance":"OBSERVED_REFERENCE","source_note":"Nope"},headers=self.headers(self.token))
  finally: main.add_admin_audit_event=original
  try:
   self.assertEqual(status,500); self.assertEqual(body,{"detail":"Template reference could not be saved."}); self.assertEqual(self.snapshot(root,version),before); self.assertEqual(self.connection.execute(text("select 1")).scalar_one(),1)
  finally: self.cleanup_baseline(root,version)
 def test_audit_failure_rolls_back_rule_version(self):
  root,version=self.baseline_reference(); before=self.snapshot(root,version)
  original=main.add_admin_audit_event; main.add_admin_audit_event=lambda *_a,**_k: (_ for _ in ()).throw(RuntimeError("audit"))
  try: status,_,body=request("POST",f"/api/v1/admin/template-reference-versions/{version}/rules",{"provenance":"OBSERVED_REFERENCE","rules":{"font_family":"CMR"}},headers=self.headers(self.token))
  finally: main.add_admin_audit_event=original
  try:
   self.assertEqual(status,500); self.assertEqual(body,{"detail":"Academic rule version could not be saved."}); self.assertEqual(self.snapshot(root,version),before); self.assertEqual(self.connection.execute(text("select 1")).scalar_one(),1)
  finally: self.cleanup_baseline(root,version)
 def _test_concurrent_metadata_version_allocation(self):
  """Separate connections serialize the production allocator and retain lineage."""
  suffix=uuid4().hex[:12]; root_id=None; admin_id=None; original=main.add_admin_audit_event
  try:
   with SessionLocal() as s:
    admin=User(full_name="Template race admin",email=f"template-race-{suffix}@example.com",registration_number=None,password_hash="test",role=UserRole.ADMIN)
    root=TemplateReference(template_type=TemplateType.LONG); s.add_all([admin,root]); s.flush()
    base=TemplateReferenceVersion(template_reference_id=root.id,version_number=1,title="Baseline",provenance="OBSERVED_REFERENCE",source_note="Race baseline",created_by_id=admin.id); s.add(base); s.commit(); root_id,admin_id=root.id,admin.id
   # The allocation test deliberately avoids durable audit rows; audit atomicity
   # is independently verified above and append-only rows must not be deleted.
   main.add_admin_audit_event=lambda *_a,**_k: None
   gate=threading.Barrier(3,timeout=5); results=[]; failures=[]
   def worker(label):
    s=SessionLocal()
    try:
     actor=s.get(User,admin_id); gate.wait(); value=create_template_version(root_id,TemplateVersionCreate(title=f"Concurrent {label}",provenance="OBSERVED_REFERENCE",source_note="Race"),type("Request",(),{"headers":{}})(),actor,s); results.append((value.id,value.version_number,value.template_reference_id))
    except Exception as error: failures.append(error)
    finally: s.close()
   threads=[threading.Thread(target=worker,args=(label,),daemon=True) for label in ("A","B")]
   [thread.start() for thread in threads]; gate.wait(); [thread.join(5) for thread in threads]
   self.assertFalse(any(thread.is_alive() for thread in threads)); self.assertEqual(failures,[]); self.assertEqual(sorted(number for _,number,_ in results),[2,3]); self.assertTrue(all(parent==root_id for _,_,parent in results))
   with SessionLocal() as s:
    lineage=[(item.version_number,item.title) for item in s.query(TemplateReferenceVersion).filter_by(template_reference_id=root_id).order_by(TemplateReferenceVersion.version_number)]
    self.assertEqual(lineage[0],(1,"Baseline")); self.assertEqual({title for _,title in lineage[1:]},{"Concurrent A","Concurrent B"})
  finally:
   main.add_admin_audit_event=original
   if root_id is not None:
    with SessionLocal() as s:
     s.execute(text("delete from academic_rule_versions where template_reference_version_id in (select id from template_reference_versions where template_reference_id=:id)"),{"id":root_id}); s.execute(text("delete from template_reference_versions where template_reference_id=:id"),{"id":root_id}); s.execute(text("delete from template_references where id=:id"),{"id":root_id}); s.execute(text("delete from users where id=:id"),{"id":admin_id}); s.commit()


class TemplateReferenceConcurrencyTests(unittest.TestCase):
 def test_concurrent_metadata_version_allocation(self):
  """Two real sessions use the production allocator without duplicate versions."""
  suffix=uuid4().hex[:12]; root_id=None; admin_id=None; original=main.add_admin_audit_event
  try:
   with SessionLocal() as s:
    admin=User(full_name="Template race admin",email=f"template-race-{suffix}@example.com",registration_number=None,password_hash="test",role=UserRole.ADMIN)
    root=TemplateReference(template_type=TemplateType.LONG); s.add_all([admin,root]); s.flush()
    s.add(TemplateReferenceVersion(template_reference_id=root.id,version_number=1,title="Baseline",provenance="OBSERVED_REFERENCE",source_note="Race baseline",created_by_id=admin.id)); s.commit(); root_id,admin_id=root.id,admin.id
   # Audit persistence is covered by rollback tests; do not leave immutable test events.
   main.add_admin_audit_event=lambda *_a,**_k: None
   gate=threading.Barrier(3,timeout=5); results=[]; failures=[]
   def worker(label):
    s=SessionLocal()
    try:
     actor=s.get(User,admin_id); gate.wait(); value=create_template_version(root_id,TemplateVersionCreate(title=f"Concurrent {label}",provenance="OBSERVED_REFERENCE",source_note="Race"),type("Request",(),{"headers":{}})(),actor,s); results.append((value.id,value.version_number,value.template_reference_id))
    except Exception as error: failures.append(error)
    finally: s.close()
   threads=[threading.Thread(target=worker,args=(label,),daemon=True) for label in ("A","B")]
   [thread.start() for thread in threads]; gate.wait(); [thread.join(5) for thread in threads]
   self.assertFalse(any(thread.is_alive() for thread in threads)); self.assertEqual(failures,[]); self.assertEqual(sorted(number for _,number,_ in results),[2,3]); self.assertTrue(all(parent==root_id for _,_,parent in results))
   with SessionLocal() as s:
    lineage=[(item.version_number,item.title) for item in s.query(TemplateReferenceVersion).filter_by(template_reference_id=root_id).order_by(TemplateReferenceVersion.version_number)]
    self.assertEqual(lineage[0],(1,"Baseline")); self.assertEqual({title for _,title in lineage[1:]},{"Concurrent A","Concurrent B"})
  finally:
   main.add_admin_audit_event=original
   if root_id is not None:
    with SessionLocal() as s:
     s.execute(text("delete from academic_rule_versions where template_reference_version_id in (select id from template_reference_versions where template_reference_id=:id)"),{"id":root_id}); s.execute(text("delete from template_reference_versions where template_reference_id=:id"),{"id":root_id}); s.execute(text("delete from template_references where id=:id"),{"id":root_id}); s.execute(text("delete from users where id=:id"),{"id":admin_id}); s.commit()
