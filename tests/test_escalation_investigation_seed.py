from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TestCase

from apps.agents.models import AgentRun
from apps.core.models import Audit, Case
from apps.documents.models import Publication, PublicationReceipt
from apps.identity.models import Grant
from apps.pmo.models import EscalationDecision, EscalationRequest, Issue
from apps.workflows import factory_escalation
from apps.workflows.models import FactoryAttempt, FactoryWork
from tests import railway_escalation_investigation_seed as seed
from tests.helpers import rev


class EscalationInvestigationFixtureTests(TestCase):
    def test_live_exact_issue_clock_reaches_separate_trial_refusal_without_delivery(self):
        self.assertEqual(connection.vendor, 'postgresql')
        trial = get_user_model().objects.create_user(seed.TRIAL)
        sample = seed.prepare()
        self.assertEqual(seed.prepare(), {**sample, 'preserved': True})
        work = FactoryWork.objects.select_related('case').get(pk=sample['work'])
        case = Case.objects.get(pk=seed.CASE_ID)
        request = EscalationRequest.objects.get(pk=sample['request'])
        self.assertNotEqual(work.actor_id, trial.pk)
        self.client.force_login(trial)
        text = 'Investigating the blocker and who needs to decide.'
        starting = self.client.get(sample['path'])
        self.assertNotContains(starting, text)
        self.assertContains(starting, seed.REFERENCE)
        self.assertNotContains(starting, seed.OTHER_REFERENCE)

        def observe_live(seconds):
            self.assertEqual(seconds, seed.WINDOW_SECONDS)
            work.refresh_from_db()
            claim = FactoryAttempt.objects.get(activity__work=work, activity__kind='ACT03', phase='started', fence=work.fence)
            native = claim.observation['native']
            self.assertEqual((native['request'], native['profile'], native['issue_state']),
                             (sample['request'], sample['profile'], sample['issue_state']))
            self.assertEqual(native['timing']['acknowledgement_status'], 'OVERDUE')
            self.assertTrue(native['timing']['client_24h'])
            page = self.client.get(sample['path'])
            self.assertContains(page, text)
            self.assertContains(page, 'data-work-watch')
            self.assertContains(page, 'Acknowledgement: OVERDUE.')
            self.assertContains(page, 'Client-dependent 24-hour threshold: Reached.')
            self.assertContains(page, seed.REFERENCE)
            self.assertNotContains(page, seed.OTHER_REFERENCE)
            self.assertNotContains(page, 'Decline client communication')
            with transaction.atomic():
                Grant.objects.filter(user=trial, case=case, action='issue.read').update(active=False)
                restricted = self.client.get(sample['path'])
                self.assertIn(restricted.status_code, (403, 404))
                self.assertNotContains(restricted, seed.REFERENCE, status_code=restricted.status_code)
                transaction.set_rollback(True)
            self.assertFalse(request.decisions.exists())
            self.assertFalse(AgentRun.objects.filter(case=case, provider='deterministic-escalation-investigation-v1').exists())

        with patch.object(seed, 'sleep', side_effect=observe_live) as pause:
            result = seed.observe(work.pk)
        pause.assert_called_once_with(seed.WINDOW_SECONDS)
        self.assertEqual(result['request'], sample['request'])
        self.assertEqual(result['issue'], sample['issue'])
        waiting = self.client.get(sample['path'])
        self.assertNotContains(waiting, text)
        self.assertContains(waiting, 'Decline client communication', count=1)
        self.assertContains(waiting, 'Head of PMO')
        self.assertContains(waiting, 'No recorded communication receipt.')
        self.assertFalse(request.decisions.exists())
        work.refresh_from_db()
        self.assertEqual(work.status, 'waiting')
        self.assertIsNone(work.lease_until)

        stale = {'action': 'decision', 'revision': work.revision, 'case_revision': rev(case),
                 'request': sample['other_request'], 'role': seed.ROLE, 'verdict': 'reject',
                 'note': 'The synthetic dependency can be handled internally.'}
        rejected = self.client.post(sample['path'], stale)
        self.assertNotEqual(rejected.status_code, 302)
        self.assertFalse(request.decisions.exists())
        self.assertFalse(EscalationDecision.objects.filter(request_id=sample['other_request']).exists())
        exact = {**stale, 'request': sample['request']}
        self.assertEqual(self.client.post(sample['path'], exact).status_code, 302)
        decision = EscalationDecision.objects.get(request=request)
        self.assertEqual((decision.actor_id, decision.role, decision.verdict), (trial.pk, seed.ROLE, 'reject'))
        self.assertEqual(decision.authority['D05.decision_action_matrix'], sample['decision_rule'])
        after = self.client.get(sample['path'])
        self.assertContains(after, 'Not escalated')
        self.assertContains(after, 'No recorded communication receipt.')
        self.assertNotContains(after, 'Approve client communication')
        self.assertEqual(Issue.objects.get(pk=sample['issue']).current.status, 'Open')
        self.assertIsNone(factory_escalation.document(work))
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())
        self.assertFalse(PublicationReceipt.objects.filter(publication__factory_work=work).exists())
        self.assertEqual(Audit.objects.filter(case=case, action=seed.OBSERVATION).count(), 1)
        with self.assertRaisesMessage(RuntimeError, 'fresh exact escalation claim'):
            seed.observe(work.pk)
