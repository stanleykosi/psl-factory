from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.test import TransactionTestCase
from django.db import close_old_connections,transaction
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.documents import migration_readiness as d
from apps.documents.migration_models import MigrationProof,MigrationReadinessReview,MigrationAF13Binding
from .migration_helpers import fixture,proof,assessed,review,bound,evidence
class MigrationConcurrencyTests(TransactionTestCase):
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
 def test_two_owner_reviews_record_one_intent(self):
  f=self.f;r=assessed(f);out=self.parallel(lambda _:review(f,r).pk);self.assertEqual(out[0],out[1]);self.assertEqual(MigrationReadinessReview.objects.count(),1)
 def test_source_receipt_concurrent_first_capture_is_one_record(self):
  # Prepare supplied evidence without inserting its receipt, then race real capture services.
  f=self.f;p=f['plan']
  from django.utils import timezone
  payload={'plan_id':p.pk,'plan_sha256':p.sha256,**{k:p.payload[k] for k in ['build_ref','source_ref','target_ref','source_version','target_version']},'kind':'backup','system':'synthetic-migration','external_ref':'SAME-RECEIPT','receipt_version':'v1','recorded_at':timezone.now().isoformat(),'performed_by_ref':'synthetic-operator','outcome':'passed','evidence_class':'synthetic_report','record_count':1,'manifest_sha256':p.payload['expected_manifest_sha256']}
  e=evidence(f,'migration_proof',payload);out=self.parallel(lambda _:d.capture_proof(f['actor'],f['case'].pk,p.pk,e.pk).pk);self.assertEqual(out[0],out[1]);self.assertEqual(MigrationProof.objects.count(),1)
 def test_unknown_restore_commits_before_owner_review(self):
  f=self.f;r=assessed(f);self.race(lambda:proof(f,'restore',{'receipt_version':'v2','outcome':'unknown'}),lambda:review(f,r));self.assertFalse(MigrationReadinessReview.objects.exists())
 def test_independent_review_grant_revocation_precedes_decision(self):
  f=self.f;r=assessed(f);review(f,r);self.race(lambda:Grant.objects.filter(case=f['case'],user=f['acceptor'],action='migration.review').update(active=False),lambda:review(f,r,'independent'));self.assertEqual(MigrationReadinessReview.objects.count(),1)
 def test_af13_acceptance_grant_revocation_precedes_binding(self):
  f=self.f;r=assessed(f);review(f,r);review(f,r,'independent');self.race(lambda:Grant.objects.filter(case=f['case'],user=f['acceptor'],action='validation.accept').update(active=False),lambda:d.bind(f['acceptor'],f['case'].pk,r.pk));self.assertFalse(MigrationAF13Binding.objects.exists())
 def test_cross_case_source_identity_has_only_one_claim(self):
  f=self.f
  from apps.core.management.commands.seed_demo import ACTIONS
  from apps.core.services import add_evidence
  from django.utils import timezone
  from apps.documents.contracts import digest
  c=Case.objects.create(tenant=f['case'].tenant,title='Other isolated migration source',kind='project',synthetic=True)
  Grant.objects.bulk_create([Grant(case=c,user=f['actor'],action=x) for x in ACTIONS],ignore_conflicts=True)
  e=add_evidence(f['actor'],c.pk,'procedure_source','Isolated synthetic second source','synthetic:second');pe=add_evidence(f['actor'],c.pk,'migration_plan','Explicit synthetic second plan','synthetic:second')
  v=dict(f['plan'].payload,source_ref=str(c.pk),evidence_ids=[e.pk],expected_manifest_sha256=digest([{'id':e.pk,'kind':e.kind,'version':e.version,'sha256':e.sha256}]))
  p2=d.capture_plan(f['actor'],c.pk,'other-migration',v,pe.pk);plans=[f['plan'],p2];sources=[]
  for p in plans:
   payload={'plan_id':p.pk,'plan_sha256':p.sha256,**{k:p.payload[k] for k in ['build_ref','source_ref','target_ref','source_version','target_version']},'kind':'backup','system':'synthetic-migration','external_ref':'CROSS-CASE-RECEIPT','receipt_version':'v1','recorded_at':timezone.now().isoformat(),'performed_by_ref':'synthetic-operator','outcome':'passed','evidence_class':'synthetic_report','record_count':1,'manifest_sha256':p.payload['expected_manifest_sha256']}
   sources.append(add_evidence(f['actor'],p.case_id,'migration_proof',__import__('json').dumps(payload),'synthetic:claim'))
  def call(n):
   p=plans[n]
   try:return d.capture_proof(f['actor'],p.case_id,p.pk,sources[n].pk).pk
   except ValidationError:return 'held'
  out=self.parallel(call);self.assertEqual(out.count('held'),1);self.assertEqual(MigrationProof.objects.count(),1)
