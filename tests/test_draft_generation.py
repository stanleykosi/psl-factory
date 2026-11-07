"""F30 native persistence, synthetic external transport only; no held modules."""
import copy
import json
import tempfile
from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection, transaction, DatabaseError
from django.utils import timezone
from apps.documents.contracts import digest
from apps.finance import draft_generation as generation
from apps.finance.models import (DraftGeneration, DraftGenerationAttempt, DraftGenerationObservation,
    DraftGenerationCancellation, InvoiceIssue, InvoiceDelivery, Invoice, InvoiceJob,
    CashReceipt, CashAllocation, CashVerification, LedgerLineage)
from apps.identity.models import Grant
from adapters.draft_generation import MockDraftGenerationAdapter
from .d03_helpers import fixture, source, confirm


def setup_generation():
    f = fixture()
    capability = {'schema': 'draft-generation-contract/v1', 'action': 'draft_generation',
        'implementation': 'mock_draft_generation_v1', 'draft_only': True,
        **{key: f['flow'].payload[key] for key in ['flow_ref', 'flow_version', 'environment_ref']},
        'output_contract': {'schema': 'draft-document/v1', 'document_ref': 'DOC-1', 'posted': False, 'sent': False}}
    f['draft_source'] = source(f, 'flow_contract', reference='draft-only-flow', changes={
        'external_ref': str(f['case'].pk) + ':draft-flow', 'implementation': 'incumbent_reference_only',
        'quote': json.dumps(capability), 'effect_requirements': {'issue': None, 'deliver': None}})
    confirm(f, f['draft_source'])
    return f


class DraftGenerationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f = setup_generation()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='psl-draft761-')
        self.addCleanup(self.directory.cleanup)
        self.adapter = MockDraftGenerationAdapter(self.directory.name)

    def reserve(self, **changes):
        f = self.f
        args = dict(actor=f['actor'], case_id=f['case'].pk, preparation_id=f['preparation'].pk,
                    source_id=f['draft_source'].pk, batch_ref='B1', operation_key='B1-generate-v1')
        args.update(changes)
        return generation.reserve(**args)

    def execute(self, row, adapter=None):
        return generation.run_once(self.f['actor'], self.f['case'].pk, row.pk, adapter or self.adapter)

    def report(self, row):
        return generation.report(self.f['actor'], self.f['case'].pk, row.pk)

    def test_f30_n01_b1_doc1_separate_generation_facts_ui_and_agent(self):
        financial_models = [Invoice, InvoiceJob, InvoiceIssue, InvoiceDelivery, CashReceipt, CashAllocation, CashVerification, LedgerLineage]
        before = {m.__name__: m.objects.count() for m in financial_models}
        row = self.reserve()
        self.assertIsNone(self.report(row)['generated'])
        observation = self.execute(row)
        self.assertTrue(observation.accepted)
        result = self.report(row)
        self.assertEqual(result['batch_ref'], 'B1')
        self.assertEqual(result['result']['document_ref'], 'DOC-1')
        self.assertTrue(result['generated']); self.assertIs(result['posted'], False); self.assertIs(result['sent'], False)
        self.assertFalse(InvoiceIssue.objects.exists()); self.assertFalse(InvoiceDelivery.objects.exists())
        self.client.force_login(self.f['actor'])
        page = self.client.get(f"/cases/{self.f['case'].pk}/finance/billing/")
        self.assertContains(page, 'Draft-only external generation (F30)')
        self.assertContains(page, 'DOC-1')
        from apps.agents.billing import investigate
        run = investigate(self.f['actor'], self.f['case'].pk, self.f['coverage'].pk, self.f['preparation'].pk, None)
        self.assertEqual(run.result['draft_generation'][0]['result']['document_ref'], 'DOC-1')
        self.assertFalse(run.result['invoice_issued'])
        self.assertEqual(before, {m.__name__: m.objects.count() for m in financial_models})

    def test_duplicate_intent_and_same_observation_retry_are_not_distinct_receipts(self):
        row = self.reserve(); self.assertEqual(row.pk, self.reserve().pk)
        observed = self.execute(row); attempt = observed.attempt
        duplicate = generation.observe(self.f['actor'], self.f['case'].pk, attempt.pk, attempt.fence, observed.payload)
        self.assertEqual(observed.pk, duplicate.pk)
        later = self.execute(row)
        self.assertNotEqual(later.pk, observed.pk)
        self.assertEqual(DraftGeneration.objects.count(), 1)
        self.assertEqual(row.attempts.filter(action='generate').count(), 1)
        self.assertEqual(later.attempt.action, 'lookup')
        self.assertEqual(later.payload['run_id'], observed.payload['run_id'])

    def test_key_collision_and_business_duplicate_hold_new_effects(self):
        self.reserve()
        with self.assertRaises(ValidationError): self.reserve(batch_ref='different')
        with self.assertRaises(ValidationError): self.reserve(operation_key='new-key')
        self.assertEqual(DraftGeneration.objects.count(), 1)
        self.assertFalse(DraftGenerationAttempt.objects.exists())

    def test_f30_e01_timeout_after_creation_reconciles_with_new_adapter(self):
        row = self.reserve()
        attempt = self.execute(row, MockDraftGenerationAdapter(self.directory.name, timeout_after_create=True))
        self.assertEqual(attempt.action, 'generate'); self.assertFalse(DraftGenerationObservation.objects.exists())
        recovered = self.execute(row, MockDraftGenerationAdapter(self.directory.name))
        self.assertEqual(recovered.attempt.action, 'lookup')
        self.assertEqual(recovered.payload['document_ref'], 'DOC-1')
        self.assertEqual(row.attempts.filter(action='generate').count(), 1)

    def test_crash_after_claim_not_found_never_authorizes_regeneration(self):
        row = self.reserve()
        generation.claim(self.f['actor'], self.f['case'].pk, row.pk)
        for _ in range(2):
            observation = self.execute(row)
            self.assertEqual(observation.payload['outcome'], 'not_found')
        self.assertEqual(row.attempts.filter(action='generate').count(), 1)
        self.assertFalse(list(self.adapter.directory.glob('*.json')))
        self.assertEqual(self.report(row)['next_action'], 'lookup_original_only')

    def test_unknown_eventual_consistency_only_allows_original_lookup(self):
        row = self.reserve()
        self.execute(row, MockDraftGenerationAdapter(self.directory.name, timeout_after_create=True))
        unknown = self.execute(row, MockDraftGenerationAdapter(self.directory.name, lookup_unknown=True))
        self.assertEqual(unknown.payload['outcome'], 'unknown')
        self.assertEqual(self.execute(row).payload['document_ref'], 'DOC-1')
        self.assertEqual(row.attempts.filter(action='generate').count(), 1)

    def test_dispatch_revocation_holds_new_generation_but_not_original_lookup(self):
        row = self.reserve()
        Grant.objects.filter(case=self.f['case'], user=self.f['actor'], action='finance.draft_generation.dispatch').update(active=False)
        with self.assertRaises(PermissionDenied): self.execute(row)
        self.assertFalse(row.attempts.exists())

    def test_timeout_then_revocation_and_cancel_preserves_original_receipt_lookup(self):
        row = self.reserve()
        self.execute(row, MockDraftGenerationAdapter(self.directory.name, timeout_after_create=True))
        generation.cancel(self.f['actor'], self.f['case'].pk, row.pk, 'Stop new effects, retain original lookup')
        Grant.objects.filter(case=self.f['case'], user=self.f['actor'], action='finance.draft_generation.dispatch').update(active=False)
        Grant.objects.filter(case=self.f['case'], user=self.f['owner'], action='d03.source.read').update(active=False)
        self.assertTrue(self.execute(row).accepted)
        self.assertTrue(self.report(row)['generated'])
        self.assertTrue(self.report(row)['holds'])
        self.assertEqual(row.attempts.filter(action='generate').count(), 1)

    def test_cancellation_before_dispatch_never_creates_external_output(self):
        row = self.reserve()
        generation.cancel(self.f['actor'], self.f['case'].pk, row.pk, 'No longer requested')
        with self.assertRaises(ValidationError): self.execute(row)
        self.assertFalse(row.attempts.exists())
        self.assertFalse(list(self.adapter.directory.glob('*.json')))

    def test_changed_source_destination_flow_holds_dispatch(self):
        row = self.reserve()
        s = self.f['draft_source']; cap = json.loads(s.payload['quote']); cap['output_contract']['document_ref'] = 'DOC-2'
        newer = source(self.f, 'flow_contract', reference=s.reference, changes={**s.payload,
            'quote': json.dumps(cap), 'source_version': 'v2'}, predecessor=s.pk)
        confirm(self.f, newer)
        with self.assertRaises(ValidationError): self.execute(row)
        self.assertFalse(row.attempts.exists())

    def test_conflicting_callback_retained_and_wrong_fence_rejected(self):
        row = self.reserve(); first = self.execute(row); attempt = first.attempt
        value = dict(first.payload, document_sha256='0' * 64, observed_at=timezone.now().isoformat())
        bad = generation.observe(self.f['actor'], self.f['case'].pk, attempt.pk, attempt.fence, value)
        self.assertFalse(bad.accepted); self.assertTrue(self.report(row)['holds'])
        with self.assertRaises(ValidationError):
            generation.observe(self.f['actor'], self.f['case'].pk, attempt.pk, 'wrong-fence', value)
        self.assertEqual(DraftGenerationObservation.objects.count(), 2)

    def test_posted_or_sent_response_never_becomes_successful_draft_receipt(self):
        row = self.reserve(); attempt = generation.claim(self.f['actor'], self.f['case'].pk, row.pk)
        response = self.adapter.generate(row.payload); response['sent'] = True
        observed = generation.observe(self.f['actor'], self.f['case'].pk, attempt.pk, attempt.fence, response)
        self.assertFalse(observed.accepted); self.assertIsNone(self.report(row)['generated'])
        self.assertFalse(InvoiceIssue.objects.exists()); self.assertFalse(InvoiceDelivery.objects.exists())

    def test_sql_append_only_and_cross_case_payload_guards(self):
        row = self.reserve(); observation = self.execute(row)
        generation.cancel(self.f['actor'], self.f['case'].pk, row.pk, 'Test cancellation history')
        for model in [DraftGeneration, DraftGenerationAttempt, DraftGenerationObservation, DraftGenerationCancellation]:
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('UPDATE ' + model._meta.db_table + ' SET id=id')
        row.pk = None; row._state.adding = True; row.operation_key = 'forged'; row.business_key = '0' * 64
        row.payload = dict(row.payload, operation_key='forged', batch_sha256='0' * 64); row.sha256 = digest(row.payload)
        with self.assertRaises(DatabaseError), transaction.atomic(): row.save(force_insert=True)
        value = dict(observation.payload, posted=True)
        with self.assertRaises(DatabaseError), transaction.atomic():
            DraftGenerationObservation.objects.create(attempt=observation.attempt, actor=self.f['actor'],
                fence=observation.attempt.fence, payload=value, sha256=digest(value), accepted=True, finding='')

    def test_read_lookup_and_other_case_grants_are_independent(self):
        row = self.reserve(); self.execute(row)
        Grant.objects.filter(case=self.f['case'], user=self.f['actor'], action='finance.draft_generation.lookup').update(active=False)
        with self.assertRaises(PermissionDenied): self.execute(row)
        self.assertTrue(self.report(row)['generated'])
        Grant.objects.filter(case=self.f['case'], user=self.f['actor'], action='d03.read').update(active=False)
        with self.assertRaises(PermissionDenied): self.report(row)

    def test_generated_document_cannot_be_claimed_by_second_business_batch(self):
        first = self.reserve(); self.execute(first)
        from .billing_helpers import usage, prepare
        f = self.f
        body = f['preparation'].usage.evidence.body.replace('tx-example-1', 'tx-distinct-2')
        new_usage = usage(f['actor'], f['case'], f['coverage'], body)
        new_preparation = prepare(f['actor'], f['case'], f['coverage'], u=new_usage)
        second = self.reserve(preparation_id=new_preparation.pk, batch_ref='B2', operation_key='B2-generate-v1')
        observation = self.execute(second)
        self.assertFalse(observation.accepted)
        self.assertIn('already belongs', observation.finding)
        self.assertIsNone(self.report(second)['generated'])
