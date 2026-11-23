"""Actual team inputs keep receipts, evidence and exact effort on the bid record."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.agents.rfp import investigate_rfp
from apps.core.models import Case
from apps.identity.models import Grant
from apps.pmo import rfp
from apps.pmo.models import RFPContribution
from tests.helpers import rev
from tests.test_rfp import fixture, response


class RFPTeamInputFactTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor, cls.case, cls.evidence, _, _ = fixture()

    def setUp(self):
        self.client.force_login(self.actor)
        self.url = reverse('rfp', args=[self.case.pk])
        self.received = timezone.now().replace(microsecond=0) - timedelta(minutes=7)

    def command(self, team, evidence, **extras):
        return {'action': 'contribute', 'revision': rev(self.case), 'team': team, 'evidence': evidence,
            'received_at': timezone.localtime(self.received).strftime('%Y-%m-%dT%H:%M:%S'),
            'source_party': 'Sample department spokesperson', 'summary': 'Sample estimate supported by the selected evidence.',
            'attested': 'on', **extras}

    def test_zero_and_unknown_are_captured_separately_and_used_as_current_evidence(self):
        root = rfp.root(self.case)
        previous = root.current_intake.contributions.get(team='Engineering')
        self.assertIsNone(previous.received_at)
        with timezone.override('Africa/Lagos'):
            self.assertContains(self.client.get(self.url), 'Received at (Africa/Lagos)')
            earlier = self.command('Engineering', self.evidence['engineering_estimate'].pk, person_days='0')
            self.assertEqual(self.client.post(self.url, earlier).status_code, 302)
            refreshed = self.command('Security', self.evidence['security_estimate'].pk, person_days='')
            self.assertEqual(self.client.post(self.url, refreshed).status_code, 302)
            page = self.client.get(self.url)
            self.assertContains(page, timezone.localtime(self.received).strftime('%d %b %Y %H:%M:%S %Z'))
            self.assertContains(page, 'Sample department spokesperson')
            self.assertContains(page, 'Time unavailable')
            self.assertContains(page, 'person-days')
        zero = root.current_intake.contributions.filter(team='Engineering').latest('pk')
        unknown = root.current_intake.contributions.filter(team='Security').latest('pk')
        self.assertEqual((zero.received_at, zero.person_days), (self.received, Decimal('0.000')))
        self.assertEqual((unknown.received_at, unknown.person_days), (self.received, None))
        previous.refresh_from_db()
        self.assertIsNone(previous.received_at)
        api = f'/api/v1/received-bids/{self.case.pk}/team-inputs'
        initial = self.client.get(api).json()
        engineering = next(item for item in initial['choices'] if item['team'] == 'Engineering')
        self.assertIn(self.evidence['engineering_estimate'].pk, [row['id'] for row in engineering['proofs']])
        facts = {'revision': initial['revision'], 'team': 'Engineering', 'received_at': self.received.isoformat(),
                 'source_party': 'Sample named Engineering contributor', 'summary': 'Exact sample work with zero person-days.',
                 'person_days': '0', 'attested': True}
        self.assertEqual(self.client.post(api, {**facts, 'evidence_id': self.evidence['security_estimate'].pk},
                                          content_type='application/json').status_code, 422)
        supplied = self.client.post(api, {**facts, 'evidence_id': self.evidence['engineering_estimate'].pk},
                                    content_type='application/json')
        self.assertEqual(supplied.status_code, 201, supplied.content)
        zero = RFPContribution.objects.get(pk=supplied.json()['id'])
        items = {row['team']: row for row in self.client.get(api).json()['items']}
        self.assertEqual(items['Engineering'], supplied.json())
        self.assertEqual(items['Engineering']['person_days'], '0.000')
        self.assertIsNone(items['Security']['person_days'])
        current = response(self.actor, self.case, self.evidence)
        self.assertEqual(current.snapshot['inputs']['Engineering']['id'], zero.pk)
        self.assertEqual(current.snapshot['inputs']['Security']['id'], unknown.pk)
        investigation = investigate_rfp(self.actor, self.case.pk, rev(self.case))
        inputs = {value['team']: value for value in investigation.result['recorded_team_inputs']}
        self.assertEqual((inputs['Engineering']['person_days'], inputs['Security']['person_days']), ('0.000', None))
        self.assertEqual(inputs['Engineering']['input_id'], zero.pk)
        self.assertNotIn('source_party', inputs['Engineering'])
        self.assertNotIn('summary', inputs['Engineering'])

        stale = self.client.post(self.url, earlier)
        self.assertContains(stale, 'Stale revision')
        corrected = self.client.post(self.url, self.command('Engineering', self.evidence['engineering_estimate'].pk, person_days='2.125'))
        self.assertEqual(corrected.status_code, 302)
        self.assertEqual(root.current_intake.contributions.filter(team='Engineering').latest('pk').person_days, Decimal('2.125'))
        with self.assertRaises(ValidationError):
            rfp.current_response(self.case, current.pk)

    def test_actual_time_attestation_team_authority_and_exact_sources(self):
        root = rfp.root(self.case)
        before = root.current_intake.contributions.count()
        proof = self.evidence['engineering_estimate'].pk
        for extras in [{'received_at': ''}, {'received_at': (timezone.now()+timedelta(days=1)).isoformat()},
                       {'person_days': '-1'}, {'person_days': '1.2345'}, {'attested': ''}]:
            with self.subTest(extras=extras):
                self.assertEqual(self.client.post(self.url, self.command('Engineering', proof, **extras)).status_code, 200)
        outsider = get_user_model().objects.create_user(username='sample-bid-qa-only')
        Grant.objects.bulk_create([Grant(case=self.case, user=outsider, action=action)
                                   for action in ['case.read', 'rfp.read', 'rfp.contribute:QA']])
        self.client.force_login(outsider)
        form = next(panel['form'] for panel in self.client.get(self.url).context['commands'] if panel['action']=='contribute')
        self.assertEqual(list(form.fields['team'].choices), [('QA', 'QA')])
        with self.assertRaises(PermissionDenied):
            rfp.record_team_input(outsider, self.case.pk, 'Engineering', proof, rev(self.case), received_at=self.received,
                                  source_party='Sample source', summary='Sample input', person_days='1', attested=True)
        self.assertEqual(root.current_intake.contributions.count(), before)

    def test_postgresql_refuses_partial_or_cross_team_facts(self):
        self.assertEqual(connection.vendor, 'postgresql')
        intake = rfp.root(self.case).current_intake
        values = {'intake': intake, 'actor': self.actor, 'team': 'QA', 'received_at': self.received,
                  'source_party': 'Sample contributor', 'summary': 'A waiting test result'}
        with self.assertRaisesMessage(DatabaseError, 'Exact current team input'), transaction.atomic():
            RFPContribution.objects.create(**values, evidence=self.evidence['engineering_estimate'])
        with self.assertRaisesMessage(DatabaseError, 'rfp_team_fact_shape'), transaction.atomic():
            RFPContribution.objects.create(**{**values, 'received_at': timezone.now()+timedelta(days=1)},
                                           evidence=self.evidence['qa_estimate'])

    def test_browser_sample_stops_before_recording_dated_team_inputs(self):
        from tests.railway_rfp_team_input_seed import RECORDER_ACTIONS, prepare

        recorder = get_user_model().objects.create_user(username='sample-browser-team-recorder')
        sample = prepare(recorder)
        case = Case.objects.get(pk=sample['case'])
        bid = rfp.root(case)
        self.assertNotEqual(sample['assigned_pm'], recorder.pk)
        self.assertEqual(set(sample['grants']), RECORDER_ACTIONS)
        self.assertEqual({proof['team']: proof['person_days'] for proof in sample['proofs']},
                         {'Engineering': '2.125', 'QA': '0', 'Security': None})
        for proof in sample['proofs']:
            self.assertTrue(case.evidence.filter(pk=proof['id'], kind=rfp.TEAMS[proof['team']]).exists())
        self.assertFalse(bid.current_intake.contributions.filter(received_at__isnull=False).exists())
        self.assertFalse(bid.current_intake.contributions.filter(team='Security').exists())
        reopened = prepare(recorder)
        self.assertTrue(reopened['preserved'])
        self.assertEqual(reopened['proofs'], sample['proofs'])
