"""Literal synthetic F29/F32 examples and bounded F28 same-receipt retry proof.

No owner rate, tax, provider authenticity, collection policy or full process
acceptance is implied. F28 does not assert the separate C1/C2 September/control
population or two distinct intake receipt records from the catalogue.
"""
import copy
import json
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from adapters.invoices import TimeoutAfterInvoiceAccept
from apps.finance import billing, cash, invoice_delivery, invoices, receivables
from apps.finance.models import (
    BillingPreparation, BillingUsage, CashAllocation, CashReceipt,
    CashReversal, CashVerification, Invoice, InvoiceDelivery, InvoiceIssue,
    InvoiceJob, InvoiceReview,
)
from apps.policy.services import reference_values
from .billing_helpers import FIXTURE, coverage, evidence, policy, prepare, usage
from .helpers import rev, setup_case
from .settlement_helpers import allocate, approve, assign, configured, draft, receipt


def explicit_price(actor, case, cov, quantity, rate, total, *, unit='request'):
    """Fixture-approved zero tax and rounding, never implicit default policy."""
    source = json.loads(FIXTURE.read_text(encoding='utf-8'))
    rule = dict(source['rule'], coverage_id=cov.pk, key='catalogue-rate-v1',
                from_period=cov.from_period, to_period=cov.to_period,
                unit=unit, rate=rate, currency=cov.currency,
                amount_basis=cov.amount_basis)
    arithmetic = {
        'implementation': 'net_exclusive_line_tax_v1', 'tax_rate': '0',
        'decimal_places': 2, 'rounding': 'half_up',
        'oracles': [{'quantity': quantity, 'rate': rate, 'net': total,
                     'tax': '0.00', 'total': total},
                    {'quantity': None, 'rate': rate, 'net': None,
                     'tax': None, 'total': None},
                    {'quantity': '0', 'rate': rate, 'net': '0.00',
                     'tax': '0.00', 'total': '0.00'}],
    }
    oracle = evidence(actor, case, 'billing_oracle', json.dumps(arithmetic['oracles']))
    arithmetic['oracle_evidence_id'] = oracle.pk
    configs = [policy(actor, case, 'D08.effective_price_rule_refs', [rule]),
               policy(actor, case, 'D08.tax_tier_rounding_rules', arithmetic)]
    return configs, oracle


class BillingExactCatalogueTests(TestCase):
    def priced_usage(self, quantity='10', rate='2', total='20.00'):
        actor, case = setup_case()
        cov = coverage(actor, case)
        configs, oracle = explicit_price(actor, case, cov, quantity, rate, total)
        body = json.loads(FIXTURE.read_text(encoding='utf-8'))['csv']
        body = body.replace(',12\n', ',' + quantity + '\n')
        batch = usage(actor, case, cov, body)
        prep = prepare(actor, case, cov, u=batch)
        return actor, case, cov, configs, oracle, batch, prep

    def assert_sql_immutable(self, model, pk, column, replacement):
        self.assertEqual(connection.vendor, 'postgresql')
        table = connection.ops.quote_name(model._meta.db_table)
        field = connection.ops.quote_name(column)
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f'UPDATE {table} SET {field}=%s WHERE id=%s',
                               [replacement, pk])

    def test_f28_same_usage_receipt_retry_creates_no_second_imported_batch(self):
        from apps.baas import partner_operations as domain
        from apps.baas.models import (
            PartnerBillingImport, PartnerFinanceReceipt, PartnerMeterClaim,
            PartnerReportReview,
        )
        from .partner_helpers import fixture, report, delivered

        actor, case, finance, _, cov = fixture()
        source_report = report(actor, case)
        accepted_receipt = delivered(actor, case, finance, source_report)
        self.assertEqual(PartnerReportReview.objects.get(report=source_report).verdict, 'approve')
        proof = evidence(finance, case, 'partner_decision',
                         'Synthetic exact supplied-meter acceptance; not provider authentication')
        imported = domain.import_finance_usage(
            finance, case.pk, accepted_receipt.pk, 'Finance', proof.pk, rev(case))
        explicit_price(actor, case, cov, '6', '2', '12.00', unit='transaction')
        prep = prepare(actor, case, cov, u=imported.usage)
        self.assertEqual(prep.result['status'], 'prepared')
        self.assertEqual(prep.result['total'], '12.00')
        self.assertEqual([row['quantity'] for row in imported.usage.rows], ['2', '3', '1'])
        before = {
            model: list(model.objects.order_by('pk').values()) for model in
            [PartnerFinanceReceipt, PartnerBillingImport, PartnerMeterClaim,
             BillingUsage, BillingPreparation, Invoice, InvoiceIssue]
        }
        repeated = domain.import_finance_usage(
            finance, case.pk, accepted_receipt.pk, 'Finance', proof.pk, rev(case))
        self.assertEqual((repeated.pk, repeated.usage_id), (imported.pk, imported.usage_id))
        self.assertEqual(prepare(actor, case, cov, u=repeated.usage).pk, prep.pk)
        for model, rows in before.items():
            self.assertEqual(list(model.objects.order_by('pk').values()), rows, model.__name__)
        self.assertEqual(PartnerFinanceReceipt.objects.count(), 1)
        self.assertEqual(PartnerBillingImport.objects.count(), 1)
        self.assertEqual(BillingUsage.objects.count(), 1)
        self.assertEqual(BillingPreparation.objects.count(), 1)
        self.assertEqual(PartnerMeterClaim.objects.count(), 3)
        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(InvoiceIssue.objects.count(), 0)
        self.assertEqual(imported.policy['receipt_hash'], accepted_receipt.sha256)
        self.assertEqual(prep.snapshot['usage_hash'], imported.usage.source_sha256)
        origin = prep.snapshot['partner_meter_origin']
        self.assertEqual(origin['acceptance'], imported.pk)
        self.assertEqual(origin['receipt'], accepted_receipt.pk)
        self.assertEqual(origin['report_hash'], source_report.sha256)
        self.assertEqual(origin['source_hash'], source_report.record.evidence.sha256)
        self.assert_sql_immutable(BillingUsage, imported.usage_id, 'source_sha256', '0' * 64)
        billing.ensure_current(prep)

    def test_f29_n01_literal_ten_times_two_is_twenty_with_exact_versions(self):
        actor, case, cov, configs, oracle, batch, prep = self.priced_usage()
        self.assertEqual(prep.result['status'], 'prepared')
        self.assertEqual(prep.result['findings'], [])
        self.assertEqual(prep.result['currency'], 'NGN')
        self.assertEqual(prep.result['amount_basis'], 'net_exclusive')
        self.assertEqual(prep.result['total'], '20.00')
        self.assertEqual(len(prep.result['lines']), 1)
        line = prep.result['lines'][0]
        self.assertEqual({key: line[key] for key in ['quantity', 'rate', 'net', 'tax', 'total']},
                         {'quantity': '10', 'rate': '2', 'net': '20.00', 'tax': '0.00', 'total': '20.00'})
        self.assertEqual(Decimal(line['raw_net']), Decimal('20'))
        self.assertEqual(line['rule'], 'catalogue-rate-v1')
        self.assertEqual(prep.usage_id, batch.pk)
        self.assertEqual(prep.snapshot['usage_hash'], batch.evidence.sha256)
        self.assertEqual(batch.evidence.version, 1)
        self.assertEqual(batch.rows[0]['quantity'], '10')
        self.assertEqual(prep.snapshot['coverage_version'], cov.version)
        for config in configs:
            self.assertEqual(prep.snapshot['policies'][config.component],
                             {'status': 'ACTIVE', 'id': config.pk, 'revision': config.revision})
        arithmetic = reference_values(configs[1])[0]
        self.assertEqual((arithmetic['tax_rate'], arithmetic['decimal_places'], arithmetic['rounding']),
                         ('0', 2, 'half_up'))
        self.assertEqual(arithmetic['oracle_evidence_id'], oracle.pk)
        self.assertEqual(prepare(actor, case, cov, u=batch).pk, prep.pk)
        self.assertEqual(BillingPreparation.objects.count(), 1)
        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(CashReceipt.objects.count(), 0)
        for flag in ['invoice_issued', 'ledger_posted', 'cash_received', 'release_authorized']:
            self.assertFalse(prep.result[flag])
        self.assert_sql_immutable(BillingPreparation, prep.pk, 'result', '{}')
        billing.ensure_current(prep)

    def test_f32_n01_native_inv1_100_r1_40_leaves_60_with_immutable_lineage(self):
        from tests.obligation_helpers import approve_identified as approve, issue_identified as issue
        actor, case, cov, _, _, batch, prep = self.priced_usage('10', '10', '100.00')
        supplied = configured(actor, case)
        self.assertEqual(supplied['matching']['implementation'], 'explicit_human_v1')
        proofs = {kind: evidence(actor, case, kind, 'Synthetic explicit ' + kind)
                  for kind in ['invoice_review', 'cash_correction', 'cash_allocation']}
        invoice = draft(actor, case, prep, 'INV1')
        self.assertEqual(invoice.amount, Decimal('100'))
        self.assertEqual(InvoiceIssue.objects.count(), 0)
        from tests.obligation_helpers import identified
        identified(actor, case, invoice)
        with self.assertRaisesMessage(ValidationError, 'Finance approval'):
            invoices.reserve(actor, case.pk, invoice.pk, 'issue', 'Finance', rev(case))
        reviewed = approve(actor, case, invoice, proofs)
        job = invoices.reserve(actor, case.pk, invoice.pk, 'issue', 'Finance', rev(case))
        invoice_delivery.run_once(TimeoutAfterInvoiceAccept())
        job.refresh_from_db()
        self.assertEqual(job.status, 'unknown')
        issued = InvoiceIssue.objects.get(invoice=invoice)
        original_issue = copy.deepcopy(issued.payload)
        original_hash = issued.sha256
        invoice_delivery.run_once()
        job.refresh_from_db()
        self.assertEqual(job.status, 'confirmed')
        self.assertFalse(invoice_delivery.run_once())
        self.assertEqual(InvoiceIssue.objects.count(), 1)
        self.assertEqual(InvoiceJob.objects.count(), 1)
        self.assertEqual(InvoiceReview.objects.count(), 1)
        self.assertEqual(issued.job_id, job.pk)
        self.assertEqual(issued.operation_key, 'obligation:' + invoice.obligation_key)
        self.assertEqual(issued.obligation_key, invoice.obligation_key)
        self.assertEqual(job.operation_key, f'invoice:{invoice.pk}:issue:g1')
        self.assertEqual(reviewed.publication_packet['payload_hash'], invoice.sha256)
        self.assertEqual(invoice.preparation_id, prep.pk)
        self.assertEqual(prep.usage_id, batch.pk)
        self.assertEqual(issued.payload, invoice.payload)
        self.assertEqual(issued.payload['reference'], 'INV1')
        self.assertEqual(issued.payload['amount'], '100.00')

        reported, lot = receipt(actor, case, '40.00', 'R1')
        self.assertEqual(lot.receipt_id, reported.pk)
        self.assertEqual(reported.transaction_ref, 'R1')
        self.assertEqual(lot.amount, Decimal('40'))
        self.assertEqual(cash.report(actor, case.pk, reported.evidence_id, rev(case)).pk, reported.pk)
        self.assertEqual(cash.verify(actor, case.pk, reported.pk, 'Finance', lot.evidence_id, rev(case)).pk, lot.pk)
        assigned = assign(actor, case, reported, cov, proofs)
        matched = allocate(actor, case, lot, issued, '40.00', proofs, 'R1-INV1')
        self.assertEqual(allocate(actor, case, lot, issued, '40.00', proofs, 'R1-INV1').pk, matched.pk)
        self.assertEqual((matched.lot_id, matched.issue_id, matched.amount), (lot.pk, issued.pk, Decimal('40')))
        self.assertEqual(assigned.coverage_id, cov.pk)
        self.assertEqual(CashReceipt.objects.count(), 1)
        self.assertEqual(CashVerification.objects.count(), 1)
        self.assertEqual(CashAllocation.objects.count(), 1)
        self.assertEqual(cash.cash_remaining(lot), Decimal('0'))
        self.assertEqual(cash.open_amount(issued), Decimal('60'))
        snapshot = receivables.snapshot(actor, case.pk, timezone.localdate(), rev(case))
        row = snapshot.result['invoices'][0]
        self.assertEqual((row['invoice'], row['issue'], row['reference']), (invoice.pk, issued.pk, 'INV1'))
        self.assertEqual([Decimal(row[key]) for key in ['face', 'allocated', 'open']],
                         [Decimal('100'), Decimal('40'), Decimal('60')])
        self.assertFalse(row['voided'])
        self.assertEqual(Decimal(snapshot.result['groups'][0]['receivable']), Decimal('60'))
        self.assertEqual(Decimal(snapshot.result['groups'][0]['verified_cash']), Decimal('40'))
        self.assertEqual(snapshot.result['unmatched_cash'], [])
        self.assertEqual(snapshot.result['reported_unverified'], [])
        for key, value in [('issues', issued.pk), ('reported_receipts', reported.pk),
                           ('verified_lots', lot.pk), ('assignments', assigned.pk), ('allocations', matched.pk)]:
            self.assertEqual(snapshot.manifest[key], [value])
        self.assertTrue(snapshot.result['payment_assessment'].startswith('UNKNOWN:'))
        self.assertFalse(snapshot.result['deployment_authorized'])
        self.assertFalse(snapshot.result['ledger_posted'])
        self.assertEqual(InvoiceDelivery.objects.count(), 0)
        self.assertEqual(CashReversal.objects.count(), 0)
        from apps.pmo.models import DeliveryRecord
        from apps.workflows.models import FactoryWork
        self.assertEqual(DeliveryRecord.objects.filter(kind='closure').count(), 0)
        self.assertEqual(FactoryWork.objects.count(), 0)
        for model, record, column, replacement in [
            (Invoice, invoice, 'amount', '1'),
            (InvoiceIssue, issued, 'payload', '{}'),
            (CashReceipt, reported, 'payload', '{}'),
            (CashVerification, lot, 'amount', '1'),
            (CashAllocation, matched, 'amount', '1'),
        ]:
            self.assert_sql_immutable(model, record.pk, column, replacement)
        issued.refresh_from_db()
        self.assertEqual((issued.payload, issued.sha256), (original_issue, original_hash))
        self.assertEqual(cash.open_amount(issued), Decimal('60'))
