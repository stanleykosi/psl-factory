"""An admitted maker and a separate Finance reviewer use the current invoice controls."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.alert_models import AccountDelivery, AlertRead
from apps.core.models import Case
from apps.finance.models import BillingPreparation, InvoiceIssue, InvoiceJob, InvoiceReview, UsageIntakeReceipt
from apps.identity import staff
from apps.identity.models import Grant
from apps.workflows.factory_invoice_review import ASSIGNMENT_CANDIDATE_LIMIT, assigned_alerts
from apps.workflows.models import FactoryInvoicePreparationBinding, FactoryWork, HumanTask, TaskEvent
from tests import railway_admitted_schedule_seed as admission_seed
from tests import railway_invoice_admitted_review_seed as seed
from tests.helpers import rev
from tests.test_staff_profiles import configured


@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class AdmittedInvoiceReviewFixtureTests(TestCase):
    def test_exact_independent_review_returns_and_readies_a_corrected_invoice_without_release(self):
        self.assertEqual(connection.vendor, 'postgresql')
        existing = configured()
        origin = existing['scopes'][0]['case']
        reviewer = get_user_model().objects.create_user(seed.TRIAL)
        invitation, token = staff.invite(existing['actor'], origin.pk, 'sample-invited-invoice-maker',
            'Fictional invoice maker', 'sample-invoice-maker@example.invalid', ['case.read'],
            rev(origin), profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!invoice.maker.734')
        original_grants = set(Grant.objects.filter(user=maker).values_list('case_id', 'action', 'active'))
        with self.assertRaisesMessage(RuntimeError, 'No exact matching accepted synthetic invitation'):
            seed.prepare(invitation.pk + 1_000, maker.pk)
        self.assertFalse(Case.objects.filter(pk=seed.CASE_ID).exists())
        sample = seed.prepare(invitation.pk, maker.pk)
        case = Case.objects.get(pk=sample['case'])
        work = FactoryWork.objects.get(pk=sample['work'], case=case)
        original = work.invoice
        first = HumanTask.objects.get(pk=sample['task'], case=case)
        self.assertEqual((original.actor_id, original.amount), (maker.pk, Decimal('20.00')))
        self.assertEqual(first.context['packet']['recipient_id'], maker.pk)
        self.assertFalse(InvoiceReview.objects.filter(invoice=original).exists())
        self.assertEqual(set(Grant.objects.filter(user=maker).exclude(case=case)
                             .values_list('case_id', 'action', 'active')), original_grants)
        self.assertFalse(Grant.objects.filter(case=case, action__in=[
            'finance.invoice.issue', 'finance.invoice.deliver', 'finance.invoice.operate',
        ]).exists())
        self.assertFalse(UsageIntakeReceipt.objects.filter(case=case, operation_key=seed.OPERATION).exists())

        def task_action(task, action, **fields):
            task.refresh_from_db()
            return self.client.post(sample['decision'], {
                'action': action, 'task': task.pk, 'task_revision': task.revision, **fields,
            })

        def decide(task, verdict, reason):
            return task_action(task, 'decide', verdict=verdict, reason=reason, evidence=sample['review_proof'])

        self.client.force_login(maker)
        page = self.client.get(sample['decision'])
        self.assertContains(page, 'Waiting for another Finance reviewer')
        self.assertContains(page, 'Comment for the Finance reviewer')
        self.assertNotContains(page, 'Claim task')
        self.assertEqual(task_action(first, 'claim').status_code, 403)
        self.assertEqual(task_action(first, 'invoice_comment', comment=seed.COMMENT).status_code, 302)
        self.assertEqual(TaskEvent.objects.filter(task=first, actor=maker, action='factory.invoice_comment').count(), 1)
        alerts_url = reverse('design_alerts')
        read_url = reverse('design_alert_read')
        self.assertNotContains(self.client.get(alerts_url), 'Invoice needs your review')

        outside = get_user_model().objects.create_user('sample-unrelated-invoice-reader')
        self.client.force_login(outside)
        self.assertEqual(self.client.get(sample['decision']).status_code, 404)
        self.assertNotContains(self.client.get(alerts_url), 'Invoice needs your review')
        self.client.force_login(reviewer)
        with CaptureQueriesContext(connection) as queries:
            assigned = assigned_alerts(reviewer)
        self.assertEqual(len(assigned), 1)
        self.assertEqual(assigned[0]['url'], sample['decision'])
        self.assertTrue(any('workflows_humantask' in query['sql']
                            and f'LIMIT {ASSIGNMENT_CANDIDATE_LIMIT}' in query['sql'] for query in queries))
        self.assertFalse(any('workflows_taskevent' in query['sql'] for query in queries))
        alert = assigned[0]
        page = self.client.get(alerts_url)
        self.assertContains(page, 'Invoice needs your review')
        self.assertContains(page, sample['decision'])
        self.assertNotContains(page, seed.COMMENT)
        self.assertNotContains(page, '20.00')
        self.assertNotContains(page, maker.username)
        self.assertNotContains(page, 'synthetic:invoice-corrected-controls')

        self.client.force_login(outside)
        self.assertEqual(self.client.post(read_url, {'key': alert['key']}).status_code, 404)
        self.client.force_login(reviewer)
        self.assertRedirects(self.client.post(read_url, {'key': alert['key']}), alerts_url, fetch_redirect_response=False)
        self.assertTrue(AlertRead.objects.filter(actor=reviewer, key=alert['key']).exists())
        self.assertNotContains(self.client.get(alerts_url, {'unread': '1'}), 'Invoice needs your review')
        review_grants = Grant.objects.filter(case=case, user=reviewer, action='finance.invoice.review')
        review_grants.update(active=False)
        self.assertNotContains(self.client.get(alerts_url), 'Invoice needs your review')
        review_grants.update(active=True)
        source_grants = Grant.objects.filter(case=case, user=maker, action='finance.billing.capture')
        source_grants.update(active=False)
        self.assertEqual(assigned_alerts(reviewer), [])
        source_grants.update(active=True)

        page = self.client.get(sample['decision'])
        self.assertContains(page, seed.COMMENT)
        self.assertContains(page, 'Claim task')
        self.assertEqual(task_action(first, 'claim').status_code, 302)
        self.assertContains(self.client.get(sample['decision']), 'Return for correction')
        self.assertEqual(decide(first, 'return', seed.RETURN_REASON).status_code, 302)
        returned = InvoiceReview.objects.get(invoice=original, actor=reviewer, verdict='return')
        work.refresh_from_db()
        self.assertEqual(returned.publication_packet, first.context['packet'])
        self.assertEqual(work.status, 'blocked')
        self.assertNotContains(self.client.get(alerts_url), 'Invoice needs your review')

        self.client.force_login(maker)
        recovery = self.client.get(sample['recovery'])
        self.assertContains(recovery, seed.RETURN_REASON)
        self.assertContains(recovery, sample['billing'])
        response = self.client.post(sample['usage_intake'], {'action': 'receive', 'revision': rev(case),
            'source_evidence': sample['source_evidence'], 'control_evidence': sample['control_evidence'],
            'delivery_ref': seed.DELIVERY, 'operation_key': seed.OPERATION, 'predecessor': sample['predecessor']})
        self.assertRedirects(response, sample['usage_intake'], fetch_redirect_response=False)
        receipt = UsageIntakeReceipt.objects.get(case=case, operation_key=seed.OPERATION)
        self.assertEqual(receipt.source.predecessor_id, sample['predecessor'])
        response = self.client.post(sample['usage_intake'], {
            'action': 'accept', 'revision': rev(case), 'source': receipt.source_id,
        })
        self.assertRedirects(response, sample['usage_intake'], fetch_redirect_response=False)
        usage = receipt.source.acceptance.partitions.get(coverage_id=sample['coverage'])
        response = self.client.post(sample['billing'], {'action': 'prepare', 'revision': rev(case),
                                    'coverage': sample['coverage'], 'kind': 'usage', 'usage': usage.pk})
        self.assertRedirects(response, sample['billing'], fetch_redirect_response=False)
        next_prep = BillingPreparation.objects.get(case=case, usage=usage)
        api = f'/api/v1/work/{work.pk}'
        replacement = {'expected_revision': work.revision,
            'preparation_id': next_prep.pk, 'reference': sample['reference'], 'due_date': sample['due_date'] or None,
            'reason': seed.CORRECTION_REASON}
        self.client.force_login(reviewer)
        self.assertEqual(self.client.post(api + '/invoice-preparation', replacement, content_type='application/json').status_code, 403)
        self.client.force_login(maker)
        self.assertEqual(self.client.post(api + '/invoice-preparation', replacement, content_type='application/json').status_code, 200)
        binding = FactoryInvoicePreparationBinding.objects.get(work=work, preparation=next_prep)
        self.assertEqual(binding.payload['previous_invoice'], original.pk)
        work.refresh_from_db()
        response = self.client.post(sample['overview'], {'action': 'advance', 'revision': work.revision})
        self.assertRedirects(response, sample['overview'], fetch_redirect_response=False)
        work.refresh_from_db()
        self.assertEqual(work.status, 'waiting', work.finding)
        successor = work.invoice
        self.assertEqual((successor.actor_id, successor.amount), (maker.pk, Decimal('24.00')))
        self.assertEqual(successor.obligation_key, original.obligation_key)
        self.assertNotEqual(successor.pk, original.pk)
        self.assertFalse(InvoiceReview.objects.filter(invoice=successor).exists())
        self.assertNotContains(self.client.get(sample['decision']), 'Approve exact packet')

        self.client.force_login(reviewer)
        self.assertContains(task_action(first, 'claim'), 'task changed')
        current = HumanTask.objects.get(case=case, context__work=work.pk, kind='factory_review', status='open')
        self.assertEqual(current.context['packet']['invoice'], successor.pk)
        self.assertNotEqual(assigned_alerts(reviewer)[0]['key'], alert['key'])
        self.assertContains(self.client.get(alerts_url, {'unread': '1'}), sample['decision'])
        exact_task = f'/api/v1/tasks/{current.pk}'
        claim = self.client.post(exact_task + '/claim', {'expected_revision': current.revision}, content_type='application/json')
        self.assertEqual(claim.status_code, 200, claim.content)
        approved = self.client.post(exact_task + '/decision', {'expected_revision': claim.json()['revision'],
            'verdict': 'approve', 'evidence_id': sample['review_proof'], 'note': seed.APPROVE_REASON},
            content_type='application/json')
        self.assertEqual(approved.status_code, 200, approved.content)
        self.assertEqual(self.client.get(exact_task).json()['invoice_packet']['invoice_id'], successor.pk)
        self.assertEqual(InvoiceReview.objects.get(invoice=successor).actor_id, reviewer.pk)
        self.assertEqual(InvoiceReview.objects.get(invoice=original).pk, returned.pk)
        history = self.client.get(sample['settlement'])
        self.assertContains(history, seed.RETURN_REASON)
        self.assertContains(history, seed.APPROVE_REASON)
        self.assertFalse(InvoiceJob.objects.filter(invoice__case=case).exists())
        self.assertFalse(InvoiceIssue.objects.filter(invoice__case=case).exists())
        self.assertFalse(AccountDelivery.objects.filter(actor__in=[maker, reviewer]).exists())
        replay = seed.prepare(invitation.pk, maker.pk)
        self.assertTrue(replay['preserved'])
        self.assertEqual((replay['invoice'], replay['current_invoice'], replay['original_decisions']),
                         (original.pk, successor.pk, 1))
