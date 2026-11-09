"""Synthetic F03 draft diagnostics, not workbook equivalence or full acceptance."""
import copy
import json
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.agents.finance_analysis import investigate_mapping_draft
from apps.core.services import add_evidence
from apps.documents.controlled import reserve_publication
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt
from apps.finance import analysis
from apps.finance.documents import draft_report
from apps.finance.mapping_diagnostics import preview_mapping_draft
from apps.finance.models import FinanceRun
from apps.finance.services import capture_import
from apps.identity.models import Grant
from apps.policy.finance_drafts import draft_finance_policy
from apps.policy.services import active_component, save_draft, transition
from .finance_analysis_helpers import fixture, pipeline, declared_units
from .helpers import rev, setup_case


class FinanceMappingDiagnosticsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a, cls.c, cls.e, cls.f, cls.configs, cls.source, cls.template, cls.recipient = fixture()

    def maps(self):
        a = dict(self.f['mapping'][0], key='A200-main', account='A200', report_line='line-one',
                 metric='other', treatment='company', bu=None, pool=None)
        return [a, dict(a, key='A200-conflict', report_line='line-two')]

    def draft(self, maps=None):
        return draft_finance_policy(self.a, self.c.pk, 'D06.account_bu_maps',
            self.maps() if maps is None else maps, self.e['policy_decision'].pk,
            timezone.now() - timedelta(days=1))

    def imported(self, rows=None):
        rows = [('A300', '30'), ('A200', '120')] if rows is None else rows
        csv = 'account,amount,currency,period\n' + ''.join(
            f'{account},{amount},NGN,2026-10\n' for account, amount in rows)
        evidence = add_evidence(self.a, self.c.pk, 'financial_input', csv, 'synthetic:F03-E01')
        batch = capture_import(self.a, self.c.pk, evidence.pk, rev(self.c))
        units = declared_units(self.a, self.c, batch)
        return analysis.capture_source(self.a, self.c.pk, batch.pk, 'synthetic-company', 'accrual',
            timezone.now()-timedelta(hours=1), 'complete', None, self.e['finance_source'].pk, rev(self.c), unit_declaration=units)

    def preview(self, source, draft):
        return preview_mapping_draft(self.a, self.c.pk, source.pk, draft.pk, rev(self.c))

    def test_f03_e01_simultaneous_unmapped_a300_and_ambiguous_a200_exact_source_rows(self):
        source, draft = self.imported(), self.draft()
        with CaptureQueriesContext(connection) as queries:
            result = self.preview(source, draft)
        self.assertFalse(any(query['sql'].lstrip().split()[0].upper() in
            ['INSERT', 'UPDATE', 'DELETE', 'ALTER', 'CREATE', 'DROP', 'TRUNCATE'] for query in queries))
        self.assertEqual(result['status'], 'draft_only')
        self.assertEqual([(item['code'], item['account'], item['source_line']) for item in result['exceptions']],
            [('UNMAPPED_ACCOUNT', 'A300', 2), ('AMBIGUOUS_MAPPING', 'A200', 3)])
        self.assertEqual(len(result['rows']), 2)  # No duplicate or synthetic missing-source rows.
        for row, account, amount, line in zip(result['rows'], ['A300', 'A200'], ['30', '120'], [2, 3]):
            self.assertEqual((row['account'], row['raw_amount'], row['source_line'], row['source_evidence']),
                (account, amount, line, source.batch.evidence_id))
            self.assertIsNone(row['selected_mapping'])
            self.assertNotIn('report_line', row)
        self.assertEqual(result['rows'][0]['candidate_keys'], [])
        self.assertEqual(result['rows'][1]['candidate_keys'], ['A200-main', 'A200-conflict'])
        self.assertEqual(result['rows'][1]['candidate_reference_ids'], [x['reference_id'] for x in result['candidates']])
        self.assertEqual(result['snapshot']['source_hash'], source.batch.source_sha256)
        self.assertEqual(result['snapshot']['configuration_id'], draft.pk)
        self.assertTrue(all(x['evidence_id'] == self.e['policy_decision'].pk and len(x['reference_sha256']) == 64
                            for x in result['candidates']))
        self.assertFalse(FinanceRun.objects.exists())
        self.assertFalse(result['authoritative'] or result['approval_granted'] or result['ledger_posted'])
        self.assertEqual(active_component('D06.account_bu_maps', self.c).pk, self.configs['D06.account_bu_maps'].pk)

    def test_overlap_still_cannot_validate_activate_review_or_reach_accounts(self):
        source, draft = self.imported(), self.draft()
        result = self.preview(source, draft)
        for state in ['validated', 'active']:
            with self.assertRaises(ValidationError):
                transition(self.a, draft.pk, state)
        with self.assertRaises(ValidationError):
            analysis.review(self.a, self.c.pk, 'mapping', draft.pk, 'Finance', 'approve',
                self.e['finance_review'].pk, 'Draft is not approved', rev(self.c))
        self.assertEqual(draft.states.order_by('-pk').first().state, 'draft')
        self.assertNotIn('id', result)
        self.assertFalse(FinanceRun.objects.filter(source=source).exists())
        self.assertEqual(active_component('D06.account_bu_maps', self.c).pk, self.configs['D06.account_bu_maps'].pk)

    def test_existing_valid_mapping_accounts_and_receipt_remain_current_and_unchanged(self):
        mapping, _, output = pipeline(self.a, self.c, self.source)
        analysis.review(self.a, self.c.pk, 'output', output.pk, 'Finance', 'approve',
            self.e['finance_review'].pk, 'Reviewed exact native result', rev(self.c))
        document = draft_report(self.a, self.c.pk, output.pk, self.template.pk, 'internal', rev(self.c))
        reserve_publication(self.a, self.c.pk, document.pk, rev(self.c))
        self.assertTrue(run_publication_once())
        before_receipt = list(PublicationReceipt.objects.values())
        before_runs = list(FinanceRun.objects.order_by('pk').values())
        draft = self.draft()
        self.preview(self.imported(), draft)
        self.assertEqual(list(PublicationReceipt.objects.values()), before_receipt)
        self.assertEqual(list(FinanceRun.objects.order_by('pk').values()), before_runs)
        analysis.ensure_current(mapping)
        analysis.ensure_current(output)
        self.assertEqual(output.result['company']['pbt']['value'], '609.99')
        self.assertFalse(analysis.certification_findings(output))

    def test_zero_unknown_duplicates_and_mismatched_convention_remain_distinct(self):
        source = self.imported([('A300', '0'), ('A300', ''), ('A200', '-120')])
        result = self.preview(source, self.draft())
        self.assertEqual([x['raw_amount'] for x in result['rows']], ['0', None, '-120'])
        self.assertEqual([x['source_line'] for x in result['rows']], [2, 3, 4])
        self.assertIn('Unknown amount; not zero', result['rows'][1]['findings'])
        self.assertIn('Repeated source account retained as separate source rows', result['rows'][0]['findings'])
        from .finance_analysis_helpers import policy
        policy(self.a, self.c, 'D06.unit_sign_currency_period', dict(self.f['conventions'], currency='USD'), self.e['policy_decision'])
        result = self.preview(source, self.draft())
        self.assertTrue(all(any('no conversion' in finding for finding in x['findings']) for x in result['rows']))
        self.assertEqual([x['raw_amount'] for x in result['rows']], ['0', None, '-120'])

    def test_entity_period_and_exact_account_are_not_guessed(self):
        maps = self.maps()
        maps += [dict(maps[0], key='other-entity', entity='other-company'),
                 dict(maps[0], key='other-period', from_period='2026-09', to_period='2026-09')]
        source = self.imported([('A200', '120'), ('a200', '1'), ('A200 extra', '2')])
        result = self.preview(source, self.draft(maps))
        self.assertEqual([x['status'] for x in result['rows']], ['ambiguous', 'unmapped', 'unmapped'])
        self.assertEqual(len(result['rows'][0]['candidate_keys']), 2)

    def test_typed_draft_records_invalid_scopes_and_duplicate_keys_still_fail_closed(self):
        source = self.imported()
        for mutation in ['invalid-treatment', 'duplicate-key', 'invalid-schema', 'foreign-scope', 'foreign-component']:
            maps = self.maps()
            if mutation == 'invalid-treatment': maps[0]['pool'] = 'not-company'
            if mutation == 'duplicate-key': maps[1]['key'] = maps[0]['key']
            draft = self.draft(maps)
            if mutation in ['invalid-schema', 'foreign-scope', 'foreign-component']:
                envelope = copy.deepcopy(draft.envelope)
                if mutation == 'invalid-schema': envelope['component_schema_ref'] = 'wrong'
                if mutation == 'foreign-scope': envelope['subject_scope']['ref'] = 'foreign'
                if mutation == 'foreign-component': envelope['component_id'] = 'D06.rule_oracle_refs'
                draft = save_draft(self.a, self.c.pk, envelope)
            with self.subTest(mutation=mutation), self.assertRaises(ValidationError): self.preview(source, draft)
        self.assertFalse(FinanceRun.objects.exists())

    def test_active_validated_cross_case_and_stale_source_or_revision_are_rejected(self):
        source = self.imported()
        with self.assertRaises(ValidationError): self.preview(source, self.configs['D06.account_bu_maps'])
        draft = self.draft(self.maps()[:1])
        transition(self.a, draft.pk, 'validated')
        with self.assertRaises(ValidationError): self.preview(source, draft)
        draft = self.draft()
        other_actor, other = setup_case(username='other-case')
        with self.assertRaises(ValidationError):
            preview_mapping_draft(other_actor, other.pk, source.pk, draft.pk, rev(other))
        other_evidence = add_evidence(other_actor, other.pk, 'policy_decision', 'Other case owner decision', 'synthetic:other-case')
        foreign = draft_finance_policy(other_actor, other.pk, 'D06.account_bu_maps', self.maps(),
            other_evidence.pk, timezone.now()-timedelta(days=1))
        with self.assertRaises(ValidationError): self.preview(source, foreign)
        forged = save_draft(self.a, self.c.pk, dict(draft.envelope, value=foreign.envelope['value']))
        with self.assertRaisesMessage(ValidationError, 'Registered domain reference is missing'):
            self.preview(source, forged)
        with self.assertRaises(ValidationError):
            preview_mapping_draft(self.a, self.c.pk, source.pk, draft.pk, rev(self.c)-1)
        analysis.capture_source(self.a, self.c.pk, source.batch_id, 'synthetic-company', 'accrual',
            timezone.now()-timedelta(minutes=30), 'complete', None, self.e['finance_source'].pk, rev(self.c))
        with self.assertRaises(ValidationError): self.preview(source, draft)

    def test_deterministic_agent_and_post_are_read_only_repeatable_and_not_cached(self):
        source, draft = self.imported(), self.draft()
        expected = rev(self.c)
        with CaptureQueriesContext(connection) as queries:
            result = investigate_mapping_draft(self.a, self.c.pk, source.pk, draft.pk, expected)
        self.assertFalse(any(query['sql'].lstrip().split()[0].upper() in ['INSERT', 'UPDATE', 'DELETE'] for query in queries))
        self.assertEqual(result, investigate_mapping_draft(self.a, self.c.pk, source.pk, draft.pk, expected))
        self.client.force_login(self.a)
        url = f'/cases/{self.c.pk}/finance/'
        from apps.finance.forms import commands
        form = next(item['form'] for item in commands(self.c) if item['action'] == 'diagnose_mapping')
        self.assertIn(draft.pk, list(form.fields['configuration'].queryset.values_list('pk', flat=True)))
        self.assertNotIn(self.configs['D06.account_bu_maps'].pk,
            list(form.fields['configuration'].queryset.values_list('pk', flat=True)))
        payload = {'action':'diagnose_mapping', 'source':source.pk, 'configuration':draft.pk, 'revision':expected}
        for _ in range(2):
            response = self.client.post(url, payload)
            self.assertContains(response, 'DRAFT only: mapping exceptions')
            self.assertContains(response, 'UNMAPPED_ACCOUNT: A300')
            self.assertContains(response, 'AMBIGUOUS_MAPPING: A200')
            self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertNotContains(self.client.get(url), 'DRAFT only: mapping exceptions')
        self.assertEqual(rev(self.c), expected)
        self.assertFalse(FinanceRun.objects.exists())

    def test_current_actor_grants_checked_without_private_diagnostic_leak(self):
        source, draft = self.imported(), self.draft()
        self.client.force_login(self.a)
        url = f'/cases/{self.c.pk}/finance/'
        for action in ['case.read', 'finance.read', 'policy.read', 'finance.calculate', 'agent.finance']:
            Grant.objects.filter(case=self.c, user=self.a, action=action).update(active=False)
            with self.subTest(action=action), self.assertRaises(PermissionDenied):
                investigate_mapping_draft(self.a, self.c.pk, source.pk, draft.pk, rev(self.c))
            response = self.client.post(url, {'action':'diagnose_mapping', 'source':source.pk,
                'configuration':draft.pk, 'revision':rev(self.c)})
            self.assertIn(response.status_code, [403, 404])
            self.assertNotIn(b'A300', response.content)
            Grant.objects.filter(case=self.c, user=self.a, action=action).update(active=True)
        self.assertFalse(FinanceRun.objects.exists())

    def test_conflict_free_draft_is_still_not_authoritative_and_resolves_only_after_normal_review(self):
        source = self.imported([('A200', '120')])
        draft = self.draft(self.maps()[:1])
        result = self.preview(source, draft)
        self.assertEqual(result['rows'][0]['status'], 'single_candidate')
        self.assertEqual(result['exceptions'], [])
        self.assertFalse(result['authoritative'])
        transition(self.a, draft.pk, 'validated')
        transition(self.a, draft.pk, 'active')
        analysis.review(self.a, self.c.pk, 'mapping', draft.pk, 'Finance', 'approve',
            self.e['finance_review'].pk, 'Reviewed corrected exact mapping', rev(self.c))
        with self.assertRaises(ValidationError): self.preview(source, draft)
        mapped = analysis.map_source(self.a, self.c.pk, source.pk, [], rev(self.c))
        self.assertEqual(mapped.result['status'], 'complete')
        self.assertEqual(mapped.result['rows'][0]['amount'], '120')
