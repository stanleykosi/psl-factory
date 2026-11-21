from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.core.models import Case
from apps.finance.models import PayrollPublication, PayrollReportReceipt
from apps.identity import staff
from apps.identity.models import Grant
from apps.workflows import factory_payroll
from apps.workflows.models import FactoryWork
from tests import railway_admitted_schedule_seed as admission_seed, railway_payroll_followup_draft_seed as seed
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_staff_profiles import configured


@patch.dict('os.environ', {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                         'PSL_COMPOSED_WALKTHROUGH': '1', seed.GUARD: '1'})
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class PayrollFollowupDraftFixtureTests(TestCase):
    def test_exact_approved_draft_has_no_delivery_and_trial_is_recipient_only(self):
        self.assertEqual(connection.vendor, 'postgresql')
        configuration = configured()
        origin = configuration['scopes'][0]['case']
        trial = get_user_model().objects.create_user('psl-agent-trial')
        invitation, token = staff.invite(configuration['actor'], origin.pk, 'sample-payroll-followup-maker',
            'Sample payroll preparer', 'sample-payroll-followup-maker@example.invalid', ['case.read'], rev(origin),
            profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!payroll-followup.481')
        with patch.dict('os.environ', {seed.GUARD: '0'}), self.assertRaises(RuntimeError):
            seed.prepare(invitation.pk, maker.pk)
        with self.assertRaises(RuntimeError):
            seed.prepare(invitation.pk, trial.pk)
        self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())

        sample = seed.prepare(invitation.pk, maker.pk)
        case = Case.objects.get(pk=sample['case'], synthetic=True, tenant=seed.TENANT)
        self.assertEqual(seed.prepare(invitation.pk, maker.pk), {**sample, 'preserved': True})
        self.assertIsNone(sample['publication'])
        self.assertEqual(set(Grant.objects.filter(case=case, user=trial, active=True).values_list('action', flat=True)),
                         seed.TRIAL_ACTIONS)
        work = FactoryWork.objects.get(pk=sample['work'], case=case, actor=maker, definition=factory_payroll.DEFINITION)
        self.assertEqual(factory_payroll.report(work, maker)['stage'], 'publish')
        self.assertFalse(PayrollPublication.objects.filter(request__case=case).exists())
        self.assertFalse(PayrollReportReceipt.objects.filter(publication__request__case=case).exists())

        self.client.force_login(maker)
        self.assertContains(self.client.get(sample['publish_path']), 'Publish exact reviewed aggregate')
        self.client.force_login(trial)
        page = self.client.get(sample['recovery_path'])
        self.assertNotContains(page, 'Acknowledge receipt as myself', status_code=403)
        self.assertNotContains(page, 'Publish exact reviewed aggregate', status_code=403)
        self.assertNotContains(page, 'E001', status_code=403)
