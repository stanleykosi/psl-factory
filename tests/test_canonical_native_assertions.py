"""Bounded canonical assertions; synthetic only, not whole-process acceptance."""
import copy
import json
from django.test import TestCase
from django.utils import timezone
from apps.core.services import add_evidence
from apps.pmo.models import Baseline, ChangeAuthorization, ChangeDecision
from apps.pmo.meetings import record_meeting
from apps.pmo.reporting import draft_minutes
from apps.policy.forecast_validators import chain
from .helpers import rev, project_evidence
from apps.pmo.services import prepare_baseline, decide, sign_baseline
from .meeting_helpers import meetings_fixture
from .forecast_helpers import fixture, payload, run, review
from .billing_helpers import evidence


class CanonicalNativeAssertionsTests(TestCase):
    def test_P43_M02_unapproved_scope_proposal_retains_CR_and_signed_baseline(self):
        actor, case, _, _, template, _, _, _ = meetings_fixture()
        baseline_evidence = project_evidence(actor, case)
        prepare_baseline(actor, case.pk, baseline_evidence['plan'].pk, baseline_evidence['costing'].pk, baseline_evidence['sow'].pk, rev(case))
        for role in ['PM', 'Head of PMO', 'CEO', 'PMO Lead']:
            decide(actor, case.pk, role, rev(case))
        from tests.signature_helpers import packet_for
        packet_for(actor, case, baseline_evidence)
        sign_baseline(actor, case.pk, baseline_evidence['signature'].pk, rev(case))
        baseline = list(Baseline.objects.filter(case=case).values())
        self.assertIsNotNone(baseline[0]['signed_id'])
        cr = add_evidence(actor, case.pk, 'change_request',
            'CR-SCOPE-1: proposed additional dashboard; no approval exists.', 'synthetic:CR-SCOPE-1')
        proposal = 'Proposal only: add dashboard under CR-SCOPE-1; approval pending.'
        notes = add_evidence(actor, case.pk, 'meeting_notes', proposal, 'synthetic:scope-meeting')
        self.assertFalse(ChangeDecision.objects.filter(version__change__case=case).exists())
        self.assertFalse(ChangeAuthorization.objects.filter(version__change__case=case).exists())
        meeting = record_meeting(actor, case.pk, 'SCOPE-PROPOSAL-1', 'status', timezone.now(),
            'Discuss proposed scope change', proposal, [actor.pk],
            [{'text': proposal, 'evidence_id': notes.pk, 'change_evidence_id': cr.pk}], notes.pk, rev(case))
        document = draft_minutes(actor, case.pk, meeting.meeting_id, template.pk, 'internal', rev(case))
        meeting.refresh_from_db()
        self.assertEqual(meeting.decisions, [{'text': proposal, 'evidence_id': notes.pk, 'change_evidence_id': cr.pk}])
        self.assertIn(proposal, str(document.version.payload))
        self.assertIn('change evidence #'+str(cr.pk), str(document.version.payload))
        self.assertEqual(list(Baseline.objects.filter(case=case).values()), baseline)
        self.assertFalse(ChangeDecision.objects.filter(version__change__case=case).exists())
        self.assertFalse(ChangeAuthorization.objects.filter(version__change__case=case).exists())

    def test_F37_N01_distinct_lease_L1_and_repair_R1_once_without_payment_authority(self):
        actor, case, _ = fixture()
        value = payload(actor, case)
        value['months'] = value['months'][:1]
        value['items'] = []
        sources = {}
        for key, amount, description in [('L1', '30', 'Recurring lease L1'), ('R1', '10', 'Distinct one-off repair R1')]:
            source = evidence(actor, case, 'document', description + '; approved forecast timing: ' + value['as_of'] + '; not payment approval.')
            sources[key] = source.pk
            value['items'].append({'key': key, 'kind': 'outflow', 'source_ref': ('lease:' if key == 'L1' else 'repair:') + key,
                'owner': 'synthetic-finance', 'amount': amount, 'expected_on': value['as_of'],
                'original_due': value['as_of'], 'issue_id': None, 'evidence_id': source.pk,
                'commitment': 'reported_commitment'})
        original = copy.deepcopy(value)
        result = run(actor, case, value)
        review(actor, case, result)
        result.refresh_from_db()
        self.assertEqual(result.scenario.payload, original)
        self.assertCountEqual([row['key'] for row in result.result['items']], ['L1', 'R1'])
        self.assertEqual(len(result.result['items']), 2)
        for row in result.result['items']:
            self.assertEqual(row['evidence_id'], sources[row['key']])
            self.assertEqual(row['expected_on'], value['as_of'])
            self.assertEqual(row['commitment'], 'reported_commitment')
            self.assertEqual(row['matched'], '0')
        self.assertEqual(len(set(sources.values())), 2)
        self.assertEqual(result.result['periods'][0]['outflow'], '40')
        self.assertFalse(result.result['execution_authorized'])
        self.assertFalse(result.result['full_business_cash_forecast'])

    def test_F39_N02_literal_single_cell_100_minus_60_plus_20_is_60_TEST(self):
        # Supplied operands only. This does not determine C34 sourcing/carry,
        # configure an operational rule, or clear the blocked F39-N01 oracle.
        cells = {key: {'amount': amount, 'unit': 'TEST', 'period': 'synthetic-period-1'}
                 for key, amount in [('C15', '100'), ('C33', '60'), ('C34', '20')]}
        self.assertEqual({cell['unit'] for cell in cells.values()}, {'TEST'})
        self.assertEqual({cell['period'] for cell in cells.values()}, {'synthetic-period-1'})
        before = copy.deepcopy(cells)
        # Existing native scalar operation accepts additive balance, inflow,
        # outflow. No assertion is made about where the supplied balance came from.
        c35 = chain(cells['C34']['amount'], cells['C15']['amount'], cells['C33']['amount'])
        self.assertEqual(c35, '60')
        self.assertEqual(cells, before)
