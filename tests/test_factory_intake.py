from django.test import TestCase
from django.urls import reverse
from apps.core.models import Case
from apps.identity.models import Grant
from apps.workflows.models import FactoryWork
from apps.workflows.factory_views import intake_options
from tests.helpers import setup_case


# Independently enumerated accepted intake paths, not derived from INTAKES.
EXPECTED_DEFINITIONS={
    'finance-bu/v1','finance-ledger/v1',
    'pmo-weekly-report/v1','pmo-escalation/v1','pmo-minutes/v1',
    'engagement/v1','finance-schedules/v1','finance-ppe/v1','finance-forecast/v1',
    'finance-payroll/v1','pmo-emergency/v1','pmo-change/v1','rfp-response/v1',
    'finance-accounts/v1','planning/v1','commercial/v1','delivery-release/v1',
    'delivery-hypercare/v1','delivery-go-live/v1','delivery-archive/v1',
    'delivery-handover/v1','delivery-closure/v1','pmo-finance/v1',
}


class FactoryIntakeTests(TestCase):
    def test_current_same_project_grants_drive_discovery_and_no_cross_project_union(self):
        actor,case=setup_case(username='synthetic-intake');self.client.force_login(actor)
        self.assertEqual({row['definition'] for row in intake_options(actor)},EXPECTED_DEFINITIONS-{'pmo-weekly-report/v1'})
        Grant.objects.create(user=actor,case=case,action='report.read')
        self.assertEqual({row['definition'] for row in intake_options(actor)},EXPECTED_DEFINITIONS)
        Grant.objects.filter(user=actor).update(active=False)
        other=Case.objects.create(tenant='other-tenant',title='Private other project',kind='project',synthetic=True)
        Grant.objects.update_or_create(user=actor,case=case,action='factory.start',defaults={'active':True})
        Grant.objects.update_or_create(user=actor,case=case,action='case.read',defaults={'active':True})
        Grant.objects.create(user=actor,case=other,action='finance.read')
        Grant.objects.create(user=actor,case=other,action='case.read')
        self.assertEqual(intake_options(actor),[])
        page=self.client.get(reverse('factory_intake'));self.assertContains(page,'No new work is available')
        self.assertNotContains(page,'Private other project');self.assertEqual(page['Cache-Control'],'no-store')
        Grant.objects.update_or_create(user=actor,case=case,action='finance.read',defaults={'active':True})
        self.assertEqual([o['definition'] for o in intake_options(actor)],['pmo-finance/v1'])
        Grant.objects.filter(user=actor,case=case,action='factory.start').update(active=False)
        self.assertEqual(intake_options(actor),[])

    def test_queue_has_one_context_preserving_start_action_and_chooser_reuses_native_forms(self):
        actor,case=setup_case(username='synthetic-intake-layout');self.client.force_login(actor)
        Grant.objects.create(user=actor,case=case,action='report.read')
        page=self.client.get(reverse('home'),{'queue':'active','q':'<script>& project'})
        self.assertContains(page,'Start work',count=1);self.assertNotContains(page,'Start planning work')
        self.assertContains(page,reverse('factory_intake')+'?queue=active&amp;q=%3Cscript%3E%26%20project')
        page=self.client.get(reverse('factory_intake'),{'queue':'active','q':'<script>& project'})
        self.assertContains(page,'What needs to move forward?');self.assertNotContains(page,'<script>')
        self.assertNotContains(page,'Factory intake');self.assertContains(page,'studio.css?v=4')
        self.assertEqual({row['definition'] for row in page.context['options']},EXPECTED_DEFINITIONS)
        for option in page.context['options']:
            form=self.client.get(reverse('factory_create'),{'definition':option['definition']})
            self.assertEqual(form.status_code,200)
        self.assertEqual(FactoryWork.objects.count(),0)

    def test_authentication_method_revocation_and_legacy_invoice_entry_are_preserved(self):
        url=reverse('factory_intake');self.assertEqual(self.client.get(url).status_code,302)
        actor,case=setup_case(username='synthetic-intake-method');self.client.force_login(actor)
        self.assertEqual(self.client.post(url,{'definition':'planning/v1'}).status_code,405)
        page=self.client.get(url,{'queue':'not-a-queue'});self.assertEqual(page.context['queue'],'needs_me')
        self.assertContains(self.client.get(reverse('factory_create')),'Invoice reference')
        actor.is_active=False;actor.save(update_fields=['is_active'])
        self.assertEqual(self.client.get(url).status_code,302)
        self.assertEqual(FactoryWork.objects.count(),0)
