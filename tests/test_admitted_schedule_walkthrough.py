"""An accepted identity starts its own synthetic Finance work with narrowly scoped access."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Case
from apps.identity import staff
from apps.identity.models import Grant
from apps.workflows import factory, factory_schedules as schedules
from apps.workflows.models import FactoryWork
from tests import railway_admitted_schedule_seed as seed
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_staff_profiles import configured


ENVIRONMENT = {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
               'PSL_COMPOSED_WALKTHROUGH': '1'}


@patch.dict('os.environ', ENVIRONMENT)
@patch.object(seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(seed, 'ADMISSION_PROFILE', 'sample-reader')
class AdmittedScheduleWalkthroughTests(TestCase):
    def test_exact_admitted_user_starts_new_case_and_keeps_invitation_and_original_scope(self):
        data = configured()
        origin = data['scopes'][0]['case']
        inviter = data['actor']
        reviewer = get_user_model().objects.create_user('psl-agent-trial')
        invitation, token = staff.invite(inviter, origin.pk, 'sample-invited-schedule-preparer', 'Sample schedule preparer',
                                         'sample-schedule-preparer@example.invalid', ['case.read'], rev(origin),
                                         profile_key='sample-reader')
        with self.assertRaisesMessage(RuntimeError, 'No exact matching accepted synthetic invitation'):
            seed.prepare(invitation.pk, 987654)
        self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())
        maker = staff.accept(token, 'Synthetic!schedule.account.816')
        original_grants = list(Grant.objects.filter(user=maker).values_list('case_id', 'action', 'active'))
        original_password = maker.password

        sample = seed.prepare(invitation.pk, maker.pk)
        self.assertEqual(seed.prepare(invitation.pk, maker.pk), sample)
        case = Case.objects.get(pk=sample['case'], synthetic=True, tenant=seed.TENANT)
        self.assertIsNone(sample['existing_work'])
        self.assertFalse(FactoryWork.objects.filter(case=case).exists())
        maker.refresh_from_db()
        self.assertTrue(maker.password == original_password)
        self.assertEqual(list(Grant.objects.filter(user=maker).exclude(case=case).values_list('case_id', 'action', 'active')),
                         original_grants)
        self.assertEqual(set(Grant.objects.filter(user=maker, case=case, active=True).values_list('action', flat=True)),
                         set(seed.MAKER_ACTIONS))

        self.client.force_login(maker)
        path = sample['start_path']
        self.assertContains(self.client.get(path), 'Start income detail or inventory work')
        response = self.client.post(path, {'definition': schedules.DEFINITION, 'key': 'sample-admitted-schedule-start',
                                           'reference': sample['reference'], 'case': case.pk, 'revision': rev(case),
                                           'kind': 'income', 'parent_id': sample['mapping'], 'evidence_id': sample['source'],
                                           'payload': '', 'background': 'on'})
        work = FactoryWork.objects.get(case=case, definition=schedules.DEFINITION, actor=maker)
        self.assertRedirects(response, reverse('factory_detail', args=[work.pk]), fetch_redirect_response=False)
        self.assertEqual(seed.prepare(invitation.pk, maker.pk)['existing_work'], work.pk)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        schedule = schedules.schedule(work)
        self.assertIsNotNone(schedule, work.finding)
        self.assertEqual(schedule.evidence_id, sample['source'])
        self.assertEqual(schedule.payload['rows'][-1]['key'], 'row-12')

        decision = reverse('factory_invoice_decision', args=[work.pk])
        recovery = reverse('factory_invoice_recovery', args=[work.pk])
        self.assertNotContains(self.client.get(decision), 'Approve exact schedule')
        self.client.force_login(reviewer)
        self.assertContains(self.client.get(decision), 'Return for correction')
        response = self.client.post(decision, {'action': 'review', 'target': schedule.pk, 'revision': work.revision,
                                               'case_revision': rev(case), 'evidence': sample['review_evidence'],
                                               'verdict': 'return', 'note': 'Review the row 12 relationship.'})
        self.assertRedirects(response, decision, fetch_redirect_response=False)
        self.assertNotContains(self.client.get(recovery), 'Row relationship')
        self.client.force_login(maker)
        self.assertContains(self.client.get(recovery), 'Row relationship')

        form = self.client.get(recovery).context['correction_form']
        response = self.client.post(recovery, {'action': 'resubmit_returned_row', 'target': schedule.pk,
                                               'return_id': form.initial['return_id'], 'revision': work.revision,
                                               'case_revision': rev(case), 'row_key': 'row-12',
                                               'relationship': 'reclassification'})
        self.assertRedirects(response, recovery, fetch_redirect_response=False)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        successor = schedules.schedule(work)
        self.assertEqual(successor.payload['rows'][-1]['relationship'], 'reclassification')
        self.assertFalse(successor.reviews.exists())
        self.assertEqual(schedule.reviews.get().verdict, 'return')
