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
        result = self.client.post(url, {'action': 'commercial', 'target': response.commercial_id,
            'role': 'CEO', 'verdict': 'approve', 'revision': work.revision, 'case_revision': rev(case),
            'note': 'Reviewed the exact current bid and separately calculated amount.'})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(CommercialDecision.objects.filter(revision=response.commercial, role='CEO', verdict='approve').exists())
        self.assertNotContains(self.client.get(url), 'Final costing decision')
        self.assertFalse(RFPSubmission.objects.filter(response=response).exists())
