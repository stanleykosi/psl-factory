from concurrent.futures import ThreadPoolExecutor
from django.test import TransactionTestCase
from django.db import close_old_connections
from django.core.exceptions import ValidationError
from apps.finance.models import BillingPreparation,BillingUsage
from apps.finance import billing
from .helpers import setup_case
from .billing_helpers import coverage,usage,prices,evidence,FIXTURE
import json

class BillingConcurrencyTests(TransactionTestCase):
    def setUp(self):self.a,self.c=setup_case();self.cov=coverage(self.a,self.c)
    def test_competing_preparations_return_one_semantic_record(self):
        prices(self.a,self.c,self.cov);u=usage(self.a,self.c,self.cov)
        def work(_):
            close_old_connections()
            try:return billing.prepare(self.a,self.c.pk,self.cov.pk,'usage',u.pk,None,None).pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(work,range(2)))
        self.assertEqual(ids[0],ids[1]);self.assertEqual(BillingPreparation.objects.count(),1)
    def test_competing_usage_capture_cannot_duplicate_same_content(self):
        body=json.loads(FIXTURE.read_text(encoding='utf-8'))['csv'];e=evidence(self.a,self.c,'billing_usage',body)
        def work(_):
            close_old_connections()
            try:
                billing.capture_usage(self.a,self.c.pk,self.cov.pk,e.pk,None);return 'captured'
            except ValidationError:return 'duplicate'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(work,range(2)))
        self.assertCountEqual(outcomes,['captured','duplicate']);self.assertEqual(BillingUsage.objects.count(),1)
