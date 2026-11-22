from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.core.models import Case
from apps.finance.payroll_models import PayrollPublication, PayrollReview, PayrollReviewNote, PayrollRun
from apps.identity import staff
from apps.workflows import factory, factory_payroll
from apps.workflows.models import FactoryWork
from tests import railway_admitted_schedule_seed as admission_seed, railway_payroll_combine_return_seed as seed
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_staff_profiles import configured


@patch.dict('os.environ', {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                         'PSL_COMPOSED_WALKTHROUGH': '1', seed.GUARD: '1'})
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class PayrollCombineReturnFixtureTests(TestCase):
    def test_trial_returns_original_before_maker_rebuild_and_fresh_review(self):
        self.assertEqual(connection.vendor, 'postgresql')
        configuration = configured()
        origin = configuration['scopes'][0]['case']
        reviewer = get_user_model().objects.create_user('psl-agent-trial')
        invitation, token = staff.invite(configuration['actor'], origin.pk, 'sample-payroll-combine-maker',
            'Sample payroll combine preparer', 'sample-payroll-combine-maker@example.invalid', ['case.read'],
            rev(origin), profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!payroll-combine.591')
        with patch.dict('os.environ', {seed.GUARD: '0'}), self.assertRaises(RuntimeError):
            seed.prepare(invitation.pk, maker.pk)
        self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())

        sample = seed.prepare(invitation.pk, maker.pk)
        case = Case.objects.get(pk=sample['case'], synthetic=True, tenant=seed.TENANT)
        work = FactoryWork.objects.get(pk=sample['work'], case=case, actor=maker, definition=factory_payroll.DEFINITION)
        original = PayrollRun.objects.get(pk=sample['combined'], request__case=case, actor=maker, kind='combine')
        self.assertFalse(original.reviews.exists())
        self.assertEqual(seed.prepare(invitation.pk, maker.pk), {**sample, 'preserved': True})
        decision, recovery = sample['decision_path'], sample['recovery_path']

        self.client.force_login(reviewer)
        self.assertContains(self.client.get(decision), 'Review combined payroll')
        result = self.client.post(decision, {
            'action': 'review', 'revision': work.revision, 'case_revision': rev(case), 'kind': 'run',
            'subject_id': original.pk, 'verdict': 'return', 'operation_key': 'exact-combine-return',
            'evidence_id': sample['review_proof'], 'note': seed.RETURN_NOTE,
        })
        self.assertRedirects(result, decision)
        returned = PayrollReview.objects.get(run=original, verdict='return', actor=reviewer)
        self.assertContains(self.client.get(decision), seed.RETURN_NOTE)

        self.client.force_login(maker)
        work.refresh_from_db()
        result = self.client.post(recovery, {
            'action': 'correct', 'revision': work.revision, 'case_revision': rev(case), 'request_id': sample['request'],
            'input_ids': sample['inputs'], 'hr_snapshot_id': sample['snapshot'], 'reason': seed.REBUILD_REASON,
        })
        self.assertRedirects(result, recovery, fetch_redirect_response=False)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        rebuilt = factory_payroll.run(work, 'combine')
        self.assertIsNotNone(rebuilt, work.finding)
        self.assertNotEqual(rebuilt.pk, original.pk)
        self.assertNotEqual(work.source_head_id, sample['original_head'])
        self.assertEqual(rebuilt.metadata['input_ids'], original.metadata['input_ids'])
        self.assertFalse(rebuilt.reviews.exists())
        self.assertEqual(PayrollReviewNote.objects.get(review=returned).note, seed.RETURN_NOTE)
        self.assertFalse(PayrollPublication.objects.filter(request__case=case).exists())
        self.client.force_login(reviewer)
        self.assertContains(self.client.get(decision), f'Inspect exact working result {rebuilt.pk}')
        self.assertEqual(seed.prepare(invitation.pk, maker.pk)['current_combine'], rebuilt.pk)
