"""Exercise the guarded synthetic invoice stations through scoped HTTP commands."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TransactionTestCase

from apps.finance.models import InvoiceDelivery, InvoiceIssue, InvoiceJob, InvoiceReview
from apps.policy.services import role_policy
from apps.workflows import factory
from apps.workflows.models import FactoryWork, HumanTask
from tests import railway_invoice_walkthrough_seed as seed


ENVIRONMENT = {'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
               'PSL_COMPOSED_WALKTHROUGH': '1'}


class InvoiceWalkthroughStationTests(TransactionTestCase):
    def setUp(self):
        self.trial = get_user_model().objects.create_user('psl-agent-trial')
        self.client.force_login(self.trial)

    @patch.dict('os.environ', ENVIRONMENT)
    def test_independent_delegate_only_decides_exact_packet_without_release_authority(self):
        sample = seed.prepare_delegation()
        self.assertEqual(seed.prepare_delegation()['work'], sample['work'])
        work = FactoryWork.objects.get(pk=sample['work'])
        task = HumanTask.objects.get(pk=sample['task'])
        with self.assertRaises(PermissionDenied):
            role_policy(self.trial, work.case, 'Finance')
        scope = self.client.get(sample['delegation_path'])
        self.assertContains(scope, 'Invoice review')
        self.assertNotContains(scope, 'Save for review')
        self.assertContains(self.client.get(sample['decision_path']), 'Your review authority: configured invoice delegate')
        response = self.client.post(sample['decision_path'], {
            'action': 'claim', 'task': task.pk, 'task_revision': task.revision,
        })
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        page = self.client.get(sample['decision_path'])
        self.assertContains(page, 'Approve exact packet')
        self.assertNotContains(page, 'Return for correction')
        self.assertNotContains(page, 'Issue and send invoice')
        response = self.client.post(sample['decision_path'], {
            'action': 'decide', 'task': task.pk, 'task_revision': task.revision, 'verdict': 'approve',
            'evidence': sample['proof'], 'reason': 'Reviewed the exact fictional invoice destination and current packet.',
        })
        self.assertEqual(response.status_code, 302)
        review = InvoiceReview.objects.get(invoice_id=sample['invoice'])
        self.assertEqual(review.actor_id, self.trial.pk)
        self.assertEqual(review.authority['D05.delegation_rules'], sample['delegation'])
        self.assertFalse(InvoiceJob.objects.filter(invoice_id=sample['invoice']).exists())

    @patch.dict('os.environ', ENVIRONMENT)
    def test_browser_lookup_miss_then_original_witness_never_sends_another_issue(self):
        sample = seed.prepare_recovery()
        self.assertEqual(seed.prepare_recovery()['job'], sample['job'])
        job = InvoiceJob.objects.get(pk=sample['job'])
        work = FactoryWork.objects.get(pk=sample['work'])
        self.assertEqual(job.status, 'unknown')
        self.assertFalse(InvoiceIssue.objects.filter(invoice=job.invoice).exists())
        with self.assertRaisesMessage(RuntimeError, 'initial lookup miss'):
            seed.reveal_original_receipt(work.pk)
        page = self.client.get(sample['path'])
        self.assertContains(page, 'Reconcile original operation')
        self.assertNotContains(page, 'Issue and send invoice')
        url = f'/api/v1/work/{work.pk}'
        state = self.client.get(url)
        self.assertEqual(state.status_code, 200, state.content)
        self.assertEqual(state.json()['state'], 'effect_uncertain')
        self.assertIn('reconcile', state.json()['actions'])
        self.assertNotIn('release_invoice', state.json()['actions'])
        response = self.client.post(url + '/actions', {'action': 'reconcile', 'expected_revision': work.revision},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 202, response.content)
        job.refresh_from_db()
        self.assertEqual(job.status, 'unknown')
        self.assertFalse(InvoiceIssue.objects.filter(invoice=job.invoice).exists())
        self.assertNotIn('release_invoice', self.client.get(url).json()['actions'])
        recovered = seed.reveal_original_receipt(work.pk)
        self.assertEqual(recovered['operation_key'], sample['operation_key'])
        self.assertEqual(seed.reveal_original_receipt(work.pk)['original_receipt'], recovered['original_receipt'])
        work.refresh_from_db()
        self.assertEqual(work.status, 'ready')
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertEqual(work.status, 'verified', work.finding)
        issue = InvoiceIssue.objects.get(invoice=job.invoice)
        self.assertEqual(issue.pk, recovered['original_receipt'])
        self.assertEqual(issue.job_id, job.pk)
        self.assertEqual(InvoiceJob.objects.filter(invoice=job.invoice, kind='issue').count(), 1)
        delivery = InvoiceDelivery.objects.get(invoice=job.invoice)
        readback = self.client.get(url).json()
        self.assertEqual(readback['state'], 'verified')
        result = self.client.get(readback['output_url'])
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual((result.json()['issue_id'], result.json()['delivery_id']), (issue.pk, delivery.pk))
