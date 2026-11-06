import os,sys,subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.conf import settings
from django.test import TransactionTestCase
from django.db import close_old_connections,connections
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.identity.models import Grant
from apps.finance import corrections,financial_reviews,invoice_delivery,cash,cash_successors
from apps.finance.models import InvoiceJob,InvoiceCorrectionAcceptance,CashSuccessorAcceptance,CashVerification
from .helpers import rev
from .correction_helpers import fixture,note,review,successor
from .settlement_helpers import receipt

class FinancialCorrectionWorkerTests(TransactionTestCase):
    def setUp(self):self.a,self.c,self.cov,self.iss,self.e=fixture()
    def test_competing_note_reservations_do_not_accept_two_changes_on_one_snapshot(self):
        one=note(self.a,self.c,self.iss,self.e,reference='RACE-1');two=note(self.a,self.c,self.iss,self.e,reference='RACE-2')
        review(self.a,self.c,one,self.e);review(self.a,self.c,two,self.e)
        def work(pk):
            close_old_connections()
            try:corrections.reserve(self.a,self.c.pk,pk,'adjust','Finance',None);return 'reserved'
            except ValidationError:return 'held'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(work,[one.pk,two.pk]))
        self.assertCountEqual(outcomes,['reserved','held']);invoice_delivery.run_once();self.assertEqual(InvoiceCorrectionAcceptance.objects.count(),1)
    def test_competing_successor_branches_accept_only_one_new_cash_lot(self):
        r,l=receipt(self.a,self.c);cash.reverse(self.a,self.c.pk,'lot',l.pk,'Finance',self.e['cash_correction'].pk,'Full parent reversal',rev(self.c))
        one=successor(self.a,self.c,l,self.e,'40');two=successor(self.a,self.c,l,self.e,'45');review(self.a,self.c,one,self.e,'cash');review(self.a,self.c,two,self.e,'cash')
        def work(pk):
            close_old_connections()
            try:cash_successors.apply(self.a,self.c.pk,pk,'Finance',None);return 'accepted'
            except ValidationError:return 'held'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(work,[one.pk,two.pk]))
        self.assertCountEqual(outcomes,['accepted','held']);self.assertEqual(CashSuccessorAcceptance.objects.count(),1);self.assertEqual(CashVerification.objects.count(),2)
    def test_separate_os_worker_reconciles_correction_after_lost_lease_and_revocation(self):
        n=note(self.a,self.c,self.iss,self.e);review(self.a,self.c,n,self.e);j=corrections.reserve(self.a,self.c.pk,n.pk,'adjust','Finance',rev(self.c))
        pk,fence=invoice_delivery.claim();invoice_delivery.deliver_local(pk,fence);InvoiceJob.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        Grant.objects.filter(case=self.c,user=self.a,action='finance.invoice.correct').update(active=False)
        env=os.environ.copy();env['PGDATABASE']=connections['default'].settings_dict['NAME'];env['PYTHONIOENCODING']='utf-8'
        result=subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),'work_invoices','--limit','1'],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(InvoiceCorrectionAcceptance.objects.count(),1)
    def test_older_correction_fence_cannot_dispatch_after_reclaim(self):
        n=note(self.a,self.c,self.iss,self.e);review(self.a,self.c,n,self.e);j=corrections.reserve(self.a,self.c.pk,n.pk,'adjust','Finance',rev(self.c))
        pk,old=invoice_delivery.claim();InvoiceJob.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1));pk,new=invoice_delivery.claim()
        with self.assertRaises(ValidationError):invoice_delivery.deliver_local(pk,old)
        invoice_delivery.deliver_local(pk,new);invoice_delivery.finish(pk,new,'confirmed');self.assertEqual(InvoiceCorrectionAcceptance.objects.count(),1)
