"""The adopted sample preparer and independent trial reviewer exercise the native asset route."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Case
from apps.finance import ppe
from apps.identity import staff
from apps.identity.models import Grant
from apps.workflows import factory, factory_ppe as flow
from apps.workflows.models import FactoryWork
from tests import railway_admitted_ppe_seed as seed, railway_admitted_schedule_seed as admission_seed
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_ppe_opening_proof import pdf_file
from tests.test_staff_profiles import configured


ENVIRONMENT = {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
               'PSL_COMPOSED_WALKTHROUGH': '1'}


@patch.dict('os.environ', ENVIRONMENT)
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class AdmittedPPEWalkthroughTests(TestCase):
    def test_admitted_preparer_preserves_their_identity_and_cannot_review_exact_asset_successor(self):
        data = configured()
        origin = data['scopes'][0]['case']
        reviewer = get_user_model().objects.create_user('psl-agent-trial')
        invitation, token = staff.invite(data['actor'], origin.pk, 'sample-invited-asset-preparer', 'Sample asset preparer',
                                         'sample-asset-preparer@example.invalid', ['case.read'], rev(origin),
                                         profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!asset.account.972')
        before = set(Grant.objects.filter(user=maker).values_list('case_id', 'action', 'active'))
        sample = seed.prepare(invitation.pk, maker.pk)
        self.assertEqual(seed.prepare(invitation.pk, maker.pk), sample)
        case = Case.objects.get(pk=sample['case'], tenant=seed.TENANT, synthetic=True)
        self.assertFalse(FactoryWork.objects.filter(case=case).exists())
        self.assertEqual(set(Grant.objects.filter(user=maker).exclude(case=case).values_list('case_id', 'action', 'active')),
                         before)
        mapping_grant = Grant.objects.filter(user=maker, case=case, action='finance.calculate')
        self.assertEqual(mapping_grant.filter(active=True).count(), 1)
        mapping_grant.update(active=False)
        with self.assertRaises(PermissionDenied):
            ppe.prepare(maker, case.pk, sample['reference'], sample['register'], None, sample['mapping'], rev(case))
        mapping_grant.update(active=True)

        self.client.force_login(maker)
        path = sample['start_path']
        self.assertContains(self.client.get(path), 'Start asset schedule work')
        response = self.client.post(path, {'definition': flow.DEFINITION, 'key': 'sample-admitted-assets-start',
                                           'reference': sample['reference'], 'case': case.pk, 'revision': rev(case),
                                           'register_id': sample['register'], 'ledger_id': sample['mapping'],
                                           'background': 'on'})
        work = FactoryWork.objects.get(case=case, definition=flow.DEFINITION, actor=maker)
        self.assertRedirects(response, reverse('factory_detail', args=[work.pk]), fetch_redirect_response=False)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        original = flow.schedule(work)
        self.assertEqual(seed.prepare(invitation.pk, maker.pk)['existing_work'], work.pk)
        self.assertIsNotNone(original, work.finding)
        self.assertEqual(original.actor_id, maker.pk)
        decision = reverse('factory_invoice_decision', args=[work.pk])
        recovery = reverse('factory_invoice_recovery', args=[work.pk])
        self.assertNotContains(self.client.get(decision), 'Approve exact schedule')

        self.client.force_login(reviewer)
        self.assertContains(self.client.get(decision), 'Return for correction')
        response = self.client.post(decision, {'action': 'review', 'target': original.pk, 'purpose': 'schedule',
                                              'revision': work.revision, 'case_revision': rev(case),
                                              'evidence': sample['review_evidence'], 'verdict': 'return',
                                              'note': 'Attach the exact original opening proof.'})
        self.assertRedirects(response, decision, fetch_redirect_response=False)
        self.assertNotContains(self.client.get(recovery), 'Opening proof')
        self.client.force_login(maker)
        form = self.client.get(recovery).context['proof_form']
        with patch('adapters.case_uploads.put') as storage:
            response = self.client.post(recovery, {'action': 'attach_opening_proof', 'target_id': original.pk,
                                                   'review_id': form.initial['review_id'], 'revision': work.revision,
                                                   'case_revision': rev(case), 'reason': 'Supplied opening proof.',
                                                   'file': pdf_file()[1]})
        self.assertRedirects(response, recovery, fetch_redirect_response=False)
        storage.assert_called_once()
        work.refresh_from_db()
        successor, _ = flow.source(work, maker)
        self.assertEqual(successor.actor_id, maker.pk)
        self.assertFalse(successor.reviews.exists())
        self.assertNotContains(self.client.get(decision), 'Approve exact register')
        self.client.force_login(reviewer)
        self.assertContains(self.client.get(decision), 'Approve exact register')
