from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Case
from apps.finance.hrfinance_models import HRHandoffRecord
from apps.finance.models import PayrollPublication, PayrollReview, PayrollRun
from apps.identity import staff
from apps.identity.models import Grant
from apps.workflows import factory_payroll
from apps.workflows.models import FactoryWork
from tests import railway_admitted_schedule_seed as admission_seed, railway_payroll_start_walkthrough_seed as seed
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_staff_profiles import configured


@patch.dict('os.environ', {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                         'PSL_COMPOSED_WALKTHROUGH': '1', seed.GUARD: '1'})
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class PayrollStartWalkthroughFixtureTests(TestCase):
    def test_guarded_source_only_specimen_leaves_start_for_exact_admitted_maker(self):
        self.assertEqual(connection.vendor, 'postgresql')
        configuration = configured()
        origin = configuration['scopes'][0]['case']
        trial = get_user_model().objects.create_user('psl-agent-trial')
        invitation, token = staff.invite(configuration['actor'], origin.pk, 'sample-payroll-start-maker',
            'Sample payroll starter', 'sample-payroll-start-maker@example.invalid', ['case.read'], rev(origin),
            profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!payroll-start.751')
        grants = Grant.objects.filter(user__in=(trial, maker))
        old_grants = set(grants.values_list('user_id', 'case_id', 'action', 'active'))
        with patch.dict('os.environ', {seed.GUARD: '0'}), self.assertRaises(RuntimeError):
            seed.prepare(invitation.pk, maker.pk)
        with self.assertRaises(RuntimeError):
            seed.prepare(invitation.pk, trial.pk)
        self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())

        sample = seed.prepare(invitation.pk, maker.pk)
        case = Case.objects.get(pk=sample['case'], synthetic=True, tenant=seed.TENANT)
        self.assertEqual(set(grants.exclude(case=case).values_list('user_id', 'case_id', 'action', 'active')), old_grants)
        self.assertEqual(seed.prepare(invitation.pk, maker.pk), {**sample, 'preserved': True})
        self.assertIsNone(sample['work'])
        self.assertFalse(HRHandoffRecord.objects.filter(snapshot_id=sample['hr_snapshot_id'], actor=maker,
                                                        kind='receipt').exists())
        self.client.force_login(trial)
        self.assertEqual(self.client.get(sample['path']).status_code, 403)
        self.client.force_login(maker)
        page = self.client.get(sample['path'])
        self.assertContains(page, 'Start payroll work')
        self.assertNotContains(page, 'E001')
        response = self.client.post(reverse('factory_create'), {
            'definition': factory_payroll.DEFINITION, 'case': case.pk, 'key': 'sample-payroll-start-native',
            'reference': sample['reference'], 'revision': rev(case), 'request_id': sample['request'],
            'input_ids': sample['input_ids'], 'hr_snapshot_id': sample['hr_snapshot_id'],
        })
        work = FactoryWork.objects.get(case=case, actor=maker, definition=factory_payroll.DEFINITION)
        self.assertRedirects(response, reverse('factory_detail', args=[work.pk]), fetch_redirect_response=False)
        self.assertFalse(PayrollRun.objects.filter(request__case=case).exists())
        self.assertFalse(PayrollReview.objects.filter(request__case=case).exists())
        self.assertFalse(PayrollPublication.objects.filter(request__case=case).exists())
        self.assertEqual(seed.prepare(invitation.pk, maker.pk)['work'], work.pk)
