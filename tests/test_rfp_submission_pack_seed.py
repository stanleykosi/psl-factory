from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.core.models import Case, Evidence
from apps.documents.models import Publication
from apps.identity import staff
from apps.identity.models import Grant
from apps.pmo.models import RFPDocumentBinding, RFPSubmission, RFPSubmissionPack
from apps.policy.services import active_component, reference_values
from apps.workflows import factory
from apps.workflows.models import FactoryWork, HumanTask
from tests import railway_admitted_schedule_seed as admission_seed
from tests import railway_rfp_submission_pack_seed as seed
from tests.helpers import rev
from tests.test_staff_profiles import configured


@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class RFPSubmissionPackFixtureTests(TestCase):
    def test_exact_admission_and_review_role_start_before_the_first_pack(self):
        self.assertEqual(connection.vendor, 'postgresql')
        data = configured()
        origin = data['scopes'][0]['case']
        trial = get_user_model().objects.create_user(seed.TRIAL)
        invitation, token = staff.invite(data['actor'], origin.pk, 'sample-admitted-pack-maker',
            'Sample independent pack preparer', 'sample-pack-maker@example.invalid', ['case.read'],
            rev(origin), profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!pack-maker.1247')
        native_grants = set(Grant.objects.filter(user=maker).values_list('case_id', 'action', 'active'))
        with self.assertRaisesMessage(RuntimeError, 'No exact matching accepted synthetic invitation'):
            seed.prepare(invitation.pk + 1000, maker.pk)
        self.assertFalse(Case.objects.filter(pk=seed.CASE_ID).exists())

        sample = seed.prepare(invitation.pk, maker.pk)
        case = Case.objects.get(pk=sample['case'])
        self.assertNotEqual(case.pk, origin.pk)
        self.assertEqual((sample['maker'], sample['reviewer']), (maker.pk, trial.pk))
        self.assertIsNone(sample['current_controlled_version'])
        self.assertFalse(RFPSubmissionPack.objects.filter(response__rfp__case=case).exists())
        self.assertFalse(RFPDocumentBinding.objects.filter(response__rfp__case=case).exists())
        received = Evidence.objects.get(case=case, pk=sample['received'])
        self.assertEqual(received.body, seed.FILE_REQUIREMENT)
        execution = reference_values(active_component(seed.COMPONENT, case))[0]
        self.assertIsNone(execution['executor_id'])
        self.assertFalse(Grant.objects.filter(case=case, action='document.publish').exists())
        self.assertEqual(set(Grant.objects.filter(user=maker).exclude(case=case)
                             .values_list('case_id', 'action', 'active')), native_grants)

        route = sample['decision'].split('#')[0]
        work = FactoryWork.objects.get(case=case, pk=sample['work'])
        self.client.force_login(trial)
        self.assertNotContains(self.client.get(route), 'Save pack draft')
        self.client.force_login(maker)
        self.assertContains(self.client.get(route), 'Save pack draft')
        self.assertEqual(self.client.post(route, {
            'action': 'submission_pack', 'revision': work.revision, 'case_revision': rev(case),
            'pack-target': sample['response'], 'pack-base': 0, 'pack-cover_note': seed.COVER_NOTE,
            'pack-file_extension': sample['file_extension'], 'pack-file_count': sample['file_count'],
            'pack-file_size_rule': sample['file_size_rule'], 'pack-file_size_bytes': sample['file_size_bytes'],
        }).status_code, 302)

        factory.run_until_wait(work.pk)
        binding = RFPDocumentBinding.objects.get(response_id=sample['response'])
        self.assertFalse(HumanTask.objects.filter(version=binding.version).exists())
        work.refresh_from_db()
        self.assertContains(self.client.get(route), 'Send for review')
        self.assertEqual(self.client.post(route, {
            'action': 'submission_pack_review', 'revision': work.revision, 'case_revision': rev(case),
            'pack': binding.snapshot['submission_pack'], 'version': binding.version_id,
        }).status_code, 302)
        self.assertTrue(HumanTask.objects.filter(version=binding.version, status='open').exists())
        self.assertNotContains(self.client.get(route), 'Final client response review')
        self.client.force_login(trial)
        review = self.client.get(route)
        self.assertContains(review, 'Final client response review')
        self.assertContains(review, seed.COVER_NOTE)
        self.assertNotContains(review, 'Save pack draft')
        self.assertEqual(seed.prepare(invitation.pk, maker.pk)['current_controlled_version'], binding.version_id)
        self.assertFalse(Publication.objects.filter(version__document__case=case).exists())
        self.assertFalse(RFPSubmission.objects.filter(response__rfp__case=case).exists())
