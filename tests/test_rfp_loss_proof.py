"""Source-bound customer loss reasons and optional, permission-scoped debriefs."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo import rfp, rfp_loss
from apps.pmo.meetings import record_meeting
from apps.pmo.models import ActionItem, RFPDisposition, RFPOutcome
from apps.policy.models import Configuration
from apps.policy import scopes
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.rfp_loss_validators import COMPONENT
from apps.policy.services import reference_values, transition
from apps.workflows import factory
from tests import factory_rfp_helpers as helpers
from tests.helpers import rev


class RFPLossProofTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = helpers.configured()
        cls.work = helpers.start(cls.data)
        response, _ = helpers.reviewed_document(cls.data, cls.work)
        factory.run_until_wait(cls.work.pk)
        cls.submission = response.submissions.get()

    def setUp(self):
        self.actor, self.case, self.proofs = self.data['actor'], self.data['case'], self.data['evidence']
        self.url = reverse('factory_work_response', args=[self.work.pk])
        self.settings = reverse('factory_rfp_outcome_configuration', args=[self.case.pk])
        self.client.force_login(self.actor)

    def meeting(self, version_of=None, *, kind='retrospective', occurred_at=None):
        evidence = add_evidence(self.actor, self.case.pk, 'meeting_notes', 'Fictional bid debrief notes.',
                                'synthetic:loss-debrief-proof')
        return record_meeting(self.actor, self.case.pk, 'SAMPLE retrospective for the exact bid', kind,
            occurred_at or timezone.now(), 'Review lessons from the synthetic loss',
            'Original debrief lesson' if version_of is None else 'Revised debrief lesson',
            [], [], evidence.pk, rev(self.case), meeting_id=version_of)

    def catalog(self, label, key='sample-timeline'):
        configured = draft_operator_policy(self.actor, self.case.pk, COMPONENT, {'reasons': [{'key': key, 'label': label}]},
                                           self.proofs['policy_decision'].pk, timezone.now())
        transition(self.actor, configured.pk, 'validated')
        transition(self.actor, configured.pk, 'active')
        return configured

    def command(self, **extras):
        self.work.refresh_from_db()
        return {'action': 'outcome', 'revision': self.work.revision, 'case_revision': rev(self.case),
            'target': self.submission.pk, 'verdict': 'lost', 'observed_at': timezone.now().isoformat(),
            'role': 'Client', 'evidence': self.proofs['rfp_outcome'].pk, 'note': 'Actual synthetic customer loss.', **extras}

    def test_typed_catalog_and_actual_debrief_survive_verified_archive(self):
        entry = {'action': 'draft_loss_catalog', 'loss-revision': rev(self.case), 'loss-base': 0,
                 'loss-evidence': self.proofs['policy_decision'].pk}
        self.assertContains(self.client.post(self.settings, {**entry, 'loss-names': 'Sample timing\nsample timing'}),
                            'Enter each loss reason once.')
        self.assertFalse(Configuration.objects.filter(case=self.case, component=COMPONENT).exists())
        self.assertEqual(self.client.post(self.settings, {**entry, 'loss-names': 'Sample delivery timing'}).status_code, 302)
        configuration = Configuration.objects.get(case=self.case, component=COMPONENT)
        self.assertNotContains(self.client.get(self.url, {'outcome': 'lost'}), 'name="loss_reason"')
        for action in ['validated', 'active']:
            self.assertEqual(self.client.post(self.settings, {'action': action, 'configuration': configuration.pk}).status_code, 302)
        reason = reference_values(configuration)[0]['reasons'][0]
        version = self.meeting()
        offered = self.client.get(self.url, {'outcome': 'lost'})
        self.assertContains(offered, reason['label'])
        self.assertContains(offered, 'Recorded debrief (optional)')
        self.assertNotContains(self.client.get(self.url, {'outcome': 'won'}), 'name="loss_reason"')
        root = f'/api/v1/work/{self.work.pk}'
        outcome = self.client.get(root + '/bid-outcomes').json()
        recorded = self.client.post(root + '/rfp-outcome', {
            'expected_revision': outcome['expected_revision'], 'case_revision': outcome['case_revision'],
            'submission_id': self.submission.pk, 'verdict': 'lost', 'observed_at': timezone.now().isoformat(),
            'role': 'Client', 'evidence_id': self.proofs['rfp_outcome'].pk, 'note': 'Actual synthetic customer loss.',
            'loss_reason_key': reason['key'], 'loss_catalog_id': configuration.pk, 'debrief_version_id': version.pk,
        }, content_type='application/json')
        self.assertEqual(recorded.status_code, 200, recorded.content)
        loss = RFPOutcome.objects.get(submission=self.submission)
        self.assertEqual(loss.loss_reason, {**reason, 'configuration': configuration.pk})
        self.assertEqual(loss.debrief_version_id, version.pk)
        factory.run_until_wait(self.work.pk)
        self.work.refresh_from_db()
        self.assertEqual(self.work.status, 'verified', self.work.finding)
        self.assertEqual(RFPDisposition.objects.get(outcome=loss).lessons_id, self.proofs['rfp_lessons'].pk)
        result = self.client.get(root + '/bid-outcomes').json()
        self.assertEqual((result['handoff']['kind'], result['handoff']['outcome_id']), ('loss_archive', loss.pk))
        self.assertFalse(ActionItem.objects.filter(case=self.case).exists())

        self.meeting(version.meeting_id)
        self.catalog('Revised sample reason')
        authorized = self.client.get(self.url)
        self.assertContains(authorized, 'Recorded debrief proof')
        self.assertContains(authorized, 'Original debrief lesson')
        self.assertNotContains(authorized, 'Revised debrief lesson')
        self.assertContains(authorized, 'Sample delivery timing')
        reader = get_user_model().objects.create_user(username='sample-loss-no-meeting-access')
        Grant.objects.bulk_create([Grant(case=self.case, user=reader, action=action)
                                   for action in ['case.read', 'factory.read', 'rfp.read']])
        self.client.force_login(reader)
        with CaptureQueriesContext(connection) as captured:
            restricted = self.client.get(self.url)
        self.assertNotContains(restricted, 'Recorded debrief proof')
        self.assertNotContains(restricted, 'Original debrief lesson')
        self.assertFalse(any('"pmo_meetingversion"."summary"' in query['sql'] for query in captured))
        self.assertContains(restricted, 'Sample delivery timing')

    def test_stale_catalog_and_forged_debrief_refuse_without_changing_status(self):
        initial = self.catalog('Sample original timing')
        current = self.catalog('Sample current timing')
        stale = self.command(loss_reason='sample-timeline', loss_catalog=initial.pk)
        self.assertContains(self.client.post(self.url, stale), 'The loss reasons changed')
        unknown = self.command(loss_reason='sample-unlisted', loss_catalog=current.pk)
        self.assertContains(self.client.post(self.url, unknown), 'current reviewed loss list')
        wrong_type = self.meeting(kind='status')
        self.assertContains(self.client.post(self.url, self.command(debrief_version=wrong_type.pk)),
                            'current recorded debrief')
        debrief = self.meeting(wrong_type.meeting_id)
        Grant.objects.filter(case=self.case, user=self.actor, action='meeting.read').update(active=False)
        with self.assertRaises(PermissionDenied):
            rfp.outcome(self.actor, self.case.pk, self.submission.pk, 'lost', timezone.now(), 'Client',
                        self.proofs['rfp_outcome'].pk, 'Sample loss', rev(self.case), debrief_version_id=debrief.pk)
        with self.assertRaisesMessage(DatabaseError, 'exact active reviewed catalog'), transaction.atomic():
            RFPOutcome.objects.create(submission=self.submission, result='lost', observed_at=timezone.now(),
                role='Client', authority={}, evidence=self.proofs['rfp_outcome'], actor=self.actor,
                loss_reason={'configuration': current.pk, 'key': 'sample-timeline', 'label': 'Forged reason label'})
        with self.assertRaisesMessage(DatabaseError, 'current meeting access'), transaction.atomic():
            RFPOutcome.objects.create(submission=self.submission, result='lost', observed_at=timezone.now(),
                role='Client', authority={}, evidence=self.proofs['rfp_outcome'], actor=self.actor,
                debrief_version=debrief)
        self.assertFalse(self.submission.outcomes.exists())
        self.assertEqual(self.client.post(self.url, self.command()).status_code, 302)
        legacy = RFPOutcome.objects.get(submission=self.submission)
        self.assertEqual(legacy.loss_reason, {})
        self.assertIsNone(legacy.debrief_version_id)

    def test_scoped_catalog_needs_origin_read_and_cannot_be_used_after_withdrawal(self):
        origin = Case.objects.create(kind='project', tenant=self.case.tenant, synthetic=True, title='Synthetic catalog origin')
        Grant.objects.bulk_create([Grant(case=origin, user=self.actor, action=action) for action in
                                   ['case.read', 'policy.read', 'policy.configure', 'policy.activate', 'evidence.add']])
        evidence = add_evidence(self.actor, origin.pk, 'policy_decision', 'Synthetic group catalog decision',
                                 'synthetic:loss-catalog-origin')
        choices = [{'key': 'sample-shared', 'label': 'Sample shared reason'}]
        source_config = draft_operator_policy(self.actor, origin.pk, COMPONENT, {'reasons': choices},
                                               evidence.pk, timezone.now())
        transition(self.actor, source_config.pk, 'validated')
        shared = scopes.create(self.actor, source_config.pk, 'organization', origin.tenant, [])
        scopes.transition(self.actor, shared.pk, 'validated')
        scopes.transition(self.actor, shared.pk, 'active')
        local = scopes.apply(self.actor, shared.pk, self.case.pk, self.proofs['policy_decision'].pk, [])
        transition(self.actor, local.pk, 'validated')
        transition(self.actor, local.pk, 'active')
        self.assertEqual(rfp_loss.catalog(self.actor, self.case), (local, choices))
        local_reader = get_user_model().objects.create_user(username='sample-loss-local-reader')
        Grant.objects.bulk_create([Grant(case=self.case, user=local_reader, action=action)
                                   for action in ['case.read', 'rfp.read']])
        with self.assertRaises(PermissionDenied):
            rfp_loss.catalog(local_reader, self.case)
        scopes.transition(self.actor, shared.pk, 'revoked')
        posted = self.client.post(self.url, self.command(loss_reason='sample-shared', loss_catalog=local.pk))
        self.assertContains(posted, 'The loss reasons changed')
        self.assertFalse(self.submission.outcomes.exists())
