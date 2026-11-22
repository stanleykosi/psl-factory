"""Synthetic dates from typed intake through owner-separated configuration and final review."""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case, Evidence
from apps.finance import ppe, ppe_dates
from apps.finance.models import ScheduleWork
from apps.identity import staff
from apps.identity.models import Grant
from apps.policy.models import Configuration
from apps.policy.services import resolve
from apps.workflows import factory, factory_ppe as flow
from apps.workflows.models import FactoryWork
from tests import railway_admitted_ppe_asset_dates_seed as seed, railway_admitted_schedule_seed as admission_seed
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_staff_profiles import configured


ENVIRONMENT = {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
               'PSL_COMPOSED_WALKTHROUGH': '1', seed.GUARD: '1'}


@patch.dict('os.environ', ENVIRONMENT)
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class AdmittedPPEAssetDatesWalkthroughTests(TestCase):
    def test_unknown_date_and_rule_holds_end_only_after_exact_review_and_activation(self):
        initial = configured()
        origin = initial['scopes'][0]['case']
        reviewer = get_user_model().objects.create_user('psl-agent-trial')
        invitation, token = staff.invite(initial['actor'], origin.pk, 'sample-admitted-individual-asset-dates',
                                         'Sample asset dates preparer', 'sample-asset-dates@example.invalid',
                                         ['case.read'], rev(origin), profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!asset.date.demo.974')
        grants = Grant.objects.filter(user__in=[maker, reviewer])
        before = set(grants.values_list('case_id', 'user_id', 'action', 'active'))
        with patch.dict('os.environ', {seed.GUARD: '0'}), self.assertRaises(RuntimeError):
            seed.prepare(invitation.pk, maker.pk)
        self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())
        sample = seed.prepare(invitation.pk, maker.pk)
        self.assertEqual(seed.prepare(invitation.pk, maker.pk), sample)
        case = Case.objects.get(pk=sample['case'], tenant=seed.TENANT, synthetic=True)
        self.assertEqual(set(grants.exclude(case=case).values_list('case_id', 'user_id', 'action', 'active')), before)
        self.assertEqual(set(grants.filter(case=case, user=maker).values_list('action', flat=True)), set(seed.MAKER_ACTIONS))
        self.assertEqual(set(grants.filter(case=case, user=reviewer).values_list('action', flat=True)),
                         set(seed.REVIEWER_ACTIONS))
        self.assertFalse(FactoryWork.objects.filter(case=case).exists())
        self.assertFalse(Evidence.objects.filter(case=case, kind=ppe_dates.FACT_KIND).exists())
        self.assertEqual(resolve(ppe_dates.COMPONENT, case).status, 'MISSING')
        original = ppe.exact(case, sample['register'], 'ppe_register')
        self.assertFalse(original.reviews.exists())
        ppe.review(reviewer, case.pk, original.pk, 'register', 'approve', sample['review_evidence'],
                   'The original supplied-fraction register is in scope.', rev(case))
        ordinary = ppe.prepare(maker, case.pk, 'sample-supplied-fraction-baseline', original.pk, None,
                               sample['mapping'], rev(case))
        self.assertEqual((ordinary.result['status'], ordinary.result['rows'][0]['charge']), ('ready', '100.00'))
        self.assertNotIn(ppe_dates.COMPONENT, ordinary.snapshot['policies'])

        def record(register, date, proof):
            self.client.force_login(maker)
            posted = self.client.post(sample['asset_path'], {'action': 'record_dates', 'register': register.pk,
                'asset_id': sample['asset'], 'delivery_date': sample['delivery_date'], 'in_service_date': date,
                'fraction_basis': ppe_dates.DERIVED, 'evidence': proof, 'revision': rev(case)})
            self.assertRedirects(posted, sample['asset_path'], fetch_redirect_response=False)
            return ScheduleWork.objects.get(case=case, kind='ppe_register', reference=original.reference,
                                            version=register.version + 1)

        unknown = record(original, '', sample['missing_support'])
        started = self.client.post(sample['start_path'], {'definition': flow.DEFINITION,
            'key': 'individual-asset-dates', 'reference': sample['reference'], 'case': case.pk,
            'revision': rev(case), 'register_id': unknown.pk, 'ledger_id': sample['mapping'], 'background': 'on'})
        work = FactoryWork.objects.get(case=case, actor=maker, definition=flow.DEFINITION)
        self.assertRedirects(started, reverse('factory_detail', args=[work.pk]), fetch_redirect_response=False)
        decision = reverse('factory_invoice_decision', args=[work.pk])
        recovery = reverse('factory_invoice_recovery', args=[work.pk])

        def approve(target, purpose, evidence_id):
            work.refresh_from_db()
            response = self.client.post(decision, {'action': 'review', 'target': target.pk, 'purpose': purpose,
                'verdict': 'approve', 'evidence': evidence_id, 'note': 'Independent review of the exact synthetic source.',
                'revision': work.revision, 'case_revision': rev(case)})
            self.assertRedirects(response, decision, fetch_redirect_response=False)

        def rebuild(register):
            self.client.force_login(maker)
            work.refresh_from_db()
            response = self.client.post(recovery, {'action': 'correct', 'register_id': register.pk,
                'ledger_id': sample['mapping'], 'reason': 'Use the exact current supplied dates and reviewed rule.',
                'revision': work.revision, 'case_revision': rev(case)})
            self.assertRedirects(response, recovery, fetch_redirect_response=False)

        self.client.force_login(reviewer)
        approve(unknown, 'register', sample['review_evidence'])
        self.assertIsNone(flow.schedule(work))
        approve(unknown, 'basis', sample['basis_evidence'])
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        held_unknown = flow.schedule(work)
        self.assertIn('in_service_date_unknown', held_unknown.result['rows'][0]['findings'])
        self.assertIsNone(held_unknown.result['rows'][0]['charge'])
        self.assertContains(self.client.get(decision), 'Supply the missing in-service date for Finance review.')
        self.assertNotContains(self.client.get(decision), 'Open exact reviewed schedule and note reference')

        proof = self.client.post(sample['evidence_path'], {'action': 'evidence', 'kind': 'finance_oracle',
            'body': seed.oracle_body(sample), 'source': seed.ORACLE_SOURCE, 'revision': rev(case)})
        self.assertRedirects(proof, sample['evidence_path'], fetch_redirect_response=False)
        oracle = Evidence.objects.get(case=case, kind='finance_oracle', source=seed.ORACLE_SOURCE, created_by=reviewer)
        dated = record(unknown, sample['in_service_date'], sample['supplied_support'])
        rebuild(dated)
        self.assertNotContains(self.client.get(decision), 'Approve exact basis')
        draft = self.client.post(sample['asset_path'], {'action': 'policy', 'component': ppe_dates.COMPONENT,
            'content': json.dumps(seed.configuration(sample, oracle.pk)), 'evidence': sample['policy_evidence'],
            'effective_from': timezone.localtime().strftime('%Y-%m-%d %H:%M:%S'), 'revision': rev(case)})
        self.assertRedirects(draft, sample['asset_path'], fetch_redirect_response=False)
        rule = Configuration.objects.get(case=case, component=ppe_dates.COMPONENT)
        validate = self.client.post(sample['policy_path'], {'configuration': rule.pk, 'action': 'validated'})
        self.assertRedirects(validate, sample['policy_path'], fetch_redirect_response=False)
        denied = self.client.post(sample['policy_path'], {'configuration': rule.pk, 'action': 'active'})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(rule.states.order_by('-pk').first().state, 'validated')

        self.client.force_login(reviewer)
        approve(dated, 'register', sample['review_evidence'])
        approve(dated, 'basis', sample['basis_evidence'])
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        held_rule = flow.schedule(work)
        self.assertIn('in_service_fraction_rule_required', held_rule.result['rows'][0]['findings'])
        self.assertIsNone(held_rule.result['rows'][0]['charge'])
        self.assertContains(self.client.get(decision), 'Activate a reviewed in-service fraction rule and rebuild')
        activated = self.client.post(sample['policy_path'], {'configuration': rule.pk, 'action': 'active'})
        self.assertRedirects(activated, sample['policy_path'], fetch_redirect_response=False)
        self.assertEqual(rule.states.order_by('-pk').first().actor_id, reviewer.pk)

        rebuild(dated)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        calculated = flow.schedule(work)
        self.assertEqual(calculated.result['status'], 'ready')
        self.assertEqual(calculated.result['rows'][0]['charge'], ordinary.result['rows'][0]['charge'])
        self.assertEqual(calculated.result['rows'][0]['used_fraction'], '1')
        self.assertEqual(calculated.snapshot['policies'][ppe_dates.COMPONENT]['id'], rule.pk)
        self.assertEqual(flow.report(work, maker)['stage'], 'output_review')

        self.client.force_login(reviewer)
        approve(calculated, 'schedule', sample['review_evidence'])
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertEqual(work.status, 'verified', work.finding)
        self.assertEqual(flow.verify(work, reviewer)['ledger'], sample['mapping'])
        self.assertFalse(flow.verify(work, reviewer)['ledger_posted'])
        self.assertContains(self.client.get(decision), 'Open exact reviewed schedule and note reference')
        for historical in (held_unknown, held_rule):
            self.assertEqual(ScheduleWork.objects.get(pk=historical.pk).result['status'], 'held')
        self.assertEqual(seed.prepare(invitation.pk, maker.pk)['existing_work'], work.pk)
