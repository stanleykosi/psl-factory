import os,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import close_old_connections,connections,connection
from django.test import TransactionTestCase
from django.utils import timezone
from apps.finance import performance
from apps.finance.models import FinancePerformance
from apps.finance.documents import draft_report
from apps.documents.controlled import reserve_publication
from apps.documents.delivery import claim_publication,deliver_internal
from apps.documents.models import PublicationJob,PublicationReceipt
from apps.identity.models import Grant
from .finance_performance_helpers import fixture_performance,build
from .helpers import rev


class FinancePerformanceWorkerTests(TransactionTestCase):
    def test_two_connections_create_one_exact_comparison(self):
        data=fixture_performance();a,c=data[:2]
        def execute(_):
            close_old_connections()
            try:return performance.build(get_user_model().objects.get(pk=a.pk),c.pk,'2026-10',[data[8].pk],data[9].pk,[],None).pk
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(execute,range(2)))
        self.assertEqual(ids[0],ids[1]);self.assertEqual(FinancePerformance.objects.count(),1)

    def test_comparison_publication_reconciles_actual_receipt_in_fresh_process(self):
        data=fixture_performance();a,c,e=data[:3];report=build(data)
        performance.decide(a,c.pk,'performance',report.pk,'Finance','approve',e['finance_review'].pk,'Exact comparison reviewed',rev(c))
        version=draft_report(a,c.pk,report.pk,data[10].pk,'internal',rev(c),performance=True)
        reserve_publication(a,c.pk,version.pk,rev(c));job_id,fence=claim_publication();deliver_internal(job_id,fence)
        PublicationJob.objects.filter(pk=job_id).update(lease_until=timezone.now()-timedelta(seconds=1))
        # Reconcile the committed actual effect even if new delivery authority is subsequently revoked.
        Grant.objects.filter(case=c,user=a,action='finance.publish').update(active=False)
        env=dict(os.environ,PGDATABASE=connection.settings_dict['NAME'])
        result=subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),'work_publications','--limit','1'],env=env,cwd=settings.BASE_DIR,capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertIn('Processed 1 publication',result.stdout)
        self.assertEqual(PublicationJob.objects.get(pk=job_id).status,'confirmed');self.assertEqual(PublicationReceipt.objects.count(),1)
