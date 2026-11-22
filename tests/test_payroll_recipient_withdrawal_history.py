from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.core.models import Case
from apps.finance.payroll_models import PayrollPublication, PayrollReportReceipt
from apps.identity import staff
from apps.identity.models import Grant
from apps.workflows import factory_payroll, factory_progress
from apps.workflows.factory_payroll_views import recipient_withdrawal
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import railway_admitted_schedule_seed as admission_seed, railway_payroll_followup_history_seed as seed
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_staff_profiles import configured


@patch.dict('os.environ', {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                         'PSL_COMPOSED_WALKTHROUGH': '1', seed.GUARD: '1'})
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class PayrollRecipientWithdrawalHistoryTests(TestCase):
    def test_replacement_retains_exact_own_withdrawal_metadata_and_new_receipt(self):
        self.assertEqual(connection.vendor, 'postgresql')
        configuration = configured()
        origin = configuration['scopes'][0]['case']
        users = get_user_model().objects
        trial = users.create_user('psl-agent-trial')
        invitation, token = staff.invite(configuration['actor'], origin.pk, 'sample-payroll-history-maker',
            'Sample payroll history maker', 'sample-payroll-history-maker@example.invalid', ['case.read'],
            rev(origin), profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!payroll-history.187')
        grants = Grant.objects.filter(user__in=(maker, trial))
        prior_grants = set(grants.values_list('case_id', 'user_id', 'action', 'active'))
        with patch.dict('os.environ', {seed.GUARD: '0'}), self.assertRaises(RuntimeError):
            seed.prepare(invitation.pk, maker.pk)
        self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())

        sample = seed.prepare(invitation.pk, maker.pk)
        case = Case.objects.get(pk=sample['case'], synthetic=True, tenant=seed.TENANT)
        self.assertEqual(set(grants.exclude(case=case).values_list('case_id', 'user_id', 'action', 'active')), prior_grants)
        self.assertEqual(seed.prepare(invitation.pk, maker.pk), {**sample, 'preserved': True})
        work = FactoryWork.objects.get(pk=sample['work'], case=case, actor=maker)
        original = PayrollPublication.objects.get(pk=sample['original_publication'], request__case=case)
        prior_receipt = PayrollReportReceipt.objects.get(pk=sample['original_receipt'], publication=original, actor=trial)
        self.assertIsNone(sample['successor_publication'])

        recipient_path, publish_path = sample['recipient_path'], sample['publish_path']
        self.client.force_login(trial)
        before = self.client.get(recipient_path)
        self.assertContains(before, 'Your published payroll report was withdrawn')
        self.assertContains(before, f'Your earlier receipt #{prior_receipt.pk}')
        self.assertNotContains(before, 'Acknowledge receipt as myself')
        self.assertNotContains(before, '250.00')
        self.assertNotContains(before, seed.REASON)
        self.client.force_login(maker)
        self.assertRedirects(self.client.post(publish_path, {'action': 'publish', 'revision': work.revision,
            'case_revision': rev(case)}), publish_path, fetch_redirect_response=False)
        current = factory_payroll.publication(work)
        self.assertEqual(current.version, 2)
        self.assertEqual(current.run_id, sample['successor_aggregate'])
        self.assertFalse(PayrollReportReceipt.objects.filter(publication=current).exists())
        work.refresh_from_db()
        self.assertRedirects(self.client.post(recipient_path, {'action': 'advance', 'revision': work.revision}),
                             recipient_path, fetch_redirect_response=False)

        outsider = users.create_user(username='sample-no-historical-payroll-audience')
        for action in seed.draft.TRIAL_ACTIONS:
            Grant.objects.create(case=case, user=outsider, action=action)
        self.assertIsNone(recipient_withdrawal(outsider, work, current))
        self.client.force_login(outsider)
        self.assertNotContains(self.client.get(recipient_path), f'Your earlier receipt #{prior_receipt.pk}', status_code=403)
        self.client.force_login(trial)
        with CaptureQueriesContext(connection) as queries:
            history = recipient_withdrawal(trial, work, current)
        self.assertEqual(history['receipt_id'], prior_receipt.pk)
        self.assertEqual(history['publication'], original.pk)
        for query in queries.captured_queries:
            selected = query['sql'].split(' FROM ', 1)[0]
            self.assertNotIn('"finance_payrollpublication"."payload"', selected)

        response = self.client.get(recipient_path)
        self.assertContains(response, 'Your published payroll report was withdrawn')
        self.assertContains(response, f'Your earlier receipt #{prior_receipt.pk}')
        self.assertContains(response, 'Acknowledge receipt as myself')
        self.assertContains(response, '260.00')
        self.assertNotContains(response, '250.00')
        self.assertNotContains(response, seed.REASON)
        self.assertNotContains(response, 'E001')
        self.assertRedirects(self.client.post(recipient_path, {
            'action': 'receive', 'revision': work.revision, 'case_revision': rev(case), 'publication_id': current.pk,
        }), recipient_path, fetch_redirect_response=False)
        newest = PayrollReportReceipt.objects.get(publication=current, actor=trial)
        progress = FactoryProgress.objects.get(work=work)
        for _ in range(6):
            factory_progress.run_once()
            work.refresh_from_db()
            if work.status == 'verified':
                break
        self.assertEqual(work.status, 'verified', work.finding)
        self.assertEqual(FactoryProgress.objects.get(work=work).pk, progress.pk)
        final = self.client.get(recipient_path)
        self.assertContains(final, f'Receipt #{newest.pk}')
        self.assertContains(final, f'Your earlier receipt #{prior_receipt.pk}')
        self.assertEqual(PayrollReportReceipt.objects.filter(publication__request__case=case).count(), 2)
