from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.documents.models import Publication, PublicationReceipt
from apps.identity import staff
from apps.workflows import factory, factory_escalation
from apps.workflows.models import FactoryWork, HumanTask
from tests import railway_admitted_schedule_seed as admission_seed
from tests import railway_escalation_review_return_seed as seed
from tests.helpers import rev
from tests.test_staff_profiles import configured


class EscalationReviewReturnFixtureTests(TestCase):
    @patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
    @patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
    def test_independent_review_returns_exact_escalation_message_with_note_and_no_send(self):
        self.assertEqual(connection.vendor, 'postgresql')
        original = configured()
        origin = original['scopes'][0]['case']
        trial = get_user_model().objects.create_user(seed.TRIAL)
        invitation, token = staff.invite(original['actor'], origin.pk, 'sample-north-clinic-message-maker',
            'Sample message maker', 'sample-north-clinic-maker@example.invalid', ['case.read'], rev(origin),
            profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!north-clinic-message-maker')
        origin_revision = rev(origin)
        sample = seed.prepare(invitation.pk, maker.pk)
        work = FactoryWork.objects.select_related('case').get(pk=sample['work'])
        task = HumanTask.objects.get(pk=sample['task'])
        version = factory_escalation.document(work)
        self.assertEqual((version.pk, version.created_by_id, task.created_by_id, task.required_role),
                         (sample['version'], maker.pk, maker.pk, 'PMO Lead'))
        self.assertEqual((task.status, version.payload_sha256), ('open', sample['version_sha256']))
        decision = {'action': 'review', 'revision': work.revision, 'case_revision': rev(work.case),
                    'version': version.pk, 'verdict': 'return', 'note': sample['note']}

        self.client.force_login(maker)
        self.assertNotContains(self.client.get(sample['decision_path']), 'Return exact communication')
        self.assertEqual(self.client.post(sample['decision_path'], decision).status_code, 403)
        self.assertFalse(version.reviews.exists())
        self.client.force_login(trial)
        page = self.client.get(sample['decision_path'])
        self.assertContains(page, f'Exact version record {version.pk}')
        self.assertContains(page, 'Return exact communication')
        self.assertContains(page, 'Document review rationale')
        response = self.client.post(sample['decision_path'], decision)
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        review = version.reviews.get()
        self.assertEqual((task.status, review.actor_id, review.verdict, review.note, review.payload_sha256),
                         ('returned', trial.pk, 'return', sample['note'], version.payload_sha256))
        self.assertEqual(review.authority['D05.decision_action_matrix'], sample['rules'])
        self.assertNotContains(self.client.get(sample['decision_path']), 'Approve exact communication')

        self.client.force_login(maker)
        self.assertContains(self.client.get(sample['readback_path']), sample['note'])
        factory.run_until_wait(work.pk)
        self.assertFalse(Publication.objects.filter(version=version).exists())
        self.assertFalse(PublicationReceipt.objects.filter(publication__version=version).exists())
        self.assertEqual(rev(origin), origin_revision)
        self.assertEqual(seed.prepare(invitation.pk, maker.pk), {**sample, 'preserved': True})
