from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.core.models import Case
from apps.finance import payroll
from apps.finance.hrfinance_models import HRHandoffRecord
from apps.finance.payroll_models import PayrollInput, PayrollPublication, PayrollReportReceipt, PayrollReview, PayrollRun
from apps.identity import staff
from apps.identity.models import Grant
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import railway_admitted_payroll_draft_seed as seed, railway_admitted_schedule_seed as admission_seed
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_staff_profiles import configured


@patch.dict('os.environ', {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                         'PSL_COMPOSED_WALKTHROUGH': '1', seed.GUARD: '1'})
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class AdmittedPayrollDraftWalkthroughTests(TestCase):
    def test_guarded_held_combination_leaves_the_exact_review_and_own_receipt_open(self):
        self.assertEqual(connection.vendor, 'postgresql')
        data = configured()
        origin = data['scopes'][0]['case']
        users = get_user_model().objects
        reviewer = users.create_user('psl-agent-trial')
        invitation, token = staff.invite(data['actor'], origin.pk, 'sample-payroll-draft-maker', 'Sample payroll maker',
            'sample-payroll-draft-maker@example.invalid', ['case.read'], rev(origin), profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!payroll-draft.471')
        grants = Grant.objects.filter(user__in=(maker, reviewer))
        before = set(grants.values_list('user_id', 'case_id', 'action', 'active'))
        with patch.dict('os.environ', {seed.GUARD: '0'}), self.assertRaises(RuntimeError):
            seed.prepare(invitation.pk, maker.pk)
        with self.assertRaises(RuntimeError):
            seed.prepare(invitation.pk, reviewer.pk)
        self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())

        specimen = seed.prepare(invitation.pk, maker.pk)
        case = Case.objects.get(pk=specimen['case'], synthetic=True)
        self.assertEqual(seed.prepare(invitation.pk, maker.pk), dict(specimen, preserved=True))
        self.assertEqual(set(grants.exclude(case=case).values_list('user_id', 'case_id', 'action', 'active')), before)
        self.assertEqual(set(grants.filter(case=case, active=True).values_list('user_id', 'action')),
                         {(maker.pk, action) for action in seed.MAKER_ACTIONS}
                         | {(reviewer.pk, action) for action in seed.REVIEWER_ACTIONS})
        owner = users.get(username=f'sample-payroll-draft-source-holder-{invitation.pk}')
        recipient = users.get(username=f'sample-payroll-draft-aggregate-reader-{invitation.pk}')
        self.assertFalse(owner.has_usable_password())
        self.assertFalse(recipient.has_usable_password())
        self.assertTrue(FactoryWork.objects.filter(case=case, actor=maker, pk=specimen['work']).exists())
        combined = PayrollRun.objects.get(pk=specimen['combined'], request__case=case)
        self.assertEqual((combined.actor_id, combined.kind, combined.metadata['status']), (maker.pk, 'combine', 'held'))
        held = PayrollInput.objects.get(request__case=case, pk=specimen['inputs'][1], actor=owner)
        self.assertEqual([row['source_amount'] for row in held.payload['rows']], ['150', '200', '50'])
        self.assertEqual([row['amount'] for row in held.payload['rows']], [None, None, None])
        _, eligible = payroll.draft_matching.scope(reviewer, combined)
        self.assertEqual(payroll.draft_matching.summary(combined, eligible),
                         {'eligible_rows': 1, 'held_rows': 2, 'known_amount': '100', 'currency': 'TEST'})

        self.client.force_login(reviewer)
        self.assertContains(self.client.get(specimen['decision_path']), 'Approve eligible rows for draft matching')
        self.client.force_login(maker)
        self.assertNotContains(self.client.get(specimen['decision_path']), 'Approve eligible rows for draft matching')
        self.assertFalse(HRHandoffRecord.objects.filter(snapshot_id=specimen['snapshot'], actor=maker, kind='receipt').exists())
        self.assertFalse(FactoryProgress.objects.filter(work_id=specimen['work']).exists())
        self.assertFalse(PayrollReview.objects.filter(request__case=case).exists())
        self.assertEqual(PayrollRun.objects.filter(request__case=case).count(), 1)
        self.assertFalse(PayrollPublication.objects.filter(request__case=case).exists())
        self.assertFalse(PayrollReportReceipt.objects.filter(publication__request__case=case).exists())
