"""Governed factory planning: real domain services, explicit modes, no provider authority."""
from django.test import TestCase
from django.utils import timezone
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory
from tests.helpers import rev
from tests.finance_analysis_helpers import fixture,METRICS
from tests.factory_accounting_helpers import configured
from django.core.exceptions import ValidationError,PermissionDenied
from django.urls import reverse
from apps.policy.models import Configuration,RegisteredReference
from apps.policy.services import reference_values
from apps.core.services import add_evidence
from tests.helpers import setup_case


class FactoryCoordinatorTests(TestCase):
    def test_configured_native_coordinator_prepares_an_operational_case_without_external_provider(self):
        a,c,e,values,configs,source,template,recipient=fixture(username='coordinator-operator',recipient_username='coordinator-reader',synthetic=False)
        policy=draft_operator_policy(a,c.pk,'OPS.factory_coordinator',{
            'mode':'internal_permitted_step_v1','contract_id':None,'planner_id':a.pk,
            'data_scope':'eligible_actions_and_opaque_citations_v1','max_output_chars':2048},e['policy_decision'].pk,timezone.now())
        transition(a,policy.pk,'validated');transition(a,policy.pk,'active')
        f=configured(a,c,e,source,template,METRICS,provider='governed_factory_v1')
        factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        self.assertEqual(f['work'].status,'waiting',f['work'].finding)
        from apps.workflows.models import HumanTask
        self.assertTrue(HumanTask.objects.filter(case=c,kind='factory_accounting_review',context__purpose='output',status='open').exists())
        from apps.agents.models import AgentRun
        self.assertTrue(AgentRun.objects.filter(case=c,provider='internal_permitted_step_v1').exists())

    def test_unknown_mode_holds_only_coordination_and_cannot_inject_test_provider(self):
        a,c,e,values,configs,source,template,recipient=fixture(username='unknown-coordinator',recipient_username='unknown-coordinator-reader',synthetic=False)
        p=draft_operator_policy(a,c.pk,'OPS.factory_coordinator',{'mode':None,'contract_id':None,'planner_id':None,
            'data_scope':'eligible_actions_and_opaque_citations_v1','max_output_chars':512},e['policy_decision'].pk,timezone.now())
        transition(a,p.pk,'validated');transition(a,p.pk,'active')
        work=configured(a,c,e,source,template,METRICS,provider='governed_factory_v1')['work']
        self.client.force_login(a)
        page=self.client.get(reverse('factory_detail',args=[work.pk]))
        self.assertContains(page,'Choose how this work will be coordinated')
        self.assertContains(page,'Allowance has not been reserved. Configured limit: 30000.')
        self.assertContains(page,'Review work coordination')
        # Budget presentation is distinct from legitimate empty intake coverage.
        setup=page.content.decode().split('<h2>Execution setup</h2>',1)[1].split('</section>',1)[0]
        self.assertNotIn('0 of 0',setup);self.assertNotContains(page,'configuration_needed:')
        queue=self.client.get(reverse('home'),{'queue':'exceptions'})
        self.assertIn(work.pk,[row['work'].pk for row in queue.context['rows']])
        class Trap:
            def choose(self,context):raise AssertionError('Operational work must never invoke a test provider')
        with self.assertRaises(PermissionDenied):factory.run_once(work.pk,provider=Trap())
        work.refresh_from_db();self.assertEqual(work.budget_used,0)
        self.assertFalse(factory.run_once(work.pk));work.refresh_from_db();self.assertEqual(work.status,'configuration_needed')
        self.assertEqual(work.budget_used,0)
        from apps.finance import analysis
        mapping=analysis.map_source(a,c.pk,source.pk,[],rev(c));self.assertEqual(mapping.kind,'mapping')


class CoordinatorConfigurationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor,cls.case=setup_case(username='coordination-owner',synthetic=False)
        cls.proof=add_evidence(cls.actor,cls.case.pk,'policy_decision','Isolated test decision; no live PSL policy','synthetic:test')

    def test_structured_unknown_settings_have_native_draft_validate_activate_lifecycle_and_csrf(self):
        from django.test import Client
        a,c,e=self.actor,self.case,self.proof;self.client.force_login(a)
        url=reverse('factory_coordinator_configuration',args=[c.pk])
        response=self.client.get(url);self.assertEqual(response.status_code,200);self.assertContains(response,'Work coordination')
        self.assertEqual(response['Cache-Control'],'no-store')
        secure=Client(enforce_csrf_checks=True);secure.force_login(a)
        self.assertEqual(secure.post(url,{'action':'draft'}).status_code,403)
        response=self.client.post(url,{'action':'draft','mode':'','planner_id':'','contract_id':'','max_output_chars':512,'evidence':e.pk})
        self.assertEqual(response.status_code,302)
        config=Configuration.objects.get(component='OPS.factory_coordinator')
        for state in ['validated','active']:self.assertEqual(self.client.post(url,{'action':'transition','configuration':config.pk,'state':state}).status_code,302)
        value=reference_values(config)[0]
        self.assertIsNone(value['mode']);self.assertIsNone(value['planner_id']);self.assertIsNone(value['contract_id'])

    def test_invalid_or_unauthorised_principal_and_raw_data_fields_are_rejected(self):
        a,c,e=self.actor,self.case,self.proof
        content={'mode':'internal_permitted_step_v1','planner_id':a.pk,'contract_id':None,
            'data_scope':'eligible_actions_and_opaque_citations_v1','max_output_chars':512}
        for changes in [{'planner_id':True},{'planner_id':9999999},{'data_scope':'raw_finance'},{'quotes':['Private text']},{'mode':'model_can_approve'},{'max_output_chars':2049}]:
            with self.subTest(changes=changes):
                config=draft_operator_policy(a,c.pk,'OPS.factory_coordinator',dict(content,**changes),e.pk,timezone.now())
                with self.assertRaises(ValidationError):transition(a,config.pk,'validated')
                self.assertEqual(config.states.latest('pk').state,'draft')

    def test_profile_ui_persists_explicit_v2_provider_and_preserves_v1_scope_guard(self):
        import json
        from pathlib import Path
        a,c,e=self.actor,self.case,self.proof;self.client.force_login(a)
        url=reverse('factory_configuration',args=[c.pk])
        value=json.loads(Path('fixtures/factory-accounting.json').read_text())
        value.update(action='draft',definition='pmo-finance/v1',provider='governed_factory_v1',required_evidence_kinds='plan,completion',evidence=e.pk,
            information_resolver_id=a.pk,executor_id=a.pk)
        response=self.client.post(url,value);self.assertEqual(response.status_code,302)
        config=Configuration.objects.get(component='OPS.factory_execution')
        self.assertEqual(reference_values(config)[0]['provider'],'governed_factory_v1')
        self.assertTrue(RegisteredReference.objects.get(ref=config.envelope['value']['artifact_ref']).schema_ref.endswith('/v2'))
        value['provider']='synthetic_factory_v1';before=Configuration.objects.count()
        response=self.client.post(url,value);self.assertEqual(response.status_code,200)
        self.assertEqual(Configuration.objects.count(),before)
        self.assertContains(response,'Synthetic factory provider cannot activate for operational data')
