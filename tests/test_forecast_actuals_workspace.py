from decimal import Decimal
import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.core.evidence_access import public_timeline
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.finance import forecast, forecast_actuals
from apps.finance.models import ForecastActualVerification, ForecastMatch, ForecastMatchReversal, ForecastRun
from apps.identity.models import Grant
from apps.policy.services import active_component, register_reference, transition
from tests import railway_forecast_actuals_walkthrough_seed as specimen
from tests.billing_helpers import evidence, policy
from tests.forecast_helpers import actual, fixture, payload, scenario
from tests.helpers import activate, rev


class ForecastActualsWorkspaceTests(TestCase):
    def setUp(self):
        self.reporter, self.case, self.policy = fixture()
        source = payload(self.reporter, self.case)
        sample = source['items'][0]
        source['items'] += [{**sample, 'key': 'missing-payroll', 'kind': 'outflow',
                            'source_ref': 'sample-missing-payroll', 'amount': None}]
        self.scenario = scenario(self.reporter, self.case, source, reference='SAMPLE-ACTUALS-COMPARISON')
        self.month, self.next_month = source['months']
        self.path = reverse('finance_forecast_actuals', args=[self.case.pk, self.scenario.pk])
        self.url = f'{self.path}?month={self.month}'
        self.reader = get_user_model().objects.create_user(username='sample-forecast-reader')
        self.verifier = get_user_model().objects.create_user(username='sample-forecast-verifier')
        for actor, actions in ((self.reader, ('case.read', 'finance.read')),
                               (self.verifier, ('case.read', 'finance.read', 'finance.forecast.actual_verify',
                                                'finance.forecast.match', 'evidence.add'))):
            Grant.objects.bulk_create([Grant(case=self.case, user=actor, action=action) for action in actions])
        owner = evidence(self.reporter, self.case, 'policy_decision', 'Separate fictional actual verifier')
        assignment = active_component('D05.role_principal_assignments', self.case)
        reference = register_reference(self.reporter, self.case.pk, 'forecast-actuals:verifier',
            'schema:psl/role-assignment/v1', {'role': 'Finance', 'user_id': self.verifier.pk}, owner.pk)
        activate(self.reporter, self.case, 'D05.role_principal_assignments', [*assignment.envelope['value'], reference.ref], owner)
        policy(self.reporter, self.case, forecast.METHOD, {**self.policy, 'distinct_actual_reporter': True})

    def post(self, action, **fields):
        return self.client.post(self.url, {'action': action, 'revision': rev(self.case), **fields})

    def test_independent_review_match_and_reversal_keep_original_version_and_note(self):
        reported = actual(self.reporter, self.case, '15', transaction='sample-part-receipt', verified=False)
        unknown = actual(self.reporter, self.case, None, direction='outflow', transaction='sample-payroll', verified=False)
        run = forecast.prepare(self.reporter, self.case.pk, self.scenario.pk, rev(self.case))
        review = evidence(self.reporter, self.case, 'forecast_review', 'Fictional selected month review')
        forecast.review(self.reporter, self.case.pk, run.pk, 'Finance', 'approve', review.pk,
                        'Original forecast approved independently of later actuals.', rev(self.case))
        source = add_evidence(self.verifier, self.case.pk, 'forecast_actual_verification', json.dumps(reported.payload),
                              'supplied-independent-confirmation')
        match_proof = add_evidence(self.verifier, self.case.pk, 'forecast_match', 'Exact synthetic match proof', 'supplied-month-review')

        self.client.force_login(self.reporter)
        page = self.client.get(self.url)
        self.assertContains(page, 'sample-part-receipt')
        self.assertContains(page, 'sample-payroll')
        self.assertNotContains(page, 'Verify reported actual')
        self.assertEqual(self.post('verify', actual=reported.pk, role='Finance', evidence=source.pk).status_code, 403)
        reason = 'Awaiting an independent check of the part-payment.'
        invalid = self.post('note', item='receipt-1', actual=unknown.pk, reason=reason)
        self.assertContains(invalid, 'matching direction and scope')
        self.assertRedirects(self.post('note', item='receipt-1', actual=reported.pk, reason=reason), self.url)
        entry = self.case.audit.get(action=forecast_actuals.NOTE)
        self.assertEqual((entry.data['actual'], entry.data['item'], entry.data['actual_evidence_sha256']),
                         (reported.pk, 'receipt-1', reported.evidence.sha256))
        self.assertRedirects(self.post('note', item='receipt-1', actual=reported.pk, reason=reason), self.url)
        self.assertEqual(self.case.audit.filter(action=forecast_actuals.NOTE).count(), 1)
        self.assertFalse(public_timeline(self.case).filter(pk=entry.pk).exists())
        with self.assertRaisesMessage(DatabaseError, 'PSL immutable history'), transaction.atomic():
            self.case.audit.filter(pk=entry.pk).update(data={})
        self.assertFalse(ForecastMatch.objects.filter(case=self.case).exists())

        self.client.force_login(self.verifier)
        self.assertRedirects(self.post('verify', actual=reported.pk, role='Finance', evidence=source.pk), self.url)
        self.assertEqual(ForecastActualVerification.objects.get(actual=reported).actor_id, self.verifier.pk)
        self.assertRedirects(self.post('match', item='receipt-1', actual=reported.pk, amount='15', evidence=match_proof.pk,
                           operation='forecast-match-' + '1'*32), self.url)
        matched = ForecastMatch.objects.get(case=self.case, actual=reported)
        page = self.client.get(self.url)
        self.assertEqual([(r['actual'], r['status']) for r in page.context['projection']['rows']],
                         [(Decimal('15'), 'Part matched'), (None, 'Awaiting match')])
        self.assertContains(page, reason)
        self.assertRedirects(self.post('unmatch', match=matched.pk, evidence=match_proof.pk,
                             reason='Remove the proposed match; the source stays verified.'), self.url)
        self.assertTrue(ForecastMatchReversal.objects.filter(match=matched, actor=self.verifier).exists())
        self.assertContains(self.client.get(self.url), 'Remove the proposed match; the source stays verified.')
        self.assertContains(self.client.get(self.url), reason)
        run.refresh_from_db()
        self.assertEqual(ForecastRun.objects.filter(scenario=self.scenario).count(), 1)
        self.assertEqual(run.forecastreview_set.count(), 1)

    def test_scoped_reads_and_missing_rules_hold_only_financial_commands(self):
        recorded = actual(self.reporter, self.case, '10', transaction='sample-correct-month', verified=False)
        outside_value = {**recorded.payload, 'transaction': 'hidden-other-account', 'account': 'other-account'}
        outside_proof = evidence(self.reporter, self.case, 'forecast_actual', json.dumps(outside_value))
        outside = forecast.capture_actual(self.reporter, self.case.pk, outside_proof.pk, rev(self.case))
        self.client.force_login(self.reader)
        page = self.client.get(self.url)
        self.assertNotContains(page, 'hidden-other-account')
        self.assertNotContains(page, 'Leave unmatched with a note')
        self.assertNotContains(page, 'Record a supplied receipt or payment')
        self.assertEqual(self.post('note', item='receipt-1', actual=recorded.pk, reason='No write access.').status_code, 403)
        self.assertNotContains(self.client.get(f'{self.path}?month={self.next_month}'), 'sample-correct-month')
        with self.assertNumQueries(6):
            summary = forecast_actuals.monthly(self.reader, self.case, self.scenario, self.month)
        self.assertEqual([a.pk for a in summary['actuals']], [recorded.pk])

        self.client.force_login(self.reporter)
        current = active_component(forecast.METHOD, self.case)
        transition(self.reporter, current.pk, 'revoked')
        self.assertContains(self.client.get(self.url), 'Set up the forecast matching rules')
        self.assertRedirects(self.post('note', item='receipt-1', actual=recorded.pk, reason='Matching rule is missing.'), self.url)
        self.assertContains(self.post('note', item='receipt-1', actual=outside.pk, reason='Mismatched source.'),
                            'Select a valid choice')
        self.assertFalse(ForecastMatch.objects.filter(case=self.case).exists())
        self.assertEqual(self.case.audit.get(action=forecast_actuals.NOTE).data['actual'], recorded.pk)


class ForecastActualsWalkthroughFixtureTests(TestCase):
    def test_exact_guarded_browser_sample_preserves_pending_actuals(self):
        trial = get_user_model().objects.create_user(username='psl-agent-trial')
        with patch.dict(os.environ, {specimen.GUARD: '0'}), self.assertRaises(RuntimeError):
            specimen.prepare()
        self.assertFalse(Case.objects.filter(pk=specimen.CASE).exists())
        with patch.dict(os.environ, {specimen.GUARD: '1'}):
            prepared = specimen.prepare()
            self.assertTrue(specimen.prepare()['preserved'])
        case = Case.objects.get(pk=prepared['case'], synthetic=True, tenant=specimen.TENANT)
        self.assertEqual(set(Grant.objects.filter(user=trial).values_list('case_id', flat=True)), {case.pk})
        self.assertFalse(prepared['part_note_recorded'])
        self.assertFalse(prepared['part_already_verified'])
        self.assertEqual(ForecastMatch.objects.filter(case=case).count(), 1)
        self.client.force_login(trial)
        page = self.client.get(prepared['path'])
        self.assertContains(page, 'SAMPLE-CURRENT-PART')
        self.assertContains(page, 'SAMPLE-PAYROLL-UNKNOWN')
        self.assertContains(page, 'Verify reported actual')
        self.assertEqual([(row['actual'], row['status']) for row in page.context['projection']['rows']],
                         [(Decimal('10'), 'Matched'), (None, 'Awaiting match'), (None, 'Awaiting match')])
