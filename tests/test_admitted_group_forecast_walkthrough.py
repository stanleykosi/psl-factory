from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.documents.models import ControlledReview, Publication, PublicationReceipt
from apps.identity import staff
from apps.identity.models import Grant
from apps.policy.models import Configuration
from apps.policy.services import active_component, transition
from apps.workflows import factory, factory_forecast as flow
from apps.workflows.models import FactoryWork
from tests import railway_admitted_group_forecast_seed as seed, railway_admitted_schedule_seed as admission_seed
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_staff_profiles import configured


@patch.dict('os.environ', {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                         'PSL_COMPOSED_WALKTHROUGH': '1'})
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class AdmittedGroupForecastWalkthroughTests(TestCase):
    def test_return_and_narrowed_disclosure_require_fresh_independent_approval(self):
        self.enterContext(patch.object(timezone, 'localdate', return_value=timezone.localdate()))
        data = configured()
        origin = data['scopes'][0]['case']
        reviewer = get_user_model().objects.create_user('psl-agent-trial')
        invitation, token = staff.invite(data['actor'], origin.pk, 'sample-group-preparer', 'Sample group preparer',
            'sample-group-preparer@example.invalid', ['case.read'], rev(origin), profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!forecast.account.972')
        original_grants = set(Grant.objects.filter(user=maker).values_list('case_id', 'action', 'active'))
        sample = seed.prepare(invitation.pk, maker.pk)
        work = FactoryWork.objects.get(pk=sample['work'], actor=maker, case__synthetic=True)
        case = work.case
        self.assertEqual(seed.prepare(invitation.pk, maker.pk), dict(sample, preserved=True))
        self.assertEqual(set(Grant.objects.filter(user=maker).exclude(case=case).values_list('case_id', 'action', 'active')),
                         original_grants)
        old = flow.document(work)
        self.assertFalse(old.version.reviews.exists())
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())
        self.assertEqual(old.version.created_by_id, maker.pk)
        decision_path = sample['decision_path']

        def review_fields(verdict, version_id):
            return {'action': 'group_review', 'work_revision': work.revision, 'revision': rev(case),
                    'selected_scenario': sample['selection']['scenario_id'], 'version': version_id,
                    'role': 'Finance', 'verdict': verdict, 'reason': 'Exact synthetic group content reviewed.'}

        self.client.force_login(maker)
        self.assertEqual(self.client.post(decision_path, review_fields('approve', old.version_id)).status_code, 403)
        self.client.force_login(reviewer)
        self.assertContains(self.client.get(decision_path), 'Exact group disclosure decision')
        self.assertRedirects(self.client.post(decision_path, review_fields('return', old.version_id)), decision_path,
                             fetch_redirect_response=False)
        self.assertEqual(ControlledReview.objects.get(version=old.version).verdict, 'return')

        self.client.force_login(maker)
        disclosure = {'action': 'group_rules', 'work_revision': work.revision, 'case_revision': rev(case),
            'base_configuration': sample['configuration'], 'rows': ['receipt-1'], 'fields': ['kind', 'residual'],
            'metadata': ['currency', 'basis', 'as_of'], 'recipients': [sample['recipient']], 'reviewer_roles': ['Finance'],
            'publisher_roles': ['Finance'], 'allow_preparer_review': 'no', 'oracle': sample['corrected_oracle'],
            'decision': sample['decision'], 'effective_from': timezone.now().isoformat()}
        self.assertRedirects(self.client.post(decision_path, disclosure), decision_path, fetch_redirect_response=False)
        successor = Configuration.objects.filter(case=case, component='D10.audience_projection_rules').latest('pk')
        self.assertEqual(active_component('D10.audience_projection_rules', case).pk, sample['configuration'])
        transition(reviewer, successor.pk, 'validated')
        transition(reviewer, successor.pk, 'active')
        work.refresh_from_db()
        flow.correct(maker, work.pk, work.revision, rev(case), sample['selection'], 'Prepare from the narrowed disclosure.')
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        fresh = flow.document(work)
        self.assertNotEqual(fresh.version_id, old.version_id)
        self.assertEqual(fresh.snapshot['projection']['fields'], ['kind', 'residual'])
        self.assertFalse(fresh.version.reviews.exists())

        self.client.force_login(reviewer)
        self.assertRedirects(self.client.post(decision_path, review_fields('approve', fresh.version_id)), decision_path,
                             fetch_redirect_response=False)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertEqual(work.status, 'verified', work.finding)
        receipt = PublicationReceipt.objects.get(publication__factory_work=work)
        self.assertEqual((receipt.publication.version_id, receipt.recipient_id), (fresh.version_id, sample['recipient']))
        self.assertEqual(old.version.reviews.get().verdict, 'return')
