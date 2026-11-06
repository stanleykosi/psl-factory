import os,sys,subprocess
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.test import TransactionTestCase,override_settings
from django.db import close_old_connections,connections,transaction
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.workflows import readiness as d,readiness_delivery as w
from apps.workflows.readiness_models import IntegrationContract,IntegrationProbe,IntegrationObservation
from adapters.readiness import ReadinessAdapter
from apps.policy.readiness_validators import ADAPTER
from .readiness_helpers import fixture,evidence,policy

@override_settings(READINESS_DATABASE_REVISION='fixture-v1')
class ReadinessConcurrencyTests(TransactionTestCase):
 def setUp(self):self.f=fixture()
 def parallel(self,fn):
  def call(n):
   close_old_connections()
   try:return fn(n)
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as p:return list(p.map(call,[0,1]))
 def test_first_contract_intents_have_one_version(self):
  f=self.f;e=evidence(f,'integration_contract');ids=self.parallel(lambda _:d.capture(f['actor'],f['case'].pk,'race',f['contract'].payload,e.pk).pk);self.assertEqual(ids[0],ids[1]);self.assertEqual(IntegrationContract.objects.filter(reference='race').count(),1)
 def test_competing_probe_reservations_and_workers_persist_one_observation(self):
  f=self.f;ids=self.parallel(lambda _:w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'race','health').pk);self.assertEqual(ids[0],ids[1]);self.parallel(lambda _:w.run_once());self.assertEqual(IntegrationObservation.objects.count(),1)
 def test_expired_fence_cannot_probe_or_complete_after_reclaim(self):
  f=self.f;j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'fence','health');pk,old=w.claim();IntegrationProbe.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1));pk,new=w.claim()
  with self.assertRaises(ValidationError):w.execute(pk,old,ReadinessAdapter())
  value=w.execute(pk,new,ReadinessAdapter());w.finish(pk,new,'confirmed',value);self.assertEqual(IntegrationObservation.objects.count(),1)
 def ordered(self,mutation):
  f=self.f;j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'ordered','health');pk,fence=w.claim();locked=Event();release=Event()
  def first():
   close_old_connections()
   try:
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
     if not release.wait(10):raise AssertionError('Coordination timeout')
     mutation()
   finally:close_old_connections()
  def second():
   close_old_connections()
   try:
    try:w.execute(pk,fence,ReadinessAdapter())
    except (ValidationError,PermissionDenied):return 'held'
    return 'probed'
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as p:
   a=p.submit(first);self.assertTrue(locked.wait(10));b=p.submit(second);release.set();a.result(timeout=30);self.assertEqual(b.result(timeout=30),'held')
  self.assertFalse(IntegrationObservation.objects.exists())
 def test_revocation_commits_before_probe(self):
  f=self.f;self.ordered(lambda:Grant.objects.filter(case=f['case'],user=f['actor'],action='integration.probe').update(active=False))
 def test_policy_replacement_commits_before_probe(self):
  f=self.f;self.ordered(lambda:policy(f,ADAPTER,dict(f['rules'],freshness_seconds=1000)))
 def test_separate_worker_recovers_committed_probe_after_revocation(self):
  f=self.f;j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'process','health');pk,fence=w.claim();w.execute(pk,fence,ReadinessAdapter());IntegrationProbe.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1));Grant.objects.filter(case=f['case'],user=f['actor'],action='integration.probe').update(active=False)
  env=os.environ.copy();env.update(PGDATABASE=connections['default'].settings_dict['NAME'],PYTHONIOENCODING='utf-8')
  result=subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),'work_integration_readiness','--limit','1'],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60);self.assertEqual(result.returncode,0,result.stderr);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(IntegrationObservation.objects.count(),1)
