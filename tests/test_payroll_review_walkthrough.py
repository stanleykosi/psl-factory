from datetime import timedelta
from hashlib import sha256
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.finance.payroll_models import PayrollHRFollowup, PayrollInput, PayrollPublication, PayrollReview, PayrollReviewNote
from apps.identity import staff
from apps.identity.models import Grant
from apps.workflows import factory, factory_payroll as flow
from apps.workflows.models import FactoryWork
from tests.helpers import rev
from tests import railway_admitted_schedule_seed as admission_seed, railway_payroll_review_walkthrough_seed as sample
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_staff_profiles import configured


@patch.dict('os.environ', {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                         'PSL_COMPOSED_WALKTHROUGH': '1', sample.GUARD: '1'})
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class PayrollReviewWalkthroughTests(TestCase):
    def test_rejected_file_replacement_and_private_staff_match_return(self):
        setup = configured()
        owner, origin = setup['actor'], setup['scopes'][0]['case']
        reviewer = get_user_model().objects.create_user('psl-agent-trial')
        invitation, token = staff.invite(
            owner, origin.pk, 'sample-payroll-return-maker', 'Sample Payroll Owner', 'sample-payroll-return@example.invalid',
            ['case.read'], rev(origin), profile_key='sample-reader',
        )
        maker = staff.accept(token, 'Synthetic!payroll.return.421')
        data = sample.prepare(invitation.pk, maker.pk)
        self.assertEqual(sample.prepare(invitation.pk, maker.pk), {**data, 'preserved': True})
        case = Case.objects.get(pk=data['case'])
        work = FactoryWork.objects.get(pk=data['work'], case=case)
        original_head = work.source_head_id
        original = PayrollInput.objects.get(pk=data['original_input'], request__case=case)

        def decide(kind, pk, verdict, operation, note=None):
            work.refresh_from_db()
            values = {'action': 'review', 'revision': work.revision, 'case_revision': rev(case),
                      'kind': kind, 'subject_id': pk, 'verdict': verdict, 'operation_key': operation,
                      'evidence_id': data['review_proof']}
            if note is not None:
                values['note'] = note
            return self.client.post(data['decision'], values)

        self.client.force_login(reviewer)
        self.assertContains(decide('input', original.pk, 'return', 'return-input'), 'Enter a note')
        self.assertRedirects(decide('input', original.pk, 'return', 'return-input', sample.INPUT_NOTE), data['decision'])
        self.assertContains(self.client.get(data['decision']), sample.INPUT_NOTE)
        input_return = PayrollReview.objects.get(input=original, verdict='return', actor=reviewer)
        self.assertEqual(PayrollReviewNote.objects.get(review=input_return).note, sample.INPUT_NOTE)

        def upload(key, content):
            return self.client.post(data['inputs_page'], {'action': 'capture', 'revision': rev(case),
                'request_record': data['request'], 'provider': data['provider'], 'operation_key': key,
                'source_version': key, 'extracted_at': (timezone.now() - timedelta(seconds=1)).isoformat(),
                'control_total': '150', 'completeness': 'complete',
                'file': SimpleUploadedFile(key + '.csv', content.encode())}, follow=True)

        self.client.force_login(maker)
        self.assertContains(self.client.get(data['decision']), sample.INPUT_NOTE)
        rejected_response = upload('sample-bad-file', sample.REJECTED_CSV)
        self.assertContains(rejected_response, 'No source values retained')
        rejected = PayrollInput.objects.get(request_id=data['request'], operation_key='sample-bad-file')
        self.assertEqual(rejected.payload, {})
        self.assertEqual(rejected.source_sha256, sha256(sample.REJECTED_CSV.encode()).hexdigest())
        self.assertContains(rejected_response, rejected.source_sha256)
        self.assertNotContains(rejected_response, 'SYNTHETIC-UNAPPROVED-TEXT')
        self.assertContains(upload('sample-corrected-file', sample.VALID_CSV), 'Payroll history updated')
        current = PayrollInput.objects.get(request_id=data['request'], operation_key='sample-corrected-file')
        self.assertGreater(current.version, rejected.version)
        self.assertFalse(current.reviews.exists())
        self.assertEqual(FactoryWork.objects.get(pk=work.pk).source_head_id, original_head)

        fields = {'action': 'correct', 'revision': work.revision, 'case_revision': rev(case),
                  'request_id': data['request'], 'input_ids': [data['other_input'], rejected.pk],
                  'hr_snapshot_id': data['snapshot'], 'reason': 'Use the exact corrected sample source version.'}
        self.assertContains(self.client.post(data['recovery'], fields), 'Choose exact current payroll sources')
        work.refresh_from_db()
        self.assertEqual(work.source_head_id, original_head)
        self.assertRedirects(self.client.post(
            data['recovery'], {**fields, 'input_ids': [data['other_input'], current.pk]},
        ), data['recovery'])
        work.refresh_from_db()
        self.assertNotEqual(work.source_head_id, original_head)
        self.assertRedirects(self.client.post(data['recovery'], {
            'action': 'receive_hr', 'revision': work.revision, 'case_revision': rev(case),
            'snapshot_id': data['snapshot'], 'evidence_id': data['hr_proof'],
        }), data['recovery'])

        self.client.force_login(reviewer)
        for pk in (data['other_input'], current.pk):
            self.assertRedirects(decide('input', pk, 'approve', f'approve-source-{pk}'), data['decision'])
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        combined = flow.run(work, 'combine')
        self.assertRedirects(decide('run', combined.pk, 'approve', 'approve-combination'), data['decision'])
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        match = flow.run(work, 'match')
        page = self.client.get(data['decision'])
        self.assertContains(page, 'Matched staff')
        self.assertContains(page, 'Ask HR to correct this match')
        self.assertNotContains(page, 'E002')
        self.assertRedirects(decide('run', match.pk, 'return', 'return-match', sample.MATCH_NOTE), data['decision'])
        result = self.client.get(data['decision'])
        self.assertContains(result, sample.MATCH_NOTE)
        self.assertContains(result, 'Staff match returned')
        self.assertContains(decide('run', match.pk, 'return', 'return-match', 'Different details'), 'Review operation note changed')
        correction = reverse('design_payroll_corrections', args=[case.pk])
        exact_correction = f'{correction}?match={match.pk}'
        values = {'action': 'hr_correction', 'run': match.pk, 'revision': rev(case),
                  'operation_key': 'review-correction', 'evidence': data['correction_proof']}
        self.assertContains(self.client.get(exact_correction), 'payroll-hr-correction')
        refused = self.client.post(exact_correction, {**values, 'run': combined.pk}, follow=True)
        self.assertContains(refused, 'Choose a permitted command')
        self.assertFalse(PayrollHRFollowup.objects.filter(run=match).exists())
        self.assertRedirects(self.client.post(exact_correction, values), correction)
        self.assertTrue(PayrollHRFollowup.objects.filter(run=match, actor=reviewer).exists())
        note = PayrollReviewNote.objects.get(review__run=match)
        with self.assertRaisesMessage(DatabaseError, 'PSL immutable history'), transaction.atomic():
            PayrollReviewNote.objects.filter(pk=note.pk).update(note='Replaced history')
        self.assertFalse(PayrollPublication.objects.filter(request__case=case).exists())
        self.assertTrue(PayrollReview.objects.filter(pk=input_return.pk).exists())
        self.assertNotIn(sample.MATCH_NOTE, str(list(Audit.objects.filter(case=case).values_list('data', flat=True))))

        aggregate = get_user_model().objects.get(pk=data['recipient'])
        self.client.force_login(aggregate)
        self.assertNotContains(self.client.get(data['inputs_page']), rejected.source_sha256)
        self.assertNotContains(self.client.get(data['inputs_page']), sample.MATCH_NOTE)
        Grant.objects.filter(case=case, user=reviewer, action='payroll.review').update(active=False)
        self.client.force_login(maker)
        self.assertNotContains(self.client.get(data['decision']), sample.MATCH_NOTE)
