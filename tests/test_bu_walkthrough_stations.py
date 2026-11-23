"""Verify the isolated Business Unit browser stations against native services."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.finance.bu_models import BUReport, BUWork
from apps.workflows import factory, factory_bu as bu, factory_progress
from apps.workflows.models import FactoryAttempt, FactoryProgress, FactoryWork
from tests import railway_bu_walkthrough_seed as seed
from tests.helpers import rev


ENVIRONMENT = {'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
               'PSL_COMPOSED_WALKTHROUGH': '1'}


class BUWalkthroughStationTests(TestCase):
    def setUp(self):
        self.reviewer = get_user_model().objects.create_user('psl-agent-trial')
        self.client.force_login(self.reviewer)

    @patch.dict('os.environ', ENVIRONMENT)
    def test_only_actual_matching_lease_shows_live_investigation_to_source_reader(self):
        sample = seed.prepare('live')
        work = FactoryWork.objects.get(pk=sample['work'])
        path = sample['path']
        label = 'Investigating the selected business-unit sources and exception rules.'
        self.assertNotContains(self.client.get(path), label)
        self.assertEqual(seed.prepare('live')['work'], work.pk)

        def inspect_during_claim(seconds):
            self.assertEqual(seconds, seed.OBSERVATION_SECONDS)
            self.assertContains(self.client.get(path), label)
            self.assertNotContains(self.client.get(reverse('factory_invoice_decision', args=[work.pk])), label)
            claim = FactoryAttempt.objects.get(activity__work=work, activity__kind='ACT03', phase='started')
            self.assertFalse(FactoryAttempt.objects.filter(activity=claim.activity, phase='observed').exists())
            self.assertFalse(FactoryProgress.objects.filter(work=work).exists())

        with patch.object(seed, 'sleep', side_effect=inspect_during_claim) as window:
            result = seed.observe(work.pk)
        window.assert_called_once_with(seed.OBSERVATION_SECONDS)
        self.assertFalse(result['private_payloads'])
        self.assertNotContains(self.client.get(path), label)
        with self.assertRaisesMessage(RuntimeError, 'fresh sample'):
            seed.observe(work.pk)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertEqual(bu.report(work)['stage'], 'result_review')

    @patch.dict('os.environ', ENVIRONMENT)
    def test_phone_observation_uses_an_independent_work_and_existing_claim(self):
        earlier = seed.prepare('live')
        sample = seed.prepare('live-retry')
        self.assertNotEqual(sample['case'], earlier['case'])
        self.assertNotEqual(sample['work'], earlier['work'])
        label = 'Investigating the selected business-unit sources and exception rules.'

        def inspect_during_claim(seconds):
            self.assertEqual(seconds, seed.PHONE_OBSERVATION_SECONDS)
            self.assertContains(self.client.get(sample['path']), label)
            self.assertNotContains(self.client.get(earlier['path']), label)

        with patch.object(seed, 'sleep', side_effect=inspect_during_claim):
            result = seed.observe(sample['work'], 'live-retry')
        self.assertFalse(result['private_payloads'])
        self.assertNotContains(self.client.get(sample['path']), label)
        self.assertFalse(FactoryAttempt.objects.filter(activity__work_id=earlier['work']).exists())

    @patch.dict('os.environ', ENVIRONMENT)
    def test_return_keeps_original_result_and_requires_independent_review_of_different_exception(self):
        sample = seed.prepare('return')
        work = FactoryWork.objects.get(pk=sample['work'])
        original = bu.result(work)
        decision = sample['path']
        pending = FactoryProgress.objects.get(work=work)

        def review(item, verdict, evidence, key):
            response = self.client.post(decision, {
                'action': 'review', 'revision': work.revision, 'case_revision': rev(work.case),
                'work_id': item.pk, 'purpose': item.kind, 'verdict': verdict, 'operation_key': key,
                'evidence_id': evidence,
            })
            self.assertRedirects(response, decision, fetch_redirect_response=False)

        with self.assertRaisesMessage(RuntimeError, 'independent browser return'):
            seed.prepare_replacement(work.pk)
        proof = work.case.evidence.get(kind='bu_review')
        review(original, 'return', proof.pk, 'synthetic-result-return')
        staged = seed.prepare_replacement(work.pk)
        self.assertEqual(seed.prepare_replacement(work.pk)['replacement'], staged['replacement'])
        prior_rule = BUWork.objects.get(pk=staged['original_rule'])
        replacement = BUWork.objects.get(pk=staged['replacement'])
        self.assertEqual(replacement.reference, prior_rule.reference)
        self.assertNotEqual(replacement.payload['weights'], prior_rule.payload['weights'])
        self.assertFalse(replacement.reviews.exists())
        response = self.client.post(sample['recovery_path'], {
            'action': 'correct', 'revision': work.revision, 'case_revision': rev(work.case), 'mode': 'staff',
            'payroll_id': replacement.payroll_id, 'rule_ids': [replacement.pk], 'reason': 'Select the corrected exception.',
        })
        self.assertRedirects(response, sample['recovery_path'], fetch_redirect_response=False)
        work.refresh_from_db()
        self.assertIsNone(bu.result(work))
        self.assertEqual(bu.report(work)['stage'], 'source_review')
        self.assertContains(self.client.get(decision), 'Review exception rule')
        review(replacement, 'approve', staged['proof'], 'synthetic-replacement-rule-approve')

        for _ in range(15):
            self.assertEqual(factory_progress.run_once(), pending.pk)
            pending.refresh_from_db()
            if pending.status == 'waiting':
                break
        self.assertEqual(pending.status, 'waiting')
        self.assertEqual(pending.requested_by_id, work.actor_id)
        work.refresh_from_db()
        successor = bu.result(work)
        self.assertIsNotNone(successor, work.finding)
        self.assertNotEqual(successor.pk, original.pk)
        self.assertNotEqual(successor.payload['by_bu'], original.payload['by_bu'])
        self.assertEqual(successor.metadata['rule_ids'], [replacement.pk])
        self.assertFalse(successor.reviews.exists())
        review(successor, 'approve', staged['proof'], 'synthetic-replacement-result-approve')
        self.assertEqual(bu.report(work)['stage'], 'publish')
        self.assertEqual(original.reviews.get().verdict, 'return')
        self.assertFalse(BUReport.objects.filter(work__case_id=work.case_id).exists())
