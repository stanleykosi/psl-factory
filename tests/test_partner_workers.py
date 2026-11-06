import os,sys,subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.test import TransactionTestCase
from django.db import close_old_connections,connections
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.baas import partner_operations as domain,partner_delivery
from apps.baas.models import PartnerFinanceJob,PartnerFinanceReceipt,PartnerBillingImport,PartnerMeterClaim
from apps.identity.models import Grant
from adapters.partner_operations import InternalPartnerFinanceAdapter
from .partner_helpers import fixture,report,review,evidence,policy,capture,body
from .helpers import rev

class PartnerWorkerTests(TransactionTestCase):
    def setUp(self):self.a,self.c,self.fin,self.f,self.cov=fixture()
    def ready(self):
        r=report(self.a,self.c);review(self.fin,self.c,r);return domain.reserve(self.a,self.c.pk,r.pk,'PM',rev(self.c))
    def test_concurrent_reservations_return_one_job_and_receipt(self):
        r=report(self.a,self.c);review(self.fin,self.c,r)
        def work(_):
            close_old_connections()
            try:return domain.reserve(self.a,self.c.pk,r.pk,'PM',None).pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:jobs=list(pool.map(work,[1,2]))
        self.assertEqual(jobs[0],jobs[1]);partner_delivery.run_once();self.assertEqual(PartnerFinanceReceipt.objects.count(),1)
    def test_separate_worker_reconciles_actual_receipt_after_lost_lease_and_revocation(self):
        j=self.ready();pk,fence=partner_delivery.claim();partner_delivery.deliver_local(pk,fence);PartnerFinanceJob.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        Grant.objects.filter(case=self.c,user=self.a,action='partner.finance.dispatch').update(active=False)
        env=os.environ.copy();env['PGDATABASE']=connections['default'].settings_dict['NAME'];env['PYTHONIOENCODING']='utf-8'
        out=subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),'work_partner_finance','--limit','1'],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60)
        self.assertEqual(out.returncode,0,out.stderr);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(PartnerFinanceReceipt.objects.count(),1)
    def test_old_fence_cannot_deliver(self):
        j=self.ready();pk,old=partner_delivery.claim();PartnerFinanceJob.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1));pk,new=partner_delivery.claim()
        with self.assertRaisesMessage(ValidationError,'fence'):partner_delivery.deliver_local(pk,old)
        partner_delivery.deliver_local(pk,new);partner_delivery.finish(pk,new,'confirmed');self.assertEqual(PartnerFinanceReceipt.objects.count(),1)
    def test_timeout_after_receipt_reconciles_without_rechecking_withdrawn_review(self):
        class LostResponse(InternalPartnerFinanceAdapter):
            def deliver(self,pk,fence):super().deliver(pk,fence);raise TimeoutError
        j=self.ready();partner_delivery.run_once(LostResponse());j.refresh_from_db();self.assertEqual(j.status,'unknown')
        Grant.objects.filter(case=self.c,user=self.fin,action='partner.report.review').update(active=False);partner_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(PartnerFinanceReceipt.objects.count(),1)
    def test_unknown_before_receipt_cannot_be_cancelled(self):
        class BeforeAcceptance(InternalPartnerFinanceAdapter):
            def deliver(self,pk,fence):raise ConnectionError
        j=self.ready();partner_delivery.run_once(BeforeAcceptance())
        with self.assertRaisesMessage(ValidationError,'Unknown'):partner_delivery.operate(self.a,self.c.pk,j.pk,'cancel','Unknown request must reconcile first',rev(self.c))
        partner_delivery.run_once();self.assertEqual(PartnerFinanceReceipt.objects.count(),1)
    def test_changed_policy_requires_explicit_new_intent_generation(self):
        class Held(InternalPartnerFinanceAdapter):
            def deliver(self,pk,fence):raise ValidationError('Synthetic target hold')
        j=self.ready();partner_delivery.run_once(Held());r=j.report;from apps.policy.partner_validators import ACTIVITY
        policy(self.a,self.c,ACTIVITY,dict(self.f['activity'],max_attempts=4))
        # New policy means a new immutable report and human review; old report cannot be repurposed.
        with self.assertRaises(ValidationError):partner_delivery.operate(self.a,self.c.pk,j.pk,'replace_intent','Reconcile changed policy',rev(self.c))
        new=domain.build_report(self.a,self.c.pk,r.record_id,rev(self.c));review(self.fin,self.c,new);domain.reserve(self.a,self.c.pk,new.pk,'PM',rev(self.c));partner_delivery.run_once();self.assertEqual(PartnerFinanceReceipt.objects.count(),1)
    def test_competing_finance_acceptances_consume_each_event_only_once(self):
        j=self.ready();partner_delivery.run_once();receipt=PartnerFinanceReceipt.objects.get();e=evidence(self.fin,self.c,'partner_decision','Exact meter acceptance')
        def work(_):
            close_old_connections()
            try:return domain.import_finance_usage(self.fin,self.c.pk,receipt.pk,'Finance',e.pk,None).pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(work,[1,2]))
        self.assertEqual(results[0],results[1]);self.assertEqual(PartnerBillingImport.objects.count(),1);self.assertEqual(PartnerMeterClaim.objects.count(),3)
    def test_explicit_replacement_after_renewed_same_report_review_preserves_old_intent(self):
        class Held(InternalPartnerFinanceAdapter):
            def deliver(self,pk,fence):raise ValidationError('Synthetic target hold')
        j=self.ready();partner_delivery.run_once(Held());review(self.fin,self.c,j.report)
        with self.assertRaisesMessage(ValidationError,'Intent changed'):partner_delivery.operate(self.a,self.c.pk,j.pk,'retry','New exact review',rev(self.c))
        partner_delivery.operate(self.a,self.c.pk,j.pk,'replace_intent','Explicit refreshed human review',rev(self.c));j.refresh_from_db();self.assertEqual(j.status,'replaced');partner_delivery.run_once();self.assertEqual(PartnerFinanceReceipt.objects.count(),1)
    def test_cross_case_tenant_meter_race_accepts_only_one_source_event_set(self):
        from apps.core.models import Case
        from apps.policy.services import register_reference
        from apps.policy.partner_validators import ACTIVITY,METER
        from apps.finance import billing
        from .helpers import activate
        from .partner_helpers import delivered
        other=Case.objects.create(tenant=self.c.tenant,title='Other partner case',kind='support',synthetic=True)
        for g in Grant.objects.filter(case=self.c):Grant.objects.create(case=other,user_id=g.user_id,action=g.action)
        e=evidence(self.a,other,'policy_decision','Synthetic second-case authority')
        refs=[register_reference(self.a,other.pk,'role:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':person.pk},e.pk).ref for role,person in [('PM',self.a),('Finance',self.fin)]];activate(self.a,other,'D05.role_principal_assignments',refs,e)
        coverage=evidence(self.a,other,'billing_coverage','Exact synthetic second coverage');cov=billing.register_coverage(self.a,other.pk,'coverage','customer-1','payments','contract-1','NGN','net_exclusive',self.cov.from_period,self.cov.to_period,'complete',coverage.pk,rev(other))
        policy(self.a,other,ACTIVITY,self.f['activity']);policy(self.a,other,METER,dict(self.f['meter'],coverage_id=cov.pk))
        one=delivered(self.a,self.c,self.fin,report(self.a,self.c));two=delivered(self.a,other,self.fin,report(self.a,other));proofs=[evidence(self.fin,c,'partner_decision','Exact synthetic meter acceptance') for c in [self.c,other]]
        def work(args):
            case,receipt,proof=args;close_old_connections()
            try:domain.import_finance_usage(self.fin,case.pk,receipt.pk,'Finance',proof.pk,None);return 'accepted'
            except ValidationError as exc:
                self.assertIn('already handed to Finance',str(exc));return 'held'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(work,[(self.c,one,proofs[0]),(other,two,proofs[1])]))
        self.assertCountEqual(out,['accepted','held']);self.assertEqual(PartnerBillingImport.objects.count(),1);self.assertEqual(PartnerMeterClaim.objects.count(),3)
