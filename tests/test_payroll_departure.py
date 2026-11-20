import json
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.evidence_access import public_evidence, public_timeline
from apps.core.models import Audit, Evidence
from apps.core.services import add_evidence
from apps.finance import hrfinance, payroll, payroll_departure as timing
from apps.finance.payroll_models import PayrollPublication
from apps.identity.models import Grant
from apps.policy.models import Configuration
from apps.policy.payroll_validators import DEPARTURE_CHECK, DEPARTURE_SOURCES
from apps.policy.services import transition
from tests.helpers import rev
from tests.payroll_helpers import fixture, pipeline, policy


class PayrollDepartureTests(TestCase):
    departure = '2026-09-30T17:00:00+01:00'
    later_payment = '2026-10-02T15:00:00+01:00'
    episode = 'sample-employment-episode-A'
    transaction = 'sample-settlement-reference-A'

    def setUp(self):
        self.f = fixture()
        self.case = self.f['case']
        self.employer = self.f['owner']
        self.cash_owner = self.f['preparer']
        self.operator = self.f['reviewer']
        self.input = self.f['inputs'][0]
        row = self.input.payload['rows'][0]
        self.row, self.employee = row['row_ref'], row['employee_id']
        self.path = reverse('payroll_departure_check', args=[self.case.pk])
        self.rules = {'entity': self.f['request'].metadata['entity'],
            'employment_holder_id': self.employer.pk, 'settlement_holder_id': self.cash_owner.pk,
            'reviewer_id': self.employer.pk, 'reader_ids': [self.operator.pk],
            'comparison': 'settlement_after_effective_instant', 'proof_max_age_seconds': 3600}
        for side, kind in DEPARTURE_SOURCES.items():
            self.rules[side + '_contract_id'] = add_evidence(self.employer, self.case.pk, kind,
                'Fictional approved source contract.', 'synthetic:payroll-timing').pk

    def enable(self, **overrides):
        return policy(self.f, DEPARTURE_CHECK, {'check': {**self.rules, **overrides}})

    def fields(self, side, **overrides):
        data = {'status': timing.KNOWN[side], 'episode': self.episode, 'source_version': 'source-v1'}
        if side == 'employment':
            data.update(employee=self.employee, instant=self.departure, source_reference='sample-HR-departure')
        else:
            data.update(input_id=self.input.pk, row=self.row, instant=self.later_payment, source_reference=self.transaction)
        return {**data, **overrides}

    def record(self, side, **overrides):
        actor = self.employer if side == 'employment' else self.cash_owner
        return timing.capture(actor, self.case.pk, side, expected=rev(self.case), **self.fields(side, **overrides))

    def compare(self, payment):
        return timing.check(self.operator, self.case.pk, payment.pk, rev(self.case))

    def test_exact_payment_and_departure_reach_hr_review_without_membership_or_raw_values(self):
        self.enable()
        source = self.f['hr']
        leave_only = {**source.payload, 'source_version': 'sample-membership-with-leaver-excluded',
                      'rows': [row for row in source.payload['rows'] if row['employee_id'] != self.employee]}
        membership = hrfinance.capture(self.employer, self.case.pk, source.contract_id, 'leaver-excluded',
                                       json.dumps(leave_only), rev(self.case))
        self.assertNotIn(self.employee, {row['employee_id'] for row in membership.payload['rows']})

        self.client.force_login(self.cash_owner)
        response = self.client.post(self.path, {'action': 'settlement', 'revision': rev(self.case),
            **self.fields('settlement')}, follow=True)
        self.assertContains(response, 'Private source evidence')
        payment = Audit.objects.get(case=self.case, action=timing.FACT, data__side='settlement')
        self.assertEqual(self.compare(payment).data['result'], 'awaiting_evidence')

        self.client.force_login(self.employer)
        self.assertContains(self.client.get(self.path), 'Record employment evidence')
        self.assertNotContains(self.client.get(self.path), 'Record payment evidence')
        self.assertRedirects(self.client.post(self.path, {'action': 'employment', 'revision': rev(self.case),
            **self.fields('employment')}), self.path, fetch_redirect_response=False)

        self.client.force_login(self.operator)
        response = self.client.post(self.path, {'action': 'check', 'revision': rev(self.case),
                                               'settlement_id': payment.pk}, follow=True)
        self.assertContains(response, 'The recorded payment settled after the recorded departure.')
        self.assertNotContains(response, 'Acknowledge this finding')
        self.assertIn('no-store', response['Cache-Control'])
        finding = response.context['comparison']['id']
        hidden = [self.departure, self.later_payment, self.episode, self.transaction, self.employee]
        for value in hidden:
            self.assertNotContains(response, value)
        self.assertEqual(self.client.post(self.path, {'action': 'review', 'revision': rev(self.case),
                                                     'check_id': finding}).status_code, 403)

        self.client.force_login(self.employer)
        check_path = f'{self.path}?check={finding}'
        self.assertContains(self.client.get(check_path), 'Acknowledge this finding')
        for _ in range(2):
            response = self.client.post(self.path, {'action': 'review', 'revision': rev(self.case),
                                                   'check_id': finding}, follow=True)
            self.assertContains(response, 'HR acknowledged this exact finding.')
        self.assertEqual(Audit.objects.filter(action=timing.REVIEW, case=self.case).count(), 1)
        for value in hidden:
            self.assertNotContains(response, value)
        self.client.force_login(self.f['manager'])
        self.assertNotContains(self.client.get(check_path), 'Recorded timing check')
        self.assertNotContains(self.client.get(self.path), 'Recorded checks')

        proofs = Evidence.objects.filter(case=self.case, kind=timing.KIND)
        self.assertEqual(proofs.count(), 2)
        self.assertFalse(public_evidence(proofs).exists())
        self.assertFalse(public_timeline(self.case).filter(action__in=[timing.FACT, timing.CHECK, timing.REVIEW]).exists())
        self.assertFalse(PayrollPublication.objects.filter(request__case=self.case).exists())
        revised = self.record('settlement', status='reversed', instant=None, source_version='source-v2')
        with self.assertRaisesMessage(ValidationError, 'evidence was corrected'):
            timing.readback(self.employer, self.case.pk, finding)
        self.assertEqual(self.compare(revised).data['result'], 'inconclusive')
        self.assertTrue(Audit.objects.filter(action=timing.REVIEW, case=self.case, data__comparison=finding).exists())

    def test_only_comparable_known_instants_can_make_a_finding_and_corrections_are_fresh(self):
        self.enable()
        payment = self.record('settlement')
        self.record('employment', episode='different-employment-episode')
        self.assertEqual(self.compare(payment).data['result'], 'awaiting_evidence')
        unknown = self.record('employment', status='unknown', instant=None)
        inconclusive = self.compare(payment)
        self.assertEqual(inconclusive.data['result'], 'inconclusive')
        with self.assertRaisesMessage(ValidationError, 'both comparable source records'):
            timing.acknowledge(self.employer, self.case.pk, inconclusive.pk, rev(self.case))
        corrected = self.record('employment', instant='2026-10-02T14:00:00Z', source_version='source-v2')
        self.assertGreater(corrected.pk, unknown.pk)
        self.assertEqual(self.compare(payment).data['result'], 'on_or_before')
        with self.assertRaisesMessage(ValidationError, 'Source evidence changed'):
            timing.readback(self.employer, self.case.pk, inconclusive.pk)
        with self.assertRaisesMessage(ValidationError, 'fresh source version'):
            self.record('employment', instant=self.departure, source_version='source-v2')

        for status in ('pending', 'failed', 'unknown', 'reversed'):
            with self.subTest(status=status):
                outcome = self.record('settlement', status=status, instant=None, source_reference=f'sample-txn-{status}')
                self.assertEqual(self.compare(outcome).data['result'], 'inconclusive')
        with self.assertRaisesMessage(ValidationError, 'employee, episode and original payroll row'):
            self.record('settlement', episode='different-employment-episode', source_version='source-v2')
        for invalid in ('2026-09-30', '2026-09-30T17:00:00', '2026-09-30T17:00:00-00:00',
                        (timezone.now() + timedelta(days=1)).isoformat()):
            with self.assertRaises(ValidationError):
                self.record('employment', instant=invalid, source_version='source-v3')
        with self.assertRaisesMessage(ValidationError, 'current, unambiguous row'):
            self.record('settlement', row='nonexistent-row', source_version='source-v2')

    def test_current_authority_and_source_contract_are_required_before_private_bodies(self):
        configuration = self.enable()
        self.record('employment')
        payment = self.record('settlement')
        finding = self.compare(payment)
        for actor, action in ((self.employer, 'hrfinance.capture'), (self.cash_owner, 'evidence.add'),
                              (self.operator, 'payroll.private.read')):
            grant = Grant.objects.filter(case=self.case, user=actor, action=action)
            grant.update(active=False)
            try:
                with patch.object(timing, 'proof_instant', side_effect=AssertionError('Private bodies are unavailable')):
                    with self.assertRaises(PermissionDenied):
                        self.compare(payment)
                    with self.assertRaises(PermissionDenied):
                        timing.readback(self.employer, self.case.pk, finding.pk)
            finally:
                grant.update(active=True)
        with patch.object(timing, 'proof_instant', side_effect=AssertionError('Stale contract cannot open proof')):
            add_evidence(self.employer, self.case.pk, DEPARTURE_SOURCES['employment'],
                         'Revised fictional source contract.', 'synthetic:payroll-timing')
            with self.assertRaises(ValidationError):
                self.compare(payment)
        self.assertEqual(configuration.component, DEPARTURE_CHECK)
        self.assertTrue(Audit.objects.filter(pk=finding.pk, case=self.case, action=timing.CHECK).exists())

    def test_optional_setting_does_not_change_an_existing_reviewed_payroll_report(self):
        self.client.force_login(self.operator)
        self.assertContains(self.client.get(self.path), 'Payroll matching can continue.')
        _, prior_match, _, report = pipeline(self.f, 'payroll-timing-legacy')
        existing = payroll.read_publication(self.f['manager'], report.pk)
        with self.assertRaises(ValidationError):
            self.enable(reviewer_id=self.cash_owner.pk)
        with self.assertRaises(ValidationError):
            self.enable(employment_contract_id=self.rules['settlement_contract_id'])
        self.client.force_login(self.employer)
        contract_ref = 'sample-reviewed-employment-source-v2'
        response = self.client.post(self.path, {'action': 'source', 'side': 'employment', 'document_ref': contract_ref,
                                                'revision': rev(self.case)}, follow=True)
        self.assertContains(response, 'Approved source reference')
        current_contract = self.case.evidence.filter(kind=DEPARTURE_SOURCES['employment']).latest('version')
        self.assertFalse(public_evidence(Evidence.objects.filter(pk=current_contract.pk)).exists())
        self.assertNotContains(response, contract_ref)
        self.rules['employment_contract_id'] = current_contract.pk
        configurations = Configuration.objects.filter(case=self.case, component=DEPARTURE_CHECK)
        prior_draft_ids = list(configurations.values_list('pk', flat=True))
        fields = {key: value for key, value in self.rules.items() if key not in ('comparison', 'proof_max_age_seconds')}
        result = self.client.post(self.path, {'action': 'policy', 'revision': rev(self.case), 'mode': 'check',
            'proof_hours': 1, 'decision': self.f['e']['policy_decision'].pk,
            'effective_from': (timezone.now() - timedelta(seconds=1)).isoformat(), **fields}, follow=True)
        self.assertContains(result, 'Rule draft saved.')
        self.assertContains(result, 'Payroll matching can continue.')
        draft = configurations.exclude(pk__in=prior_draft_ids).get()
        with self.assertRaises(ValidationError):
            timing.rule(self.case)
        transition(self.employer, draft.pk, 'validated')
        transition(self.employer, draft.pk, 'active')
        self.assertEqual(timing.rule(self.case)[0], draft.pk)
        self.assertEqual(payroll.read_publication(self.f['manager'], report.pk), existing)
        self.assertEqual(payroll.private_run(self.operator, self.case.pk, prior_match.pk), prior_match.result)
        policy(self.f, DEPARTURE_CHECK, {'check': None})
        self.assertEqual(payroll.read_publication(self.f['manager'], report.pk), existing)
        with self.assertRaises(ValidationError):
            self.record('employment')
