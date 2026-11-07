"""Native transaction boundary for independently durable synthetic invoice effects."""
import tempfile
from pathlib import Path
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import connection,transaction
from django.test import TransactionTestCase
from adapters.factory_invoices import MockFactoryInvoiceAdapter
from adapters.invoices import InternalInvoiceAdapter
from apps.finance import invoices,invoice_delivery
from apps.finance.models import InvoiceIssue,ObligationEffect
from .settlement_helpers import fixture,draft
from .obligation_helpers import approve_identified
from .helpers import rev

class InvoiceTransactionTests(TransactionTestCase):
    def setUp(self):
        self.a,self.c,self.cov,self.p,self.e=fixture()
        self.invoice=draft(self.a,self.c,self.p)
        approve_identified(self.a,self.c,self.invoice,self.e)
        self.job=invoices.reserve(self.a,self.c.pk,self.invoice.pk,'issue','Finance',rev(self.c))
        self.directory=tempfile.TemporaryDirectory(prefix='psl-invoice784-')
        self.addCleanup(self.directory.cleanup)
        self.adapter=MockFactoryInvoiceAdapter(self.directory.name)

    def state(self):
        self.job.refresh_from_db()
        return (self.job.status,self.job.fence,self.job.attempts,self.job.lease_until,
            InvoiceIssue.objects.count(),ObligationEffect.objects.count())

    def assert_rejected(self):
        with patch.object(invoice_delivery,'claim') as claim,patch.object(self.adapter,'lookup') as lookup,patch.object(self.adapter,'deliver') as deliver:
            with self.assertRaisesRegex(ValidationError,'outer autocommit boundary'):
                invoice_delivery.run_once(self.adapter,case_id=self.c.pk,job_id=self.job.pk)
            claim.assert_not_called();lookup.assert_not_called();deliver.assert_not_called()

    def test_outer_atomic_rejects_before_claim_or_independent_effect(self):
        before=self.state()
        with transaction.atomic():self.assert_rejected()
        self.assertEqual(self.state(),before)
        self.assertEqual(list(Path(self.directory.name).iterdir()),[])

    def test_autocommit_off_rejects_before_claim_or_independent_effect(self):
        before=self.state()
        connection.set_autocommit(False)
        try:self.assert_rejected()
        finally:connection.rollback();connection.set_autocommit(True)
        self.assertEqual(self.state(),before)
        self.assertEqual(list(Path(self.directory.name).iterdir()),[])

    def test_exact_internal_effect_rolls_back_with_owning_transaction(self):
        before=self.state()
        with transaction.atomic():
            self.assertTrue(invoice_delivery.run_once(InternalInvoiceAdapter(),case_id=self.c.pk,job_id=self.job.pk))
            self.assertEqual(InvoiceIssue.objects.count(),before[4]+1)
            transaction.set_rollback(True)
        self.assertEqual(self.state(),before)
        self.assertEqual(list(Path(self.directory.name).iterdir()),[])

    def test_autocommit_dispatch_and_lost_response_reconcile_original(self):
        self.adapter.lose_response=True
        self.assertTrue(invoice_delivery.run_once(self.adapter,case_id=self.c.pk,job_id=self.job.pk))
        self.job.refresh_from_db();self.assertEqual(self.job.status,'unknown')
        self.assertEqual(InvoiceIssue.objects.count(),0)
        files=list(Path(self.directory.name).glob('*.json'));self.assertEqual(len(files),1)
        original=files[0].read_bytes()
        self.assertTrue(invoice_delivery.run_once(MockFactoryInvoiceAdapter(self.directory.name),case_id=self.c.pk,job_id=self.job.pk,lookup_only=True))
        self.job.refresh_from_db();self.assertEqual(self.job.status,'confirmed')
        self.assertEqual(InvoiceIssue.objects.count(),1)
        self.assertEqual(list(Path(self.directory.name).glob('*.json')),files)
        self.assertEqual(files[0].read_bytes(),original)
