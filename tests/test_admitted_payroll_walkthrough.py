from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.core.models import Audit, Case
from apps.finance import payroll_departure as timing, payroll_identity as names
from apps.finance.hrfinance_models import HRReadSnapshot
from apps.finance.payroll_models import PayrollHRFollowup, PayrollInput, PayrollPublication, PayrollRun
from apps.identity import staff
from apps.identity.models import Grant
from tests import railway_admitted_payroll_seed as seed, railway_admitted_schedule_seed as admission_seed
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_staff_profiles import configured


@patch.dict('os.environ', {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                         'PSL_COMPOSED_WALKTHROUGH': '1', seed.GUARD: '1'})
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class AdmittedPayrollWalkthroughTests(TestCase):
    def test_only_the_exact_admitted_people_can_complete_the_two_private_source_checks(self):
        data = configured()
        origin = data['scopes'][0]['case']
        users = get_user_model().objects
        hr_actor = users.create_user('psl-agent-trial')
        invitation, token = staff.invite(data['actor'], origin.pk, 'sample-payroll-preparer', 'Sample payroll preparer',
            'sample-payroll-preparer@example.invalid', ['case.read'], rev(origin), profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!payroll.fixture.471')
        grants = Grant.objects.filter(user__in=(maker, hr_actor))
        original_grants = set(grants.values_list('user_id', 'case_id', 'action', 'active'))
        with patch.dict('os.environ', {seed.GUARD: '0'}), self.assertRaises(RuntimeError):
            seed.prepare(invitation.pk, maker.pk)
        with self.assertRaises(RuntimeError):
            seed.prepare(invitation.pk, hr_actor.pk)
        origin_access = grants.filter(case=origin, user=maker, action='case.read')
        origin_access.update(active=False)
        try:
            with self.assertRaises(PermissionDenied):
                seed.prepare(invitation.pk, maker.pk)
        finally:
            origin_access.update(active=True)
        self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())

        sample = seed.prepare(invitation.pk, maker.pk)
        case = Case.objects.get(pk=sample['case'], synthetic=True)
        self.assertEqual(seed.prepare(invitation.pk, maker.pk), dict(sample, preserved=True))
        self.assertEqual(set(grants.exclude(case=case).values_list('user_id', 'case_id', 'action', 'active')),
                         original_grants)
        self.assertEqual(set(grants.filter(case=case, active=True).values_list('user_id', 'action')),
                         {(maker.pk, action) for action in seed.MAKER_ACTIONS}
                         | {(hr_actor.pk, action) for action in seed.HR_ACTIONS})
        self.assertTrue(PayrollInput.objects.filter(pk=sample['input'], actor=maker, request__case=case).exists())
        self.assertTrue(HRReadSnapshot.objects.filter(pk=sample['hr_snapshot'], actor=hr_actor,
                                                     contract__need__case=case).exists())
        self.assertTrue(PayrollRun.objects.filter(pk=sample['match'], kind='match', request__case=case,
                                                 reviews__verdict='approve').exists())
        self.assertFalse(Audit.objects.filter(case=case, action__in=(names.FACT, names.CHECK, timing.FACT, timing.CHECK)).exists())

        name_path, timing_path = sample['name_path'], sample['timing_path']
        payroll_name, hr_name = 'Fictional Avery East', 'Fictional Avery West'
        episode = 'sample-employment-period'
        departed = '2026-09-30T17:00:00+01:00'
        settled = '2026-10-02T15:00:00+01:00'

        def attest_name(side, record, row, name):
            return self.client.post(name_path, {'action': side, 'revision': rev(case), 'record': record, 'row': row,
                                               'name': name, 'reference': 'Fictional owner name record'})

        self.client.force_login(maker)
        self.assertContains(self.client.get(name_path), 'Record payroll evidence')
        self.assertNotContains(self.client.get(name_path), 'Record HR evidence')
        self.assertEqual(attest_name('hr', sample['hr_snapshot'], sample['staff'], hr_name).status_code, 403)
        self.assertEqual(attest_name('payroll', sample['input'], sample['row'], payroll_name).status_code, 302)
        self.assertEqual(self.client.post(timing_path, {'action': 'settlement', 'revision': rev(case),
            'input_id': sample['input'], 'row': sample['row'], 'episode': episode, 'status': 'settled',
            'instant': settled, 'source_reference': 'sample-payroll-settlement', 'source_version': 'v1'}).status_code, 302)
        payment = Audit.objects.get(case=case, actor=maker, action=timing.FACT, data__side='settlement')

        self.client.force_login(hr_actor)
        self.assertContains(self.client.get(name_path), 'Record HR evidence')
        self.assertNotContains(self.client.get(name_path), 'Record payroll evidence')
        self.assertEqual(attest_name('hr', sample['hr_snapshot'], sample['staff'], hr_name).status_code, 302)
        self.assertEqual(self.client.post(timing_path, {'action': 'employment', 'revision': rev(case),
            'employee': sample['staff'], 'episode': episode, 'status': 'ended', 'instant': departed,
            'source_reference': 'sample-hr-departure', 'source_version': 'v1'}).status_code, 302)

        self.client.force_login(maker)
        names_checked = self.client.post(name_path, {'action': 'check', 'revision': rev(case), 'run': sample['match'],
            'input_record': sample['input'], 'row': sample['row']}, follow=True)
        self.assertContains(names_checked, 'different names for the same staff ID')
        self.assertNotContains(names_checked, payroll_name)
        self.assertNotContains(names_checked, hr_name)
        comparison = names_checked.context['comparison']['id']
        routed = self.client.post(name_path, {'action': 'route', 'comparison': comparison, 'revision': rev(case)}, follow=True)
        self.assertContains(routed, 'Awaiting HR review')
        self.assertTrue(PayrollHRFollowup.objects.filter(run_id=sample['match'], record__snapshot_id=sample['hr_snapshot']).exists())
        timing_checked = self.client.post(timing_path, {'action': 'check', 'revision': rev(case),
            'settlement_id': payment.pk}, follow=True)
        self.assertContains(timing_checked, 'The recorded payment settled after the recorded departure.')
        self.assertNotContains(timing_checked, 'Acknowledge this finding')
        timing_id = timing_checked.context['comparison']['id']

        self.client.force_login(hr_actor)
        self.assertContains(self.client.get(sample['hr_corrections_path']), 'Correction')
        acknowledged = self.client.post(timing_path, {'action': 'review', 'revision': rev(case),
            'check_id': timing_id}, follow=True)
        self.assertContains(acknowledged, 'HR acknowledged this exact finding.')
        self.assertNotContains(acknowledged, departed)
        self.assertNotContains(acknowledged, settled)

        self.client.force_login(users.get(pk=sample['aggregate_reader']))
        self.assertNotContains(self.client.get(f'{timing_path}?check={timing_id}'), 'Recorded timing check')
        self.assertNotContains(self.client.get(name_path + f'&check={comparison}'), 'Recorded name check')
        self.assertFalse(PayrollPublication.objects.filter(request__case=case).exists())
