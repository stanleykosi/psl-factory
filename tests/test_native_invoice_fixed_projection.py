"""Native fixed-contract contrast for supplied-source invoice receipt projection."""
import hashlib
import tempfile
from django.test import TransactionTestCase
from django.db import connection
from apps.finance.models import InvoiceJob
from apps.workflows import factory
from adapters.factory_invoices import MockFactoryInvoiceAdapter
from adapters import native_invoice_receipts as adapter, native_application_archive as source
from tests.test_factory_invoice_intake import FactoryFixedPreparationTests, start
from tests.obligation_helpers import factory_approve_identified


class FixedSourceProjectionTests(TransactionTestCase):
    def test_source_fixed_contract_delivery_preserves_exact_period(self):
        helper, request, charge, preparation, proof = FactoryFixedPreparationTests().fixed()
        work = start(dict(actor=helper.b,case=helper.c,prep=preparation,proof=proof),reference='SOURCE-FIXED')
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertIsNotNone(work.invoice_id,work.finding)
        factory_approve_identified(dict(actor=helper.a,case=helper.c,proof=proof,work=work,binding_actor=helper.b))
        with tempfile.TemporaryDirectory() as directory:
            factory.run_until_wait(work.pk,adapter=MockFactoryInvoiceAdapter(directory))
        work.refresh_from_db()
        self.assertEqual(work.status,'verified',work.finding)
        job=InvoiceJob.objects.get(invoice_id=work.invoice_id,kind='deliver')
        with source.connect(connection.settings_dict['NAME']) as db:
            row_sha=db.execute("SELECT encode(sha256(convert_to(to_jsonb(j)::text,'UTF8')),'hex') FROM finance_invoicejob j WHERE id=%s",[job.pk]).fetchone()[0]
            effect=dict(job_id=job.pk,case_id=str(helper.c.pk),effect_key='f'*64,intent_sha256=row_sha,
                        operation_sha256=hashlib.sha256(job.operation_key.encode()).hexdigest())
            metadata,operation,payload=adapter.original(db,effect,1048576)
            observed=adapter.receipt(db,metadata,payload)
        self.assertEqual(work.invoice.preparation.kind,'fixed_contract')
        self.assertEqual(payload['contract_period'],work.invoice.payload['contract_period'])
        self.assertEqual(payload['projection'],'finance-invoice-public/v1')
        self.assertEqual(metadata['variant'],'deliver')
        self.assertEqual(observed[0],'present')
