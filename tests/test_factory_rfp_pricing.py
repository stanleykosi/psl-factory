from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.identity.models import Grant
from apps.pmo import rfp
from apps.pmo.models import CommercialDecision
from tests import factory_rfp_helpers, test_rfp
from tests.helpers import rev


class FactoryRFPPricingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = factory_rfp_helpers.configured()
        cls.work = factory_rfp_helpers.start(cls.data)

    def test_pricing_keeps_supplied_legacy_reference_separate_from_calculated_amounts(self):
        actor, case = self.data['actor'], self.data['case']
        self.client.force_login(actor)
        url = reverse('factory_rfp_pricing', args=[self.work.pk])
        initial_revision = rev(case)
        page = self.client.get(url)
        self.assertContains(page, 'A costing reference was supplied. Its calculated amounts are unavailable here.')
        self.assertContains(page, 'Not yet recorded')
        self.assertContains(self.client.get(reverse('factory_detail', args=[self.work.pk])),
                            f'href="{url}"')
        self.assertEqual(rev(case), initial_revision)
        self.assertEqual(self.client.post(url, {}).status_code, 405)
        Grant.objects.filter(case=case, user=actor, action='costing.source.read').update(active=False)
        self.assertContains(self.client.get(url), 'Your access does not include the calculation amounts.')

    def test_exact_recorded_proposal_decisions_and_current_access(self):
        actor, case, evidence = self.data['actor'], self.data['case'], self.data['evidence']
        response = test_rfp.response(actor, case, evidence)
        test_rfp.approve(actor, case, evidence, response)
        self.client.force_login(actor)
        url = reverse('factory_rfp_pricing', args=[self.work.pk])
        page = self.client.get(url)
        self.assertContains(page, 'Proposal version')
        self.assertContains(page, 'Approved', count=3)
        self.assertEqual(CommercialDecision.objects.filter(revision=response.commercial).count(), 3)
        Grant.objects.filter(case=case, user=actor, action='rfp.read').update(active=False)
        self.assertIn(self.client.get(url).status_code, (403, 404))

    def test_original_security_contributor_revocation_holds_estimate(self):
        actor, case, evidence = self.data['actor'], self.data['case'], self.data['evidence']
        security = get_user_model().objects.create_user('sample-security-contributor')
        grant = Grant.objects.create(case=case, user=security, action='rfp.contribute:Security')
        rfp.contribute(security, case.pk, 'Security', evidence['security_estimate'].pk, rev(case))
        self.client.force_login(actor)
        url = reverse('factory_rfp_pricing', args=[self.work.pk])
        self.assertNotContains(self.client.get(url), 'Total unknown until the Engineering and Security inputs are recorded.')
        grant.active = False
        grant.save(update_fields=['active'])
        self.assertContains(self.client.get(url), 'Total unknown until the Engineering and Security inputs are recorded.')


class FactoryFinalCostingDecisionTests(TestCase):
    def test_final_costing_shows_exact_figures_and_earlier_decisions_then_records_current_approval(self):
        from apps.pmo.models import RFPSubmission

        work, response, run = factory_rfp_helpers.final_costing_wait()
        actor, case = work.actor, work.case
        self.client.force_login(actor)
        url = reverse('factory_invoice_decision', args=[work.pk])
        page = self.client.get(url)
        self.assertContains(page, 'Final costing decision')
        self.assertContains(page, 'Project manager · Approved')
        self.assertContains(page, 'Head of project management · Approved')
        self.assertContains(page, 'Amounts come from the reviewed calculation for these inputs.')
        for item in run.result['values']:
            self.assertContains(page, item['value'])
        root = f'/api/v1/work/{work.pk}'
        pricing = self.client.get(root + '/bid-pricing').json()
        self.assertEqual(pricing['commercial_revision_id'], response.commercial_id)
        self.assertEqual({row['value'] for row in pricing['amounts']}, {item['value'] for item in run.result['values']})
        result = self.client.post(root + '/reviews', {'kind': 'bid', 'subject': 'commercial',
            'target_id': response.commercial_id, 'role': 'CEO', 'verdict': 'approve',
            'expected_revision': pricing['expected_revision'], 'case_revision': pricing['case_revision'],
            'evidence_id': None, 'note': 'Reviewed the exact current bid and separately calculated amount.'},
            content_type='application/json')
        self.assertEqual(result.status_code, 200, result.content)
        after = self.client.get(root + '/bid-pricing').json()
        self.assertEqual(len(after['approvals']), 3)
        self.assertTrue(all(row['status'] == 'Approved' and row['recorded_at'] for row in after['approvals']))
        self.assertTrue(CommercialDecision.objects.filter(revision=response.commercial, role='CEO', verdict='approve').exists())
        self.assertNotContains(self.client.get(url), 'Final costing decision')
        self.assertFalse(RFPSubmission.objects.filter(response=response).exists())


class FactoryBidAdjustmentTests(TestCase):
    def test_finance_lead_approves_exact_naira_price_before_it_changes(self):
        from apps.pmo.costing_models import CostingBinding
        from apps.workflows import factory, factory_rfp, factory_rfp_adjustments as adjustments
        from tests.helpers import admit_department

        work, original, base = factory_rfp_helpers.final_costing_wait(adjustable=True)
        lead, staff = admit_department(work.actor, work.case, 'finance-lead', member=True)
        url = f'/api/v1/work/{work.pk}/bid-pricing'
        self.client.force_login(staff)
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200, page.content)
        self.assertTrue(page.json()['can_propose'])
        self.assertIn({'key': 'output:cost', 'kind': 'output', 'label': 'cost', 'amount': '20.00'},
                      page.json()['finance_targets'])
        versions = {key: page.json()[key] for key in ('expected_revision', 'case_revision')}
        response = self.client.post(url, {**versions, 'action': 'propose', 'target': 'output:cost',
            'amount': '70.25', 'reason': 'Reprice installation after the updated estimate.'},
            content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        page = self.client.get(url).json()
        self.assertIn({'key': 'cost', 'unit': 'NGN', 'value': '20.00'}, page['amounts'])
        proposal_id = page['finance_pending']['id']
        command = {**versions, 'case_revision': page['case_revision'], 'action': 'approve',
                   'proposal_id': proposal_id, 'reason': 'Verified the revised installation estimate.'}
        self.assertEqual(self.client.post(url, command, content_type='application/json').status_code, 403)
        self.client.force_login(lead)
        self.assertTrue(self.client.get(url).json()['can_decide'])
        response = self.client.post(url, command, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        work.refresh_from_db()
        changed = CostingBinding.objects.get(costing_id=factory_rfp.inputs(work)['sources']['costing']).run
        self.assertEqual(changed.result['values'][0]['value'], '70.25')
        self.assertEqual(changed.snapshot['sources'], base.snapshot['sources'])
        self.assertEqual(work.case.audit.get(action=adjustments.APPROVED, data__proposal=proposal_id).actor_id, lead.pk)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        current = factory_rfp.response_for(work)
        self.assertIsNotNone(current, work.finding)
        self.assertEqual(current.commercial.previous_id, original.commercial_id)
        self.assertFalse(current.commercial.decisions.exists())
        read = self.client.get(url).json()
        self.assertIn({'key': 'cost', 'unit': 'NGN', 'value': '70.25'}, read['amounts'])
        self.assertIsNone(read['finance_pending'])

    def test_adjustment_recalculates_native_figures_and_starts_new_decisions(self):
        from apps.pmo.costing_models import CostingBinding, CostingRun
        from apps.pmo.models import RFPSubmission
        from apps.workflows import factory, factory_rfp

        work, original, base_run = factory_rfp_helpers.final_costing_wait(adjustable=True)
        actor, case = work.actor, work.case
        self.client.force_login(actor)
        url = reverse('factory_rfp_pricing', args=[work.pk])
        self.assertNotContains(self.client.get(url), 'Apply adjustment')
        authority = factory_rfp_helpers.configure_sample_adjustment(actor, case, base_run)
        posted = {'action': 'adjust', 'target': 'adjustment', 'amount': '5.25',
                  'reason': 'Apply the supplied synthetic change.', 'revision': work.revision, 'case_revision': rev(case)}
        count = CostingRun.objects.count()
        self.assertContains(self.client.post(url, {**posted, 'amount': '7.01'}), 'exceed the configured limit')
        self.assertEqual(CostingRun.objects.count(), count)
        self.assertContains(self.client.get(url), 'Add an adjustment')
        page = self.client.post(url, posted, follow=True)
        self.assertContains(page, '25.25')
        self.assertContains(page, 'The updated bid requires fresh decisions')
        self.assertContains(page, 'Adjustment history')
        self.assertEqual(CostingRun.objects.count(), count + 1)
        self.assertContains(self.client.post(url, posted), 'Stale revision')
        work.refresh_from_db()
        selected = factory_rfp.inputs(work)
        replacement = CostingBinding.objects.get(costing_id=selected['sources']['costing']).run
        self.assertEqual(replacement.snapshot['sources'], base_run.snapshot['sources'])
        self.assertEqual(replacement.result['values'], [{'key': 'cost', 'unit': 'NGN', 'value': '25.25'}])
        audit = case.audit.get(action='factory.rfp_costing_adjusted')
        self.assertIn(authority.pk, audit.data['authority'].values())
        self.assertEqual(audit.data['previous_run'], base_run.pk)
        self.assertEqual(audit.data['current_run'], replacement.pk)
        next_post = {**posted, 'revision': work.revision, 'case_revision': rev(case), 'amount': '2.00'}
        self.assertContains(self.client.post(url, next_post), 'exceed the configured limit')
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        current = factory_rfp.response_for(work)
        self.assertIsNotNone(current, work.finding)
        self.assertNotEqual(current.pk, original.pk)
        self.assertEqual(current.commercial.previous_id, original.commercial_id)
        self.assertEqual(original.commercial.decisions.count(), 2)
        self.assertFalse(current.commercial.decisions.exists())
        self.assertFalse(current.reviews.exists())
        self.assertFalse(RFPSubmission.objects.filter(response__rfp=original.rfp).exists())

    def test_api_adjustment_recalculates_current_bid_without_reusing_old_human_decisions(self):
        from apps.workflows import factory, factory_rfp

        work, original, run = factory_rfp_helpers.final_costing_wait(adjustable=True)
        actor, case = work.actor, work.case
        self.client.force_login(actor)
        url = f'/api/v1/work/{work.pk}/bid-pricing'
        factory_rfp_helpers.configure_sample_adjustment(actor, case, run)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        page = response.json()
        self.assertEqual(page['adjustment_run_id'], run.pk)
        self.assertEqual(page['adjustment_targets'][0]['key'], 'adjustment')
        versions = {key: page[key] for key in ('expected_revision', 'case_revision')}
        values = {**versions, 'target': 'adjustment', 'amount': '5.25', 'reason': 'Reviewed synthetic change.'}
        excess = self.client.post(url, dict(values, amount='7.01'), content_type='application/json')
        self.assertNotEqual(excess.status_code, 200)
        adjusted = self.client.post(url, values, content_type='application/json')
        self.assertEqual(adjusted.status_code, 200, adjusted.content)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        current = factory_rfp.response_for(work)
        self.assertEqual(current.commercial.previous_id, original.commercial_id)
        self.assertFalse(current.commercial.decisions.exists())
        self.assertIn({'key': 'cost', 'unit': 'NGN', 'value': '25.25'}, self.client.get(url).json()['amounts'])
