import os,sys,subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.test import TransactionTestCase
from django.db import connections,close_old_connections
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.finance import forecast,forecast_documents
from apps.finance.models import ForecastMatch
from apps.documents.controlled import reserve_publication
from apps.documents.delivery import claim_publication,deliver_internal
from apps.documents.models import PublicationJob,PublicationReceipt
from apps.identity.models import Grant
from .forecast_helpers import fixture,run,actual,review,publication
from .billing_helpers import evidence
from .helpers import rev

class ForecastWorkerTests(TransactionTestCase):
    def setUp(self):self.a,self.c,self.m=fixture()
    def test_competing_actual_matches_cannot_overconsume_one_cash_transaction(self):
        r=run(self.a,self.c);a=actual(self.a,self.c);e=evidence(self.a,self.c,'forecast_match','Synthetic competing exact actual match')
        def work(key):
            close_old_connections()
            try:forecast.match(self.a,self.c.pk,r.scenario_id,'receipt-1',a.pk,'10',key,e.pk,None);return 'matched'
            except ValidationError:return 'held'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(work,['RACE-A','RACE-B']))
        self.assertCountEqual(out,['matched','held']);self.assertEqual(ForecastMatch.objects.count(),1)
    def test_competing_matches_cannot_overconsume_forecast_capacity(self):
        r=run(self.a,self.c);one=actual(self.a,self.c,'40',transaction='ONE');two=actual(self.a,self.c,'40',transaction='TWO');e=evidence(self.a,self.c,'forecast_match','Synthetic competing forecast capacity match')
        def work(actual_id):
            close_old_connections()
            try:forecast.match(self.a,self.c.pk,r.scenario_id,'receipt-1',actual_id,'40','KEY-'+str(actual_id),e.pk,None);return 'matched'
            except ValidationError:return 'held'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(work,[one.pk,two.pk]))
        self.assertCountEqual(out,['matched','held']);self.assertEqual(ForecastMatch.objects.count(),1)
    def test_separate_process_reconciles_publication_after_lost_lease_and_revocation(self):
        r=run(self.a,self.c);review(self.a,self.c,r);t,_=publication(self.a,self.c);v=forecast_documents.draft(self.a,self.c.pk,r.pk,t.pk,'internal',rev(self.c));p=reserve_publication(self.a,self.c.pk,v.pk,rev(self.c))
        pk,fence=claim_publication();deliver_internal(pk,fence);PublicationJob.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1));Grant.objects.filter(case=self.c,user=self.a,action='finance.publish').update(active=False)
        env=os.environ.copy();env['PGDATABASE']=connections['default'].settings_dict['NAME'];env['PYTHONIOENCODING']='utf-8'
        result=subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),'work_publications','--limit','1'],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(PublicationJob.objects.get(pk=pk).status,'confirmed');self.assertEqual(PublicationReceipt.objects.filter(publication=p).count(),1)
