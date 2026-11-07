from django.test import TransactionTestCase
import copy
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection, transaction, DatabaseError
from django.test import TestCase
from django.utils import timezone
from apps.core.models import Case
from apps.core.evidence_access import public_evidence, public_agent_runs
from apps.identity.models import Grant
from apps.finance import usage_intake as domain, billing, invoices, invoice_delivery
from apps.finance.models import (UsageIntakeSource, UsageIntakeReceipt, UsageIntakeAcceptance, UsageIntakeWithdrawal,
                                BillingUsage, BillingPreparation, Invoice, InvoiceReview, InvoiceJob, InvoiceIssue)
from adapters.invoices import TimeoutAfterInvoiceAccept
from .helpers import rev
from .billing_helpers import evidence, coverage, prepare
from .usage_intake_helpers import fixture, receive, correction, prices
from .settlement_helpers import configured, draft, approve


class UsageIntakeTests(TransactionTestCase):
    def setUp(self):
        self.a, self.c, self.covs, self.payload, self.controls = fixture()

    def received(self, **kwargs):
        return receive(self.a, self.c, self.payload, self.controls, **kwargs)

    def accepted(self):
        receipt = self.received()
        accepted = domain.accept(self.a, self.c.pk, receipt.source_id, rev(self.c))
        return receipt, accepted

    def prepared(self):
        receipt, accepted = self.accepted()
        prices(self.a, self.c, self.covs)
        preparations = [prepare(self.a, self.c, p.coverage, u=p) for p in accepted.partitions.select_related('coverage').order_by('pk')]
        return receipt, accepted, preparations

    def assert_immutable(self, model, record, field, value):
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f'UPDATE {model._meta.db_table} SET {field}=%s WHERE id=%s', [value, record.pk])

    def test_f28_u1_c1_c2_september_approved_controls_two_deliveries_one_partition_set_feeds_native_pricing(self):
        r, accepted, preparations = self.prepared()
        self.assertEqual(r.source.report_ref, 'U1'); self.assertEqual(r.source.period, '2026-09')
        self.assertEqual(accepted.result['status'], 'reconciled')
        self.assertEqual([p.result['total'] for p in preparations], ['20.00', '40.00'])
        self.assertEqual({p.coverage.customer for p in preparations}, {'C1', 'C2'})
        self.assertTrue(all(billing.coverage_current(c) for c in self.covs))
        before = {m: list(m.objects.order_by('pk').values()) for m in [BillingUsage, BillingPreparation, UsageIntakeSource, UsageIntakeAcceptance]}
        duplicate = self.received(delivery='delivery-2', operation='operation-2')
        self.assertEqual(duplicate.duplicate_of_id, r.pk)
        self.assertEqual(duplicate.source_id, r.source_id)
        self.assertEqual(UsageIntakeReceipt.objects.count(), 2)
        self.assertEqual(domain.accept(self.a, self.c.pk, r.source_id, 0).pk, accepted.pk)
        for p in preparations:
            billing.ensure_current(p)
            self.assertEqual(prepare(self.a, self.c, p.coverage, u=p.usage).pk, p.pk)
            self.assertEqual(p.snapshot['collective_usage_origin']['source_sha256'], r.source.sha256)
            self.assertEqual(p.snapshot['collective_usage_origin']['population'], sorted(c.pk for c in self.covs))
        for model, rows in before.items(): self.assertEqual(list(model.objects.order_by('pk').values()), rows)
        self.assertFalse(Invoice.objects.exists())

    def test_same_operation_retry_reconciles_before_revision_or_effect_and_conflicting_intent_rejected(self):
        r, accepted = self.accepted()
        self.assertEqual(domain.lookup(self.a, self.c.pk, 'operation-1').pk, r.pk)
        retry = domain.receive(self.a, self.c.pk, r.evidence_id, r.control_evidence_id, 'delivery-1', 'operation-1', 0)
        self.assertEqual(retry.pk, r.pk); self.assertEqual(UsageIntakeReceipt.objects.count(), 1)
        with self.assertRaisesMessage(ValidationError, 'conflicts'):
            domain.receive(self.a, self.c.pk, r.evidence_id, r.control_evidence_id, 'other-delivery', 'operation-1')
        with self.assertRaisesMessage(ValidationError, 'already recorded'):
            domain.receive(self.a, self.c.pk, r.evidence_id, r.control_evidence_id, 'delivery-1', 'different-operation')
        self.assertEqual(BillingUsage.objects.count(), 2)
        self.assertEqual(UsageIntakeAcceptance.objects.count(), 1)

    def test_missing_c2_unknown_quantity_control_mismatch_and_explicit_zero(self):
        variants = [([self.payload['rows'][0]], 'Missing expected population'),
                    ([dict(self.payload['rows'][0], quantity=None), self.payload['rows'][1]], 'Unknown quantity'),
                    ([dict(self.payload['rows'][0], quantity='11'), self.payload['rows'][1]], 'control total mismatch')]
        for index, (rows, message) in enumerate(variants):
            with self.subTest(message=message):
                payload, controls = copy.deepcopy(self.payload), copy.deepcopy(self.controls)
                payload['report_ref'] = controls['report_ref'] = 'exception-' + str(index)
                payload['rows'] = rows
                r = receive(self.a, self.c, payload, controls, delivery='delivery-' + str(index), operation='operation-' + str(index))
                run = domain.investigate(self.a, self.c.pk, r.source_id, rev(self.c))
                self.assertTrue(any(message in f for f in run.result['missing_fields']))
                self.assertEqual(len(run.result['citations']), 2)
                self.assertFalse(run.result['approval_granted'])
                with self.assertRaises(ValidationError): domain.accept(self.a, self.c.pk, r.source_id, rev(self.c))
        self.assertFalse(BillingUsage.objects.exists()); self.assertFalse(BillingPreparation.objects.exists())
        self.payload['rows'][0]['quantity'] = self.controls['population'][0]['quantity'] = '0'
        self.controls['totals'][0]['quantity'] = '20'
        r = self.received(delivery='explicit-zero-delivery', operation='explicit-zero-operation')
        accepted = domain.accept(self.a, self.c.pk, r.source_id)
        self.assertEqual(accepted.partitions.order_by('pk')[0].rows[0]['quantity'], '0')

    def test_unknown_control_total_and_unexpected_unit_hold_without_zero_default(self):
        self.controls['totals'][0]['quantity'] = None
        self.controls['population'][0]['quantity'] = None
        self.payload['rows'][1]['unit'] = 'unexpected-unit'
        r = self.received(); result = domain.inspect(r.source)
        self.assertEqual(result['status'], 'held')
        self.assertTrue(any('Collective control quantity unknown' in f for f in result['findings']))
        self.assertTrue(any('Unexpected population' in f for f in result['findings']))
        with self.assertRaises(ValidationError): domain.accept(self.a, self.c.pk, r.source_id)
        self.assertFalse(BillingUsage.objects.exists())

    def test_renaming_report_is_not_an_authorized_duplicate_usage_import(self):
        original, accepted = self.accepted()
        payload, controls = copy.deepcopy(self.payload), copy.deepcopy(self.controls)
        payload['report_ref'] = controls['report_ref'] = 'U2'
        r = receive(self.a, self.c, payload, controls, delivery='renamed-delivery', operation='renamed-operation')
        self.assertIn('Previously captured transaction needs explicit source correction lineage', domain.inspect(r.source)['findings'])
        with self.assertRaises(ValidationError): domain.accept(self.a, self.c.pk, r.source_id)
        # A raw acceptance can satisfy controls but cannot commit a duplicate partition.
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SELECT psl_usage_result(%s)', [r.source_id]); result = json.loads(cursor.fetchone()[0])
            bypass = UsageIntakeAcceptance.objects.create(source=r.source, receipt=r, result=result, actor=self.a)
            partition = accepted.partitions.order_by('pk').first()
            BillingUsage.objects.create(coverage=partition.coverage, collective_acceptance=bypass, evidence=r.evidence,
                source_sha256=r.evidence.sha256, rows=partition.rows, findings=[], source_context=domain.context(r.source), actor=self.a)
        self.assertEqual(BillingUsage.objects.count(), 2)

    def test_unknown_completeness_dates_and_control_approval_hold_without_inferred_signature(self):
        self.payload['cutoff_at'] = None; self.payload['completeness'] = 'unknown'
        self.controls['approval_reference'] = None
        r = self.received(); result = domain.inspect(r.source)
        self.assertEqual(result['status'], 'held')
        self.assertIn('cutoff_at is unknown', result['findings'])
        self.assertIn('Supplied control approval reference is unknown', result['findings'])
        with self.assertRaises(ValidationError): domain.accept(self.a, self.c.pk, r.source_id)
        self.assertFalse(UsageIntakeAcceptance.objects.exists())

    def test_changed_c1_explicit_correction_preserves_old_partitions_preparations_review_and_obligation(self):
        from tests.obligation_helpers import approve_identified as approve
        r, accepted, preparations = self.prepared(); configured(self.a, self.c)
        old = draft(self.a, self.c, preparations[0], 'INV-U1-C1')
        proof = evidence(self.a, self.c, 'invoice_review', 'Synthetic exact native review')
        review = approve(self.a, self.c, old, {'invoice_review': proof})
        frozen = {m: list(m.objects.order_by('pk').values()) for m in [BillingUsage, BillingPreparation, Invoice, InvoiceReview]}
        payload, controls = correction(self.payload, self.controls)
        with self.assertRaisesMessage(ValidationError, 'predecessor'):
            receive(self.a, self.c, payload, controls, delivery='corrected-delivery', operation='corrected-operation')
        replacement = receive(self.a, self.c, payload, controls, delivery='corrected-delivery', operation='corrected-operation', predecessor=r.source_id)
        with self.assertRaises(ValidationError): billing.ensure_current(preparations[0])
        with self.assertRaises(ValidationError): invoices.reviewed(old)
        with self.assertRaises(ValidationError): invoices.reserve(self.a, self.c.pk, old.pk, 'issue', 'Finance', rev(self.c))
        next_accepted = domain.accept(self.a, self.c.pk, replacement.source_id, rev(self.c))
        newer = prepare(self.a, self.c, self.covs[0], u=next_accepted.partitions.get(coverage=self.covs[0]))
        self.assertEqual(newer.result['total'], '24.00'); billing.ensure_current(newer)
        self.assertEqual(invoices.obligation(newer), old.obligation_key)
        for model, rows in frozen.items(): self.assertEqual(list(model.objects.filter(pk__in=[x['id'] for x in rows]).order_by('pk').values()), rows)
        self.assertEqual(InvoiceReview.objects.get(pk=review.pk).publication_packet['sources'], preparations[0].snapshot)
        held = prepare(self.a, self.c, self.covs[0], u=preparations[0].usage)
        self.assertEqual(held.result['status'], 'held')

    def test_changed_content_under_old_version_is_not_a_retry_and_control_version_is_exact(self):
        r = self.received()
        self.payload['rows'][0]['quantity'] = '13'
        with self.assertRaisesMessage(ValidationError, 'correction version'):
            self.received(delivery='delivery-2', operation='operation-2')
        self.payload['controls_version'] = 'unmatched'
        with self.assertRaisesMessage(ValidationError, 'version-bound'):
            self.received(delivery='delivery-3', operation='operation-3')
        self.assertEqual(UsageIntakeSource.objects.count(), 1)
        self.assertEqual(UsageIntakeReceipt.objects.count(), 1)

    def test_cross_case_routing_and_finance_privacy_and_current_grants(self):
        other = Case.objects.create(tenant=self.c.tenant, title='Other private scope', kind='project', synthetic=True)
        self.controls['scope']['case_id'] = str(other.pk)  # shared scope object in fixture, both now wrong
        with self.assertRaises(ValidationError): self.received()
        self.controls['scope']['case_id'] = str(self.c.pk)
        Grant.objects.bulk_create([Grant(user=self.a, case=other, action=act) for act in ['case.read', 'finance.read', 'finance.billing.register', 'evidence.add']])
        other_cov = coverage(self.a, other, customer='C2', service='API', contract='C2-contract')
        self.controls['population'][1]['coverage_id'] = other_cov.pk
        with self.assertRaisesMessage(ValidationError, 'authorized case coverage'): self.received()
        self.controls['population'][1]['coverage_id'] = self.covs[1].pk
        r = self.received(); run = domain.investigate(self.a, self.c.pk, r.source_id)
        self.assertFalse(public_evidence(self.c.evidence.all()).filter(pk=r.evidence_id).exists())
        self.assertFalse(public_agent_runs(type(run).objects.all()).filter(pk=run.pk).exists())
        reader = get_user_model().objects.create_user(username='case-reader')
        Grant.objects.create(user=reader, case=self.c, action='case.read')
        self.client.force_login(reader)
        self.assertEqual(self.client.get(f'/cases/{self.c.pk}/finance/usage-intake/').status_code, 403)
        page = self.client.get(f'/cases/{self.c.pk}/')
        self.assertNotContains(page, 'synthetic-owner-approved-example')
        self.assertNotContains(page, 'U1-C1')
        Grant.objects.filter(user=self.a, case=self.c, action='finance.billing.capture').update(active=False)
        with self.assertRaises(PermissionDenied): domain.accept(self.a, self.c.pk, r.source_id)

    def test_source_withdrawal_and_capture_grant_revocation_hold_native_pricing(self):
        r, accepted, preparations = self.prepared()
        proof = evidence(self.a, self.c, 'usage_intake_withdrawal', 'Data withdraws supplied report U1')
        withdrawal = domain.withdraw(self.a, self.c.pk, r.source_id, proof.pk, 'Source withdrawn', rev(self.c))
        self.assertEqual(domain.withdraw(self.a, self.c.pk, r.source_id, proof.pk, 'Source withdrawn', 0).pk, withdrawal.pk)
        with self.assertRaises(ValidationError): billing.ensure_current(preparations[0])
        with self.assertRaises(ValidationError): domain.accept(self.a, self.c.pk, r.source_id)
        self.assertEqual(domain.lookup(self.a, self.c.pk, r.operation_key).pk, r.pk)
        self.assertEqual(domain.receive(self.a, self.c.pk, r.evidence_id, r.control_evidence_id, r.delivery_ref, r.operation_key, 0).pk, r.pk)
        self.assertEqual(BillingUsage.objects.count(), 2)
        self.assert_immutable(UsageIntakeWithdrawal, withdrawal, 'reason', 'tamper')

    def test_superseded_coverage_and_revoked_acceptance_actor_invalidate_all_populations(self):
        r, accepted, preparations = self.prepared()
        coverage(self.a, self.c, reference=self.covs[1].reference, customer='C2', service='API', contract='C2-contract', from_period='2026-09', to_period='2026-09')
        with self.assertRaises(ValidationError): billing.ensure_current(preparations[0])
        Grant.objects.filter(user=self.a, case=self.c, action='finance.billing.capture').update(active=False)
        with self.assertRaises(ValidationError): billing.ensure_current(preparations[1])
        self.assertEqual(UsageIntakeAcceptance.objects.count(), 1)

    def test_native_ui_receive_investigate_accept_repeat_lookup_withdraw_and_back_get_readonly(self):
        self.client.force_login(self.a)
        url = f'/cases/{self.c.pk}/finance/usage-intake/'
        e = evidence(self.a, self.c, 'usage_intake_source', json.dumps(self.payload))
        c = evidence(self.a, self.c, 'usage_intake_controls', json.dumps(self.controls))
        payload = {'action': 'receive', 'source_evidence': e.pk, 'control_evidence': c.pk, 'delivery_ref': 'delivery-1', 'operation_key': 'operation-1', 'revision': rev(self.c)}
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        r = UsageIntakeReceipt.objects.get()
        for action in ['inspect', 'accept']:
            self.assertEqual(self.client.post(url, {'action': action, 'source': r.source_id, 'revision': rev(self.c)}).status_code, 302)
        page = self.client.get(url); self.assertContains(page, 'Accepted usage'); self.assertContains(page, 'Cited investigation')
        self.assertContains(self.client.get(f'/cases/{self.c.pk}/finance/billing/'), 'Collective usage intake')
        self.assertEqual(self.client.post(url, {'action': 'lookup', 'operation_key': r.operation_key, 'revision': rev(self.c)}).status_code, 302)
        before = list(UsageIntakeReceipt.objects.values()); revision = rev(self.c)
        self.client.get(url); self.client.get(url)
        self.assertEqual(rev(self.c), revision); self.assertEqual(list(UsageIntakeReceipt.objects.values()), before)
        proof = evidence(self.a, self.c, 'usage_intake_withdrawal', 'Synthetic withdrawal')
        self.assertEqual(self.client.post(url, {'action': 'withdraw', 'source': r.source_id, 'evidence': proof.pk, 'reason': 'Withdrawn', 'revision': rev(self.c)}).status_code, 302)
        self.assertContains(self.client.get(url), 'Collective source withdrawn')

    def test_sql_immutable_and_insert_guards_reject_partial_unauthorized_or_stale_effects(self):
        r, accepted, preparations = self.prepared()
        self.assertEqual(connection.vendor, 'postgresql')
        self.assert_immutable(UsageIntakeSource, r.source, 'report_ref', 'tamper')
        self.assert_immutable(UsageIntakeReceipt, r, 'delivery_ref', 'tamper')
        self.assert_immutable(UsageIntakeAcceptance, accepted, 'result', '{}')
        self.assert_immutable(BillingUsage, preparations[0].usage, 'rows', '[]')
        partition = preparations[0].usage
        values = {f.attname: getattr(partition, f.attname) for f in BillingUsage._meta.fields if f.name not in ['id', 'created_at']}
        values['collective_acceptance_id'] = None
        with self.assertRaises(DatabaseError), transaction.atomic(): BillingUsage.objects.create(**values)
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_usage_current(%s)', [partition.pk]); self.assertTrue(cursor.fetchone()[0])
        configured(self.a, self.c); inv = draft(self.a, self.c, preparations[0])
        proof = evidence(self.a, self.c, 'invoice_review', 'Exact approved synthetic invoice')
        review = approve(self.a, self.c, inv, {'invoice_review': proof})
        withdrawal = evidence(self.a, self.c, 'usage_intake_withdrawal', 'Withdraw for correction')
        domain.withdraw(self.a, self.c.pk, r.source_id, withdrawal.pk, 'Withdrawn')
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_usage_current(%s)', [partition.pk]); self.assertFalse(cursor.fetchone()[0])
        for model, obj, changes in [(Invoice, inv, {'reference': 'BYPASS', 'version': 2}), (InvoiceReview, review, {}),
                                   (BillingPreparation, preparations[0], {'operation_key': 'a' * 64})]:
            data = {f.attname: getattr(obj, f.attname) for f in model._meta.fields if f.name not in ['id', 'created_at']}
            data.update(changes)
            with self.assertRaises(DatabaseError), transaction.atomic(): model.objects.create(**data)

    def test_missing_population_cannot_insert_acceptance_via_sql(self):
        self.payload['rows'].pop()
        r = self.received()
        fake = dict(domain.inspect(r.source), status='reconciled', findings=[])
        with self.assertRaises(DatabaseError), transaction.atomic():
            UsageIntakeAcceptance.objects.create(source=r.source, receipt=r, result=fake, actor=self.a)
        self.assertFalse(BillingUsage.objects.exists())

    def test_uncertain_invoice_acceptance_reconciles_receipt_after_source_withdrawal_and_blocks_second_issue(self):
        from tests.obligation_helpers import approve_identified as approve
        r, accepted, preparations = self.prepared(); configured(self.a, self.c)
        inv = draft(self.a, self.c, preparations[0], 'INV-U1-C1')
        proof = evidence(self.a, self.c, 'invoice_review', 'Synthetic approved exact invoice')
        approve(self.a, self.c, inv, {'invoice_review': proof})
        job = invoices.reserve(self.a, self.c.pk, inv.pk, 'issue', 'Finance', rev(self.c))
        invoice_delivery.run_once(adapter=TimeoutAfterInvoiceAccept())
        job.refresh_from_db(); self.assertEqual(job.status, 'unknown')
        withdrawal = evidence(self.a, self.c, 'usage_intake_withdrawal', 'Source withdrawn after uncertain issue')
        domain.withdraw(self.a, self.c.pk, r.source_id, withdrawal.pk, 'Await corrected source')
        invoice_delivery.run_once()
        job.refresh_from_db(); self.assertEqual(job.status, 'confirmed')
        issued = InvoiceIssue.objects.get(invoice=inv)
        self.assertEqual(issued.payload, inv.payload)
        payload, controls = correction(self.payload, self.controls)
        replacement = receive(self.a, self.c, payload, controls, delivery='correction', operation='correction', predecessor=r.source_id)
        newer = domain.accept(self.a, self.c.pk, replacement.source_id)
        prep = prepare(self.a, self.c, self.covs[0], u=newer.partitions.get(coverage=self.covs[0]))
        with self.assertRaisesMessage(ValidationError, 'already issued'): draft(self.a, self.c, prep, 'NO-SECOND-INVOICE')
        self.assertEqual(InvoiceIssue.objects.count(), 1)
        self.assertEqual(InvoiceJob.objects.count(), 1)


from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections, connections
from django.test import TransactionTestCase


class UsageIntakeConcurrencyTests(TransactionTestCase):
    def test_concurrent_same_operation_retry_and_same_acceptance_commit_one_exact_set(self):
        actor, case, coverages, payload, controls = fixture()
        e = evidence(actor, case, 'usage_intake_source', json.dumps(payload))
        ce = evidence(actor, case, 'usage_intake_controls', json.dumps(controls))
        barrier = Barrier(2)
        def receive_once():
            close_old_connections()
            try:
                a = get_user_model().objects.get(pk=actor.pk)
                barrier.wait(timeout=10)
                return domain.receive(a, case.pk, e.pk, ce.pk, 'actual-delivery-1', 'same-operation').pk
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: receive_once(), range(2)))
        self.assertEqual(ids[0], ids[1]); self.assertEqual(UsageIntakeReceipt.objects.count(), 1)
        source = UsageIntakeSource.objects.get()
        barrier = Barrier(2)
        def accept_once():
            close_old_connections()
            try:
                a = get_user_model().objects.get(pk=actor.pk)
                barrier.wait(timeout=10)
                return domain.accept(a, case.pk, source.pk).pk
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: accept_once(), range(2)))
        self.assertEqual(ids[0], ids[1]); self.assertEqual(UsageIntakeAcceptance.objects.count(), 1)
        self.assertEqual(BillingUsage.objects.count(), 2)

    def test_concurrent_distinct_deliveries_preserve_one_original_and_one_duplicate(self):
        actor, case, coverages, payload, controls = fixture()
        e = evidence(actor, case, 'usage_intake_source', json.dumps(payload))
        ce = evidence(actor, case, 'usage_intake_controls', json.dumps(controls))
        barrier = Barrier(2)
        def deliver(index):
            close_old_connections()
            try:
                a = get_user_model().objects.get(pk=actor.pk); barrier.wait(timeout=10)
                return domain.receive(a, case.pk, e.pk, ce.pk, 'delivery-' + str(index), 'operation-' + str(index)).pk
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(deliver, range(2)))
        self.assertNotEqual(ids[0], ids[1])
        self.assertEqual(UsageIntakeSource.objects.count(), 1)
        original = UsageIntakeReceipt.objects.get(duplicate_of=None)
        self.assertEqual(UsageIntakeReceipt.objects.exclude(pk=original.pk).get().duplicate_of_id, original.pk)
        self.assertFalse(BillingUsage.objects.exists())

    def test_sql_deferrable_guard_rejects_partial_partition_set_on_commit(self):
        actor, case, coverages, payload, controls = fixture()
        r = receive(actor, case, payload, controls)
        with self.assertRaises(DatabaseError), transaction.atomic():
            UsageIntakeAcceptance.objects.create(source=r.source, receipt=r, actor=actor, result=domain.inspect(r.source))
        self.assertFalse(UsageIntakeAcceptance.objects.exists())
