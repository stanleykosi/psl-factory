from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import Case
from apps.finance.models import Invoice, InvoiceDelivery, InvoiceIssue, InvoiceJob
from apps.workflows.models import FactoryWork
from tests.helpers import rev
from tests.railway_invoice_draft_stop_seed import CASE_ID, ORIGINAL, REASON, TRIAL, prepare


class InvoiceDraftStopFixtureTests(TestCase):
    def test_exact_trial_stop_preserves_original_internal_issue_and_duplicate_history(self):
        trial = get_user_model().objects.create_user(TRIAL)
        specimen = prepare()
        self.assertFalse(specimen['stopped'])
        self.assertFalse(specimen['preserved'])
        self.assertEqual(prepare()['issue'], specimen['issue'])
        case = Case.objects.get(pk=CASE_ID)
        work = FactoryWork.objects.get(pk=specimen['work'], case=case)
        self.assertNotEqual(work.actor_id, trial.pk)
        self.client.force_login(trial)
        self.assertContains(self.client.get(specimen['recovery']), 'Stop this invoice draft')
        response = self.client.post(specimen['recovery'], {
            'action': 'stop_invoice_draft', 'revision': work.revision, 'case_revision': rev(case),
            'reason': REASON, 'existing_invoice': specimen['invoice'],
        })
        self.assertRedirects(response, specimen['recovery'])
        stopped = self.client.get(specimen['recovery'])
        self.assertContains(stopped, REASON)
        self.assertContains(stopped, 'Never sent')
        self.assertContains(stopped, 'Open ' + ORIGINAL)
        self.assertTrue(prepare()['stopped'])
        self.assertEqual(Invoice.objects.filter(case=case).count(), 2)
        self.assertEqual(list(InvoiceIssue.objects.filter(invoice__case=case).values_list('pk', flat=True)), [specimen['issue']])
        self.assertEqual(list(InvoiceJob.objects.filter(invoice__case=case).values_list('pk', flat=True)), [specimen['job']])
        self.assertFalse(InvoiceDelivery.objects.filter(invoice__case=case).exists())
