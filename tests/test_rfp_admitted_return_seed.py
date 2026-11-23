"""An admitted reviewer can return and approve exact versions, never edit the preparer's bid."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.core.models import Case
from apps.documents.models import Publication
from apps.identity import staff
from apps.identity.models import Grant, StaffAdmission
from apps.pmo.models import RFPReview, RFPSubmission
from apps.policy.services import active_component, reference_values
from apps.workflows import factory, factory_rfp
from apps.workflows.models import FactoryWork
from tests import railway_admitted_schedule_seed as admission_seed
from tests import railway_rfp_admitted_return_seed as seed
from tests.helpers import rev
from tests.test_staff_profiles import configured


@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class AdmittedBidReturnFixtureTests(TestCase):
    def test_exact_admission_keeps_return_correction_and_new_review_separate(self):
        self.assertEqual(connection.vendor, 'postgresql')
        existing = configured()
        origin = existing['scopes'][0]['case']
        trial = get_user_model().objects.create_user(seed.TRIAL)
        invitation, token = staff.invite(existing['actor'], origin.pk, 'sample-invited-bid-reviewer',
            'Sample Engineering reviewer', 'sample-engineering-reviewer@example.invalid', ['case.read'],
            rev(origin), profile_key='sample-reader')
        reviewer = staff.accept(token, 'Synthetic!bid-review.sample.734')
        admission = StaffAdmission.objects.get(invitation=invitation, user=reviewer)
        original_grants = set(Grant.objects.filter(user=reviewer).values_list('case_id', 'action', 'active'))
        with self.assertRaisesMessage(RuntimeError, 'No exact matching accepted synthetic invitation'):
            seed.prepare(invitation.pk + 1000, reviewer.pk)
        self.assertFalse(Case.objects.filter(pk=seed.CASE_ID).exists())

        sample = seed.prepare(invitation.pk, reviewer.pk)
        self.assertNotEqual(sample['case'], str(origin.pk))
        self.assertEqual(sample['admission'], admission.pk)
        self.assertEqual(sample['existing_decisions'], 0)
        case = Case.objects.get(pk=sample['case'])
        work = FactoryWork.objects.get(pk=sample['work'], case=case)
        self.assertEqual(work.actor_id, trial.pk)
        execution = reference_values(active_component(seed.EXECUTION_COMPONENT, case))[0]
        self.assertTrue(all(execution[field] is None for field in ('executor_id', 'template_id', 'route_key')))
        self.assertFalse(Grant.objects.filter(case=case, action__in=('document.publish', 'rfp.submit')).exists())
        self.assertEqual(set(Grant.objects.filter(user=reviewer).exclude(case=case)
                             .values_list('case_id', 'action', 'active')), original_grants)

        def decision(target, verdict, note):
            work.refresh_from_db()
            return self.client.post(sample['decision'], {'action': 'response', 'target': target, 'role': seed.ROLE,
                'verdict': verdict, 'note': note, 'evidence': sample['review_proof'], 'revision': work.revision,
                'case_revision': rev(case)})

        def correction():
            work.refresh_from_db()
            payload = factory_rfp.inputs(work)
            return self.client.post(sample['correction'].split('#')[0], {'action': 'correct',
                'revision': work.revision, 'case_revision': rev(case), 'reason': seed.RETURN_REASON,
                'response_evidence': payload['response_evidence'], 'public_terms': payload['public_terms'],
                'lessons': payload['lessons'], **payload['sources'], 'requirements-INITIAL_FORMS': 1,
                'requirements-TOTAL_FORMS': 1, 'requirements-0-key': 'R1',
                'requirements-0-evidence_id': sample['requirement'], 'requirements-0-response': seed.CORRECTED_ANSWER,
                'requirements-0-disposition': 'addressed'})

        original = sample['original_response']
        self.client.force_login(trial)
        self.assertEqual(decision(original, 'return', seed.RETURN_REASON).status_code, 403)
        self.client.force_login(reviewer)
        page = self.client.get(sample['decision'])
        self.assertContains(page, 'Return exact Response')
        self.assertContains(page, seed.INITIAL_ANSWER)
        self.assertEqual(decision(original, 'return', seed.RETURN_REASON).status_code, 302)
        self.assertNotContains(self.client.get(sample['decision']), '#correct-response')
        self.assertEqual(correction().status_code, 403)
        returned = RFPReview.objects.get(response_id=original, actor=reviewer, verdict='return')
        self.assertEqual(returned.evidence_id, sample['review_proof'])

        self.client.force_login(trial)
        page = self.client.get(sample['decision'])
        self.assertContains(page, seed.RETURN_REASON)
        self.assertContains(page, '#correct-response')
        self.assertEqual(correction().status_code, 302)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        successor = factory_rfp.response_for(work)
        self.assertIsNotNone(successor, work.finding)
        self.assertNotEqual(successor.pk, original)
        self.assertEqual(successor.actor_id, trial.pk)
        self.assertEqual(successor.matrix[0]['evidence_id'], sample['requirement'])
        self.assertFalse(successor.reviews.exists())

        self.client.force_login(reviewer)
        self.assertContains(decision(original, 'approve', seed.APPROVE_REASON), 'Review the exact current response')
        self.assertContains(self.client.get(sample['decision']), seed.CORRECTED_ANSWER)
        self.assertEqual(decision(successor.pk, 'approve', seed.APPROVE_REASON).status_code, 302)
        self.assertContains(self.client.get(sample['decision']), 'Earlier returns')
        self.assertEqual(successor.reviews.get().actor_id, reviewer.pk)
        self.assertFalse(Publication.objects.filter(version__document__case=case).exists())
        self.assertFalse(RFPSubmission.objects.filter(response__rfp__case=case).exists())
        replay = seed.prepare(invitation.pk, reviewer.pk)
        self.assertTrue(replay['preserved'])
        self.assertEqual((replay['original_response'], replay['current_response'], replay['existing_decisions']),
                         (original, successor.pk, 1))
