from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.core.models import Case
from apps.finance.models import CashAllocation, InvoiceDelivery, InvoiceIssue
from apps.pmo.models import ChangeMilestoneLink
from tests.helpers import rev
from tests.railway_signed_milestone_payment_seed import (
    CASE_ID, CHANGE_REFERENCE, CHANGE_SCOPE, MILESTONE, PART_PAYMENT, REFERENCE, SIGNED_AMOUNT, TRIAL, prepare,
)


class SignedMilestonePaymentFixtureTests(TestCase):
    def test_trial_links_current_change_and_original_part_payment_remains_exact(self):
        self.assertEqual(connection.vendor, 'postgresql')
        trial = get_user_model().objects.create_user(TRIAL)
        prepared = prepare()
        case = Case.objects.get(pk=CASE_ID)
        self.assertEqual(prepared['trial'], trial.pk)
        self.assertNotEqual(prepared['trial'], prepared['preparer'])
        self.assertIsNone(prepared['linked'])
        self.assertFalse(prepared['preserved'])
        self.assertFalse(ChangeMilestoneLink.objects.filter(case=case).exists())
        same = prepare()
        self.assertTrue(same['preserved'])
        self.assertEqual(same['issue'], prepared['issue'])
        self.assertEqual(same['allocation'], prepared['allocation'])

        self.client.force_login(trial)
        stages = self.client.get(prepared['milestones'])
        self.assertContains(stages, 'NGN 42.50')
        self.assertContains(stages, MILESTONE)
        self.assertContains(stages, REFERENCE)
        self.assertContains(stages, 'Applied NGN 20.00')
        self.assertNotContains(stages, 'Recorded completions')
        self.assertNotContains(stages, 'Additional amount unknown.')
        ready = self.client.get(prepared['form'])
        self.assertContains(ready, CHANGE_REFERENCE)
        self.assertContains(ready, MILESTONE)
        posted = self.client.post(prepared['form'], {
            'stage': 'completion', 'plan': prepared['plan'], 'scope_note': CHANGE_SCOPE, 'revision': rev(case),
        })
        self.assertRedirects(posted, prepared['milestones'])
        confirmed = self.client.get(prepared['milestones'])
        self.assertContains(confirmed, 'NGN 42.50')
        self.assertContains(confirmed, 'Applied NGN 20.00')
        self.assertContains(confirmed, 'Additional amount unknown.')
        self.assertContains(confirmed, CHANGE_SCOPE)
        self.assertContains(confirmed, f"Original project plan evidence {prepared['original_plan']}")
        money = self.client.get(prepared['money'])
        self.assertContains(money, 'Outstanding NGN 22.50')
        [line] = money.context['money']['selected']['invoices']
        self.assertEqual((line['paid'], line['owed']), (PART_PAYMENT, Decimal('22.50')))

        saved = ChangeMilestoneLink.objects.get(case=case, actor=trial)
        self.assertEqual((saved.version_id, saved.plan_event_id, saved.signed_id, saved.terms_id),
                         (prepared['change'], prepared['plan'], prepared['signed'], prepared['terms']))
        self.assertEqual(prepare()['linked'], saved.pk)
        [issue] = InvoiceIssue.objects.filter(invoice__case=case)
        [allocation] = CashAllocation.objects.filter(issue=issue)
        self.assertEqual((issue.pk, issue.invoice.amount, allocation.pk, allocation.amount),
                         (prepared['issue'], SIGNED_AMOUNT, prepared['allocation'], PART_PAYMENT))
        self.assertFalse(InvoiceDelivery.objects.filter(invoice__case=case).exists())
