from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.test import TransactionTestCase
from django.db import transaction,close_old_connections
from django.core.exceptions import PermissionDenied,ValidationError
from apps.core.models import Case
from apps.identity.models import Grant
from apps.core.management.commands.seed_demo import ACTIONS
from apps.policy.services import register_reference
from apps.finance import bu as domain
from apps.finance.models import BUWork,BUReport,BUEventClaim
from .bu_helpers import fixture,configure,body,event,publish
from .helpers import activate
class BUConcurrencyTests(TransactionTestCase):
 def setUp(self):self.f=fixture()
 def parallel(self,work):
  def task(n):
   close_old_connections()
   try:return work(n)
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(task,[0,1]))
 def test_two_connections_capture_same_export_once(self):
  f=self.f;raw=body(f);scope={k:f['bu_config']['export'][k] for k in ['entity','period','currency']}
  ids=self.parallel(lambda _:domain.capture(f['preparer'],f['case'].pk,'events','same',scope,raw,None).pk);self.assertEqual(ids[0],ids[1]);self.assertEqual(BUWork.objects.filter(kind='source').count(),1);self.assertEqual(BUEventClaim.objects.count(),1)
 def test_two_connections_publish_same_work_once(self):
  f=self.f;w=event(f);p=publish(f,w)
  ids=self.parallel(lambda _:domain.publish(f['preparer'],f['case'].pk,w.pk,'same-publication',None).pk);self.assertEqual(ids[0],ids[1]);self.assertEqual(BUReport.objects.filter(operation_key='same-publication').count(),1)
 def test_two_case_event_claim_race_has_one_owner_and_no_duplicate(self):
  f=self.f;c=Case.objects.create(tenant=f['case'].tenant,title='Other synthetic event source',kind='project',synthetic=True)
  for u in [f['preparer'],f['reviewer'],f['manager']]:
   for action in ACTIONS:Grant.objects.create(case=c,user=u,action=action)
  from apps.core.services import add_evidence
  e=add_evidence(f['preparer'],c.pk,'policy_decision','Synthetic role decision','synthetic:bu-race');refs=[]
  for u in [f['preparer'],f['reviewer']]:refs.append(register_reference(f['preparer'],c.pk,'Finance-'+str(u.pk),'schema:psl/role-assignment/v1',{'user_id':u.pk,'role':'Finance'},e.pk).ref)
  activate(f['preparer'],c,'D05.role_principal_assignments',refs,e);other=configure({'case':c,'preparer':f['preparer'],'reviewer':f['reviewer'],'manager':f['manager'],'e':{'policy_decision':e}});scope={k:f['bu_config']['export'][k] for k in ['entity','period','currency']};raw=body(f);cases=[f['case'],c]
  ids=self.parallel(lambda n:domain.capture(f['preparer'],cases[n].pk,'events','cross-case-race',scope,raw,None).pk);rows=list(BUWork.objects.filter(pk__in=ids));self.assertEqual(sum(r.metadata['accepted'] for r in rows),1);self.assertEqual(BUEventClaim.objects.count(),1);self.assertEqual(next(r for r in rows if not r.metadata['accepted']).payload,{})
 def test_committed_revocation_blocks_report_reader_on_second_connection(self):
  f=self.f;p=publish(f,event(f));locked=Event();commit=Event()
  def revoke():
   close_old_connections()
   try:
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
     if not commit.wait(10):raise AssertionError('Coordination timeout')
     Grant.objects.filter(case=f['case'],user=f['manager'],action='bu.report.read').update(active=False)
   finally:close_old_connections()
  def read():
   close_old_connections()
   try:
    try:domain.read_report(f['manager'],p.pk)
    except PermissionDenied:return 'held'
    return 'read'
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:
   a=pool.submit(revoke);self.assertTrue(locked.wait(10));b=pool.submit(read);commit.set();a.result(timeout=30);self.assertEqual(b.result(timeout=30),'held')

 def test_new_classification_commits_before_publication_and_blocks_omission(self):
  from .bu_helpers import staff,review
  f=self.f;w=staff(f,rules=[],declared=[]);review(f,w);locked=Event();commit=Event()
  def classify():
   close_old_connections()
   try:
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
     if not commit.wait(10):raise AssertionError('Coordination timeout')
     r=domain.rule(f['preparer'],f['case'].pk,f['match'].pk,'classification-race','classification-race',f['bu_config']['exception'],None)
     domain.review(f['reviewer'],f['case'].pk,r.pk,'rule','approve','classification-approve',f['e']['bu_review'].pk,None)
   finally:close_old_connections()
  def send():
   close_old_connections()
   try:
    try:domain.publish(f['preparer'],f['case'].pk,w.pk,'omission-race',None)
    except ValidationError:return 'held'
    return 'published'
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:
   a=pool.submit(classify);self.assertTrue(locked.wait(10));b=pool.submit(send);commit.set();a.result(timeout=60);self.assertEqual(b.result(timeout=60),'held')
  self.assertFalse(BUReport.objects.exists())
