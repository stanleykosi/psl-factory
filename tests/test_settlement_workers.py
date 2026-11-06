import os,sys,subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.test import TransactionTestCase
from django.db import close_old_connections,connections
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.identity.models import Grant
from apps.finance import cash,invoices,invoice_delivery
from apps.finance.models import InvoiceJob,InvoiceIssue,CashAllocation,CashReversal
from .helpers import rev
from .settlement_helpers import fixture,draft,approve,issue,receipt,assign

class SettlementWorkerTests(TransactionTestCase):
    def setUp(self):self.a,self.c,self.cov,self.p,self.e=fixture()
    def test_competing_allocations_share_both_capacities(self):
        iss=issue(self.a,self.c,draft(self.a,self.c,self.p),self.e);r,l=receipt(self.a,self.c,'30.00');assign(self.a,self.c,r,self.cov,self.e)
        def work(n):
            close_old_connections()
            try:
                cash.allocate(self.a,self.c.pk,l.pk,iss.pk,'20.00','parallel-'+str(n),'Finance',self.e['cash_allocation'].pk,None);return 'allocated'
            except ValidationError:return 'capacity-held'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(work,range(2)))
        self.assertCountEqual(outcomes,['allocated','capacity-held']);self.assertEqual(CashAllocation.objects.count(),1)
        self.assertEqual(cash.cash_remaining(l),Decimal('10.00'));self.assertEqual(cash.open_amount(iss),Decimal('12.25'))
    def test_competing_full_reversals_remove_cash_only_once(self):
        r,l=receipt(self.a,self.c)
        def work(n):
            close_old_connections()
            try:
                cash.reverse(self.a,self.c.pk,'lot',l.pk,'Finance',self.e['cash_correction'].pk,'Parallel full reversal',None);return 'reversed'
            except ValidationError:return 'already-reversed'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(work,range(2)))
        self.assertCountEqual(outcomes,['reversed','already-reversed']);self.assertEqual(CashReversal.objects.count(),1)
    def test_separate_os_worker_reconciles_accepted_invoice_after_lost_lease_and_revocation(self):
        i=draft(self.a,self.c,self.p);approve(self.a,self.c,i,self.e);j=invoices.reserve(self.a,self.c.pk,i.pk,'issue','Finance',rev(self.c))
        pk,fence=invoice_delivery.claim();invoice_delivery.deliver_local(pk,fence)
        InvoiceJob.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        Grant.objects.filter(case=self.c,user=self.a,action='finance.invoice.issue').update(active=False)
        env=os.environ.copy();env['PGDATABASE']=connections['default'].settings_dict['NAME'];env['PYTHONIOENCODING']='utf-8'
        result=subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),'work_invoices','--limit','1'],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('Processed 1',result.stdout)
        j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(InvoiceIssue.objects.count(),1)
    def test_old_fence_cannot_deliver_after_reclaim(self):
        i=draft(self.a,self.c,self.p);approve(self.a,self.c,i,self.e);j=invoices.reserve(self.a,self.c.pk,i.pk,'issue','Finance',rev(self.c))
        pk,fence=invoice_delivery.claim();InvoiceJob.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        pk2,fence2=invoice_delivery.claim();self.assertGreater(fence2,fence)
        with self.assertRaises(ValidationError):invoice_delivery.deliver_local(pk,fence)
        invoice_delivery.deliver_local(pk2,fence2);invoice_delivery.finish(pk2,fence2,'confirmed');self.assertEqual(InvoiceIssue.objects.count(),1)

    def test_cross_case_concurrent_report_reserves_one_tenant_transaction(self):
        import json
        from apps.core.models import Case
        from apps.core.services import add_evidence
        from apps.finance.models import CashReceipt
        other=Case.objects.create(tenant=self.c.tenant,title='Other Finance case',kind='project',synthetic=True)
        for action in ['evidence.add','finance.cash.record']:Grant.objects.create(case=other,user=self.a,action=action)
        value={'source':'synthetic-bank','transaction_ref':'cross-case-race','customer':self.cov.customer,'amount':'50','currency':'NGN','amount_basis':'gross_including_tax','received_at':timezone.now().isoformat()}
        first=add_evidence(self.a,self.c.pk,'cash_report',json.dumps(value),'synthetic:cash');second=add_evidence(self.a,other.pk,'cash_report',json.dumps(value),'synthetic:cash')
        def work(pair):
            close_old_connections()
            try:cash.report(self.a,pair[0],pair[1],None);return 'recorded'
            except ValidationError:return 'duplicate-held'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(work,[(self.c.pk,first.pk),(other.pk,second.pk)]))
        self.assertCountEqual(outcomes,['recorded','duplicate-held']);self.assertEqual(CashReceipt.objects.count(),1)
