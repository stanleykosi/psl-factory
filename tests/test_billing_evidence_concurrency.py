import os,sys,subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Event,Barrier
from datetime import timedelta
from django.test import TransactionTestCase
from django.db import close_old_connections,transaction,connections
from django.conf import settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.models import Case
from apps.identity.models import Grant
from apps.finance import billing_evidence as d,invoices,invoice_delivery
from apps.finance.models import BillingControlReceipt,InvoiceIssue,InvoiceJob,BillingReleaseAssessment
from .d03_helpers import fixture,observe,bound,evidence
class BillingEvidenceConcurrencyTests(TransactionTestCase):
 def setUp(self):self.f=fixture()
 def parallel(self,call):
  def task(n):
   close_old_connections()
   try:return call(n)
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(task,[0,1]))
 def race(self,mutation,action):
  locked=Event();commit=Event();f=self.f
  def first():
   close_old_connections()
   try:
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
     if not commit.wait(10):raise AssertionError('Coordination timeout')
     mutation()
   finally:close_old_connections()
  def second():
   close_old_connections()
   try:
    try:action()
    except (ValidationError,PermissionDenied):return 'held'
    return 'used'
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:
   a=pool.submit(first);self.assertTrue(locked.wait(10));b=pool.submit(second);commit.set();a.result(timeout=30);self.assertEqual(b.result(timeout=30),'held')
 def test_unavailable_control_commits_before_invoice_dispatch(self):
  f=self.f;bound(f);j=invoices.reserve(f['actor'],f['case'].pk,f['invoice'].pk,'issue','Finance',None);pk,fence=invoice_delivery.claim();self.race(lambda:observe(f,changes={'source_version':'v2','outcome':'unavailable'}),lambda:invoice_delivery.deliver_local(pk,fence));self.assertFalse(InvoiceIssue.objects.exists())
 def test_source_read_revocation_commits_before_binding(self):
  f=self.f;observe(f);r=d.assess(f['actor'],f['case'].pk,f['invoice'].pk,'issue');self.race(lambda:Grant.objects.filter(case=f['case'],user=f['owner'],action='d03.source.read').update(active=False),lambda:d.bind(f['owner'],f['case'].pk,r.pk))
 def test_competing_reservations_have_one_job_and_effect(self):
  f=self.f;bound(f);out=self.parallel(lambda _:invoices.reserve(f['actor'],f['case'].pk,f['invoice'].pk,'issue','Finance',None).pk);self.assertEqual(out[0],out[1]);self.parallel(lambda _:invoice_delivery.run_once());self.assertEqual(InvoiceIssue.objects.count(),1)
 def test_separate_worker_recovers_committed_receipt_after_source_revocation(self):
  f=self.f;bound(f);j=invoices.reserve(f['actor'],f['case'].pk,f['invoice'].pk,'issue','Finance',None);pk,fence=invoice_delivery.claim();invoice_delivery.deliver_local(pk,fence)
  InvoiceJob.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1));Grant.objects.filter(case=f['case'],user=f['owner'],action='d03.source.read').update(active=False)
  env=os.environ.copy();env['PGDATABASE']=connections['default'].settings_dict['NAME'];env['PYTHONIOENCODING']='utf-8'
  result=subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),'work_invoices','--limit','1'],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60)
  self.assertEqual(result.returncode,0,result.stderr);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(InvoiceIssue.objects.count(),1)

 def test_simultaneous_first_control_capture_is_one_receipt(self):
  f=self.f
  from django.utils import timezone
  i=f['invoice'];v=f['v'];payload={'invoice_id':i.pk,'invoice_sha256':i.sha256,'preparation_key':i.preparation.operation_key,'effect':'issue','control_key':v['control_key'],'system':'synthetic-billing-system','external_ref':str(f['case'].pk)+':issue','source_version':'v1','flow_ref':v['flow_ref'],'flow_version':v['flow_version'],'environment_ref':v['environment_ref'],'observed_at':timezone.now().isoformat(),'outcome':'passed','evidence_class':'synthetic_reference'}
  e=evidence(f,v['control_evidence_kind'],payload);barrier=Barrier(2)
  def capture(_):
   barrier.wait(timeout=10);return d.observe_control(f['owner'],f['case'].pk,i.pk,e.pk).pk
  ids=self.parallel(capture);self.assertEqual(ids[0],ids[1]);self.assertEqual(BillingControlReceipt.objects.count(),1)
 def test_simultaneous_first_source_capture_and_cross_case_claim(self):
  from apps.finance.models import BillingEvidenceSource
  from apps.core.management.commands.seed_demo import ACTIONS
  f=self.f;s=f['statement'];payload=dict(s.payload,external_ref='first-shared-source');e=evidence(f,'d03_source',payload['quote']);barrier=Barrier(2)
  def capture(_):
   barrier.wait(timeout=10);return d.capture_source(f['actor'],f['case'].pk,'shared-source',payload,e.pk).pk
  ids=self.parallel(capture);self.assertEqual(ids[0],ids[1]);self.assertEqual(BillingEvidenceSource.objects.filter(external_ref='first-shared-source').count(),1)
  c=Case.objects.create(tenant=f['case'].tenant,title='Synthetic cross-case source identity',synthetic=True)
  Grant.objects.bulk_create([Grant(case=c,user=f['actor'],action=x) for x in ACTIONS]);other=dict(f,case=c);e2=evidence(other,'d03_source',payload['quote'])
  with self.assertRaises(ValidationError):d.capture_source(f['actor'],c.pk,'other-claim',payload,e2.pk)
