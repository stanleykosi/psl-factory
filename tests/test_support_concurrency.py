from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.db import close_old_connections,transaction
from django.test import TransactionTestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.models import Case
from apps.identity.models import Grant
from apps.baas import support as d
from apps.baas.models import SupportIntake,SupportMerge
from .support_helpers import fixture,capture,ready,act,result,report,evidence
class SupportConcurrencyTests(TransactionTestCase):
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
 def test_same_case_duplicate_capture_has_one_receipt(self):
  f=self.f;e=evidence(f,'support_intake',f['v']['message']);ids=self.parallel(lambda _:d.capture(f['actor'],f['case'].pk,e.pk).pk);self.assertEqual(ids[0],ids[1]);self.assertEqual(SupportIntake.objects.count(),1)
 def test_cross_case_message_claim_is_unique_and_never_silently_merged(self):
  f=self.f;g=fixture('second');g['v']['message']=dict(f['v']['message']);es=[evidence(z,'support_intake',z['v']['message']) for z in [f,g]]
  def call(n):
   z=[f,g][n]
   try:return d.capture(z['actor'],z['case'].pk,es[n].pk).pk
   except ValidationError:return 'held'
  answers=self.parallel(call);self.assertEqual(answers.count('held'),1);self.assertEqual(SupportIntake.objects.count(),1);self.assertEqual(SupportMerge.objects.count(),0)
 def test_latest_unknown_specialist_result_commits_before_resolution(self):
  f=self.f;ready(f);act(f,'investigate');p=act(f,'await_specialist');result(f,p)
  self.race(lambda:result(f,p,'unknown'),lambda:d.transition(f['actor'],f['case'].pk,'resolve',f['actor'].pk,f['e']['support_transition'].pk,timezone.now().isoformat()))
  self.assertEqual(d.head(f['case']).state,'specialist_pending')
 def test_reviewer_revocation_commits_before_report_read(self):
  f=self.f;ready(f);r=report(f);self.race(lambda:Grant.objects.filter(case=f['case'],user=f['reviewer'],action='support.review').update(active=False),lambda:d.read_report(f['actor'],f['case'].pk,r.pk))
 def test_opposite_merges_use_ordered_case_locks_and_preserve_one_canonical_target(self):
  f=self.f;g=fixture('merge-other',people=[f['actor'],f['reviewer'],f['specialist']]);ready(f);ready(g)
  def call(n):
   source,target=[(f,g),(g,f)][n]
   try:return d.merge(source['actor'],source['case'].pk,target['case'].pk,source['e']['support_merge'].pk,timezone.now().isoformat()).pk
   except ValidationError:return 'held'
  answers=self.parallel(call);self.assertEqual(answers.count('held'),1);self.assertEqual(SupportMerge.objects.count(),1)
