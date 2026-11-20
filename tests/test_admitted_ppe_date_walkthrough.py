"""Role-separated asset period Return, revised evidence and exact schedule verification."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Case, Evidence
from apps.finance import ppe
from apps.identity import staff
from apps.identity.models import Grant
from apps.workflows import factory, factory_ppe as flow
from apps.workflows.models import FactoryWork
from tests import railway_admitted_ppe_date_seed as seed, railway_admitted_schedule_seed as admission_seed
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_staff_profiles import configured


ENVIRONMENT = {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
               'PSL_COMPOSED_WALKTHROUGH': '1', seed.GUARD: '1'}


@patch.dict('os.environ', ENVIRONMENT)
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class AdmittedPPEDateWalkthroughTests(TestCase):
    def test_return_requires_distinct_period_explanation_before_fresh_schedule_review(self):
        configuration = configured()
        origin = configuration['scopes'][0]['case']
        reviewer = get_user_model().objects.create_user('psl-agent-trial')
        invitation, token = staff.invite(configuration['actor'], origin.pk, 'sample-invited-asset-dates',
                                         'Sample asset dates preparer', 'sample-asset-dates@example.invalid',
                                         ['case.read'], rev(origin), profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!sample.asset.dates.385')
        source_grants = Grant.objects.filter(user__in=[maker, reviewer])
        before = set(source_grants.values_list('case_id', 'user_id', 'action', 'active'))
        with patch.dict('os.environ', {seed.GUARD: '0'}), self.assertRaises(RuntimeError):
            seed.prepare(invitation.pk, maker.pk)
        self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())
        sample = seed.prepare(invitation.pk, maker.pk)
        self.assertEqual(seed.prepare(invitation.pk, maker.pk), sample)
        case = Case.objects.get(pk=sample['case'], tenant=seed.TENANT, synthetic=True)
        self.assertEqual(set(source_grants.exclude(case=case).values_list('case_id', 'user_id', 'action', 'active')),
                         before)
        self.assertEqual(set(source_grants.filter(case=case, user=reviewer).values_list('action', flat=True)),
                         set(seed.REVIEWER_ACTIONS))
        register = ppe.exact(case, sample['register'], 'ppe_register')
        self.assertEqual((register.actor_id, register.evidence_id), (maker.pk, sample['original']))
        self.assertTrue(register.result['date_basis_ambiguous'])
        self.assertFalse(register.reviews.exists())
        self.assertFalse(FactoryWork.objects.filter(case=case).exists())

        self.client.force_login(maker)
        self.assertContains(self.client.get(sample['start_path']), 'Start asset schedule work')
        start = self.client.post(sample['start_path'], {'definition': flow.DEFINITION, 'case': case.pk,
            'key': 'sample-asset-dates-start', 'reference': sample['reference'], 'revision': rev(case),
            'register_id': register.pk, 'ledger_id': sample['mapping'], 'background': 'on'})
        work = FactoryWork.objects.get(case=case, actor=maker, definition=flow.DEFINITION)
        self.assertRedirects(start, reverse('factory_detail', args=[work.pk]), fetch_redirect_response=False)
        decision = reverse('factory_invoice_decision', args=[work.pk])
        factory.run_until_wait(work.pk)

        def decide(target, purpose, verdict, evidence, note):
            work.refresh_from_db()
            return self.client.post(decision, {'action': 'review', 'target': target.pk, 'purpose': purpose,
                'verdict': verdict, 'evidence': evidence, 'note': note, 'revision': work.revision,
                'case_revision': rev(case)})

        self.assertNotContains(self.client.get(decision), 'Approve exact basis')
        denied = decide(register, 'basis', 'approve', sample['initial_basis'], 'Wrong role for dates.')
        self.assertEqual(denied.status_code, 403)
        self.assertFalse(register.reviews.exists())

        self.client.force_login(reviewer)
        self.assertRedirects(decide(register, 'register', 'approve', sample['review_evidence'],
                                   'The supplied synthetic register is in scope. Review the dates separately.'),
                             decision, fetch_redirect_response=False)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertEqual(flow.report(work, reviewer)['stage'], 'basis_review')
        self.assertIsNone(flow.schedule(work))
        self.assertContains(self.client.get(decision), 'Reporting dates decision')
        returned_reason = 'Explain the difference between the printed label and the reporting period.'
        self.assertRedirects(decide(register, 'basis', 'return', sample['initial_basis'], returned_reason),
                             decision, fetch_redirect_response=False)
        returned = ppe.latest(register, 'basis')
        self.assertEqual((returned.verdict, returned.actor_id, returned.note), ('return', reviewer.pk, returned_reason))
        self.assertContains(self.client.get(decision), returned_reason)
        self.assertIsNone(flow.schedule(work))

        unchanged = decide(register, 'basis', 'approve', sample['initial_basis'], 'Attempt to reuse the first proof.')
        self.assertContains(unchanged, 'Record corrected asset evidence before a fresh Finance decision')
        self.assertEqual(ppe.latest(register, 'basis').pk, returned.pk)
        self.assertIsNone(flow.schedule(work))

        self.client.force_login(maker)
        self.assertNotContains(self.client.get(decision), 'Approve exact basis')
        supplied = self.client.post(sample['evidence_path'], {'action': 'evidence', 'kind': 'ppe_basis_explanation',
            'body': seed.corrected_explanation(sample), 'source': seed.CORRECTED_SOURCE, 'revision': rev(case)})
        self.assertRedirects(supplied, sample['evidence_path'], fetch_redirect_response=False)
        fresh = Evidence.objects.get(case=case, kind='ppe_basis_explanation', source=seed.CORRECTED_SOURCE,
                                     created_by=maker)
        self.assertGreater(fresh.version, returned.evidence.version)
        self.assertNotEqual(fresh.sha256, returned.evidence.sha256)

        self.client.force_login(reviewer)
        self.assertRedirects(decide(register, 'basis', 'approve', fresh.pk,
                                   'The corrected explanation reconciles the reporting period and printed label.'),
                             decision, fetch_redirect_response=False)
        confirmed = ppe.latest(register, 'basis')
        self.assertEqual((confirmed.evidence_id, confirmed.verdict, confirmed.actor_id), (fresh.pk, 'approve', reviewer.pk))
        self.assertTrue(register.reviews.filter(pk=returned.pk, verdict='return').exists())
        factory.run_until_wait(work.pk)
        schedule = flow.schedule(work)
        self.assertIsNotNone(schedule)
        self.assertEqual(schedule.snapshot['basis_review'], confirmed.pk)
        self.assertEqual(schedule.result['status'], 'ready')
        for field, key in [('label_as_of', 'label'), ('period_start', 'period_start'), ('period_end', 'period_end')]:
            self.assertEqual(schedule.result['scope'][field], sample[key])
        work.refresh_from_db()
        self.assertEqual(flow.report(work, reviewer)['stage'], 'output_review')

        self.assertRedirects(decide(schedule, 'schedule', 'approve', sample['review_evidence'],
                                   'Finance reviewed the schedule against the corrected reporting basis.'),
                             decision, fetch_redirect_response=False)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertEqual(work.status, 'verified', work.finding)
        verification = flow.verify(work, reviewer)
        self.assertEqual((verification['register'], verification['schedule'], verification['ledger']),
                         (register.pk, schedule.pk, sample['mapping']))
        self.assertFalse(verification['ledger_posted'])
        self.assertEqual(verification['full_owner_oracle_acceptance'], 'unresolved')
        self.assertContains(self.client.get(decision), 'Open exact reviewed schedule and note reference')
        self.assertEqual(seed.prepare(invitation.pk, maker.pk)['existing_work'], work.pk)
