import os,sys,subprocess,copy
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.test import TransactionTestCase
from django.db import close_old_connections,connections
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.baas import corrective,corrective_delivery
from apps.baas.models import CorrectiveJob,CorrectiveDelivery
from apps.identity.models import Grant
from .reconciliation_helpers import fixture,run,request,decide,evidence,policy,batch
from .helpers import rev

class ReconciliationWorkerTests(TransactionTestCase):
    def setUp(self):self.a,self.c,self.engineer,self.f,self.b=fixture()
    def test_competing_reservations_accept_only_one_transaction_command(self):
        r=run(self.a,self.c,self.b);one=request(self.a,self.c,r,reference='ONE',operation='ONE');two=request(self.a,self.c,r,reference='TWO',operation='TWO');decide(self.a,self.c,one);decide(self.a,self.c,two)
        def work(pk):
            close_old_connections()
            try:corrective.reserve(self.a,self.c.pk,pk,'Finance',None);return 'reserved'
            except ValidationError:return 'held'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(work,[one.pk,two.pk]))
        self.assertCountEqual(out,['reserved','held']);corrective_delivery.run_once();self.assertEqual(CorrectiveDelivery.objects.count(),1)
    def test_separate_worker_reconciles_lost_lease_after_approval_revocation(self):
        r=run(self.a,self.c,self.b);q=request(self.a,self.c,r);decide(self.a,self.c,q);j=corrective.reserve(self.a,self.c.pk,q.pk,'Finance',rev(self.c));pk,fence=corrective_delivery.claim();corrective_delivery.deliver_local(pk,fence)
        CorrectiveJob.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1));Grant.objects.filter(case=self.c,user=self.a,action='baas.corrective.decide').update(active=False)
        env=os.environ.copy();env['PGDATABASE']=connections['default'].settings_dict['NAME'];env['PYTHONIOENCODING']='utf-8'
        p=subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),'work_corrective_requests','--limit','1'],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60)
        self.assertEqual(p.returncode,0,p.stderr);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(CorrectiveDelivery.objects.count(),1)
    def test_old_fence_cannot_deliver_after_reclaim(self):
        r=run(self.a,self.c,self.b);q=request(self.a,self.c,r);decide(self.a,self.c,q);j=corrective.reserve(self.a,self.c.pk,q.pk,'Finance',rev(self.c));pk,old=corrective_delivery.claim();CorrectiveJob.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1));pk,new=corrective_delivery.claim()
        with self.assertRaisesMessage(ValidationError,'fence'):corrective_delivery.deliver_local(pk,old)
        corrective_delivery.deliver_local(pk,new);corrective_delivery.finish(pk,new,'confirmed');self.assertEqual(CorrectiveDelivery.objects.count(),1)
    def test_timeout_after_receipt_reconciles_once_even_after_sender_revocation(self):
        from adapters.reconciliation import InternalEngineeringAdapter
        class LostResponse(InternalEngineeringAdapter):
            def deliver(self,pk,fence):super().deliver(pk,fence);raise TimeoutError
        r=run(self.a,self.c,self.b);q=request(self.a,self.c,r);decide(self.a,self.c,q);j=corrective.reserve(self.a,self.c.pk,q.pk,'Finance',rev(self.c));corrective_delivery.run_once(LostResponse());j.refresh_from_db();self.assertEqual(j.status,'unknown')
        Grant.objects.filter(case=self.c,user=self.a,action='baas.corrective.dispatch').update(active=False);corrective_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(CorrectiveDelivery.objects.count(),1)
    def test_unknown_before_acceptance_holds_competitor_and_operator_cancellation(self):
        from adapters.reconciliation import InternalEngineeringAdapter
        class BeforeAcceptance(InternalEngineeringAdapter):
            def deliver(self,pk,fence):raise ConnectionError
        r=run(self.a,self.c,self.b);q=request(self.a,self.c,r);decide(self.a,self.c,q);j=corrective.reserve(self.a,self.c.pk,q.pk,'Finance',rev(self.c));corrective_delivery.run_once(BeforeAcceptance())
        other=request(self.a,self.c,r,reference='OTHER',operation='OTHER');decide(self.a,self.c,other)
        with self.assertRaises(ValidationError):corrective.reserve(self.a,self.c.pk,other.pk,'Finance',rev(self.c))
        with self.assertRaisesMessage(ValidationError,'Unknown'):corrective_delivery.operate(self.a,self.c.pk,j.pk,'cancel','Cannot cancel uncertainty',rev(self.c))
        corrective_delivery.run_once();self.assertEqual(CorrectiveDelivery.objects.count(),1)
    def test_cross_case_tenant_race_is_constrained_without_disclosing_other_records(self):
        from apps.core.models import Case
        from apps.policy.services import register_reference
        from .helpers import activate
        other=Case.objects.create(tenant=self.c.tenant,title='Other support case',kind='support',synthetic=True)
        for old in Grant.objects.filter(case=self.c):Grant.objects.create(case=other,user_id=old.user_id,action=old.action)
        owner=evidence(self.a,other,'policy_decision','Synthetic second case role scope')
        refs=[register_reference(self.a,other.pk,'role:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':person.pk},owner.pk).ref for role,person in [('Finance',self.a),('Engineering',self.engineer)]]
        activate(self.a,other,'D05.role_principal_assignments',refs,owner);policy(self.a,other,'D09.reconciliation_contract_ref',self.f['contract']);policy(self.a,other,'D09.queue_state_command_map',self.f['commands'])
        sources={kind:batch(self.a,other,kind) for kind in ['ledger','settlement','queue']};one=request(self.a,self.c,run(self.a,self.c,self.b),operation='CASE-ONE');two=request(self.a,other,run(self.a,other,sources),operation='CASE-TWO');decide(self.a,self.c,one);decide(self.a,other,two)
        def work(pair):
            case,subject=pair;close_old_connections()
            try:corrective.reserve(self.a,case.pk,subject.pk,'Finance',None);return 'reserved'
            except ValidationError:return 'held'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(work,[(self.c,one),(other,two)]))
        self.assertCountEqual(out,['reserved','held']);self.assertEqual(CorrectiveJob.objects.count(),1)
    def test_held_policy_change_requires_explicit_new_intent_and_preserves_old_job(self):
        from adapters.reconciliation import InternalEngineeringAdapter
        class HeldTarget(InternalEngineeringAdapter):
            def deliver(self,pk,fence):raise ValidationError('Synthetic target hold')
        r=run(self.a,self.c,self.b);q=request(self.a,self.c,r);decide(self.a,self.c,q);j=corrective.reserve(self.a,self.c.pk,q.pk,'Finance',rev(self.c));corrective_delivery.run_once(HeldTarget())
        policy(self.a,self.c,'D09.queue_state_command_map',dict(self.f['commands'],max_attempts=4));decide(self.a,self.c,q)
        with self.assertRaisesMessage(ValidationError,'Intent changed'):corrective_delivery.operate(self.a,self.c.pk,j.pk,'retry','Renewed exact approval',rev(self.c))
        corrective_delivery.operate(self.a,self.c.pk,j.pk,'replace_intent','Explicit changed policy recovery',rev(self.c));j.refresh_from_db();self.assertEqual(j.status,'replaced');self.assertEqual(CorrectiveJob.objects.count(),2)
        corrective_delivery.run_once();self.assertEqual(CorrectiveDelivery.objects.count(),1)
