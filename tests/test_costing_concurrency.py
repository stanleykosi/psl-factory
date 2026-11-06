import os,sys,subprocess,json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier,Event
from django.test import TransactionTestCase
from django.db import close_old_connections,connections,transaction
from django.conf import settings
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.pmo import costing as d
from apps.pmo.costing_models import CostingRule,CostingRun,CostingReview,CostingBinding
from .costing_helpers import fixture,run,evidence,review

class CostingConcurrencyTests(TransactionTestCase):
    def setUp(self):self.f=fixture()
    def parallel(self,call):
        barrier=Barrier(2)
        def task(n):
            close_old_connections()
            try:barrier.wait(timeout=10);return call(n)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(task,[0,1]))
    def race(self,mutation,action):
        held=Event();commit=Event();f=self.f
        def first():
            close_old_connections()
            try:
                with transaction.atomic():
                    Case.objects.select_for_update().get(pk=f['case'].pk);held.set()
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
            a=pool.submit(first);self.assertTrue(held.wait(10));b=pool.submit(second);commit.set();a.result(timeout=30);self.assertEqual(b.result(timeout=30),'held')
    def test_simultaneous_first_calculation_and_binding_are_unique(self):
        f=self.f;ids=self.parallel(lambda _:run(f).pk);self.assertEqual(ids[0],ids[1]);self.assertEqual(CostingRun.objects.count(),1)
        ids=self.parallel(lambda _:d.bind(f['actor'],f['case'].pk,ids[0]).pk);self.assertEqual(ids[0],ids[1]);self.assertEqual(CostingBinding.objects.count(),1)
    def test_simultaneous_first_source_capture_is_one_version(self):
        f=self.f;v=dict(f['rule'].payload,calculator_version='v2');e=evidence(f,'p14_rule',v)
        ids=self.parallel(lambda _:d.capture_rule(f['actor'],f['case'].pk,'new-source',e.pk).pk);self.assertEqual(ids[0],ids[1]);self.assertEqual(CostingRule.objects.filter(reference='new-source').count(),1)
    def test_simultaneous_review_intent_is_one_receipt(self):
        f=self.f;ids=self.parallel(lambda _:review(f,f['oracle'],key='concurrent-review').pk);self.assertEqual(ids[0],ids[1]);self.assertEqual(CostingReview.objects.filter(operation_key='concurrent-review').count(),1)
    def test_oracle_source_revocation_commits_before_calculation(self):
        f=self.f;self.race(lambda:Grant.objects.filter(case=f['case'],user=f['tester'],action='costing.source.read').update(active=False),lambda:run(f));self.assertFalse(CostingRun.objects.exists())
    def test_oracle_withdrawal_commits_before_binding(self):
        f=self.f;r=run(f);self.race(lambda:review(f,f['oracle'],verdict='withdraw',key='concurrent-withdraw'),lambda:d.bind(f['actor'],f['case'].pk,r.pk));self.assertFalse(CostingBinding.objects.exists())
    def test_separate_process_reconciles_persisted_calculation_after_restart(self):
        f=self.f;s=f['sources'];env=os.environ.copy();env['PGDATABASE']=connections['default'].settings_dict['NAME'];env['PYTHONIOENCODING']='utf-8'
        cmd=[sys.executable,str(settings.BASE_DIR/'manage.py'),'run_costing','--case',str(f['case'].pk),'--actor',str(f['actor'].pk),'--plan',str(s['plan'].pk),'--engineering',str(s['engineering_estimate'].pk),'--security',str(s['security_estimate'].pk),'--inputs',str(f['inputs'].pk),'--key','process-recovery']
        for _ in range(2):
            result=subprocess.run(cmd,cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60);self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(CostingRun.objects.count(),1);self.assertEqual(CostingRun.objects.get().result['values'][0]['value'],'20.00')
