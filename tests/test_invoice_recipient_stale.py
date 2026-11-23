"""Current Finance reviewers can compare governed invoice recipients and review afresh."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.core.models import Case
from apps.finance.models import Invoice, InvoiceIssue, InvoiceJob, InvoiceReview
from apps.identity import staff
from apps.identity.models import Grant
from apps.workflows.factory_progress import invoice_release_ready
from apps.workflows.models import FactoryWork, HumanTask
from tests import railway_admitted_schedule_seed as admissions
from tests import railway_invoice_recipient_stale_seed as seed
from tests.helpers import rev
from tests.test_staff_profiles import configured


@patch.object(admissions, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admissions, 'ADMISSION_PROFILE', 'sample-reader')
class InvoiceRecipientStaleTests(TestCase):
    def test_only_exact_reviewer_compares_and_approves_new_recipient_packet_on_same_obligation(self):
        self.assertEqual(connection.vendor, 'postgresql')
        existing = configured()
        origin = existing['scopes'][0]['case']
        reviewer = get_user_model().objects.create_user(seed.TRIAL)
        invitation, token = staff.invite(existing['actor'], origin.pk, 'sample-invited-stale-maker',
            'Synthetic invoice preparer', 'sample-stale-maker@example.invalid', ['case.read'],
            rev(origin), profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!invoice.stale.348')
        with self.assertRaisesMessage(RuntimeError, 'No exact matching accepted synthetic invitation'):
            seed.prepare(invitation.pk + 1000, maker.pk)
        self.assertFalse(Case.objects.filter(pk=seed.CASE_ID).exists())
        sample = seed.prepare(invitation.pk, maker.pk)
        case = Case.objects.get(pk=sample['case'])
        work = FactoryWork.objects.get(pk=sample['work'], case=case)
        first = HumanTask.objects.get(pk=sample['task'])
        original = first.context['packet']
        invoice = work.invoice
        self.assertEqual(original['recipient_id'], sample['earlier'])
        self.assertFalse(invoice_release_ready(work))
        decision = sample['decision_path']

        self.client.force_login(maker)
        page = self.client.get(decision)
        self.assertContains(page, 'Visible to the assigned Finance reviewer')
        for value in [seed.EARLIER_LABEL, seed.CURRENT_LABEL, seed.EARLIER_EMAIL, seed.CURRENT_EMAIL, 'recipient_id']:
            self.assertNotContains(page, value)
        self.assertNotContains(page, 'The invoice recipient changed')
        task_api = f'/api/v1/tasks/{first.pk}'
        self.assertNotIn('recipient_change', self.client.get(task_api).json())

        self.client.force_login(reviewer)
        page = self.client.get(decision)
        for value in ['The invoice recipient changed', seed.EARLIER_LABEL, seed.CURRENT_LABEL, '42.00 · unchanged']:
            self.assertContains(page, value)
        self.assertNotContains(page, seed.EARLIER_EMAIL)
        self.assertNotContains(page, seed.CURRENT_EMAIL)
        self.assertNotContains(page, 'Claim task')
        self.assertNotContains(page, 'Issue and send invoice')
        stale = self.client.get(task_api).json()
        self.assertEqual(stale['recipient_change'], {'earlier': seed.EARLIER_LABEL, 'current': seed.CURRENT_LABEL})
        self.assertFalse(stale['task']['can_claim'])
        self.assertEqual(self.client.post(task_api + '/claim', {'expected_revision': first.revision},
                                          content_type='application/json').status_code, 409)
        claim = {'action': 'claim', 'task': first.pk, 'task_revision': first.revision}
        self.assertContains(self.client.post(decision, claim), 'STALE_EVIDENCE')
        self.assertFalse(InvoiceReview.objects.filter(invoice=invoice).exists())
        self.assertFalse(InvoiceJob.objects.filter(invoice=invoice).exists())

        self.client.force_login(maker)
        response = self.client.post(sample['overview_path'], {'action': 'advance', 'revision': work.revision})
        self.assertRedirects(response, sample['overview_path'], fetch_redirect_response=False)
        work.refresh_from_db()
        first.refresh_from_db()
        self.assertEqual((work.invoice_id, first.status, first.context['packet']), (invoice.pk, 'returned', original))
        fresh = HumanTask.objects.get(case=case, context__work=work.pk, kind='factory_review', status='open')
        packet = fresh.context['packet']
        self.assertEqual(packet['recipient_id'], sample['current'])
        for key in ('invoice', 'version', 'amount', 'currency', 'payload_hash', 'preparation'):
            self.assertEqual(packet[key], original[key])
        self.assertEqual(Invoice.objects.filter(case=case, obligation_key=invoice.obligation_key).count(), 1)

        self.client.force_login(reviewer)
        page = self.client.get(decision)
        self.assertNotContains(page, 'The invoice recipient changed')
        self.assertContains(page, seed.CURRENT_LABEL)
        exact = f'/api/v1/tasks/{fresh.pk}'
        response = self.client.post(exact + '/claim', {'expected_revision': fresh.revision}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        fresh.refresh_from_db()
        response = self.client.post(exact + '/decision', {'expected_revision': fresh.revision,
            'verdict': 'approve', 'note': seed.APPROVAL_REASON, 'evidence_id': sample['review_proof']},
            content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        review = InvoiceReview.objects.get(invoice=invoice, actor=reviewer)
        self.assertEqual(review.publication_packet, packet)
        self.assertFalse(InvoiceJob.objects.filter(invoice__case=case).exists())
        self.assertFalse(InvoiceIssue.objects.filter(invoice__case=case).exists())
        Grant.objects.filter(case=case, user=reviewer, action='finance.invoice.review').update(active=False)
        page = self.client.get(decision)
        self.assertNotContains(page, seed.CURRENT_LABEL)
        self.assertNotContains(page, seed.EARLIER_LABEL)
        self.assertNotContains(page, 'recipient_id')
