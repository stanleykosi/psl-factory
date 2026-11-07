import copy,json
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from apps.pmo import costing as d
from apps.pmo.costing_models import CostingRule,CostingOracle,CostingReview,CostingRun,CostingBinding,CostingAF13Binding
from apps.pmo.services import prepare_baseline,decide,sign_baseline
from apps.policy.services import transition,resolve
from apps.policy.costing_validators import COMPONENT
from apps.identity.models import Grant
from apps.agents.costing import investigate
from adapters.costing import calculate
from .costing_helpers import fixture,evidence,run,review,policy,package
from .helpers import rev

class CostingTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=fixture()
    def test_connected_calculation_cost_approvals_signature_and_af13(self):
        f=self.f;r=run(f);self.assertEqual(r.result['values'][0]['value'],'20.00');self.assertTrue(all(x['matches'] for x in r.result['oracle_results']));b=d.bind(f['actor'],f['case'].pk,r.pk);s=f['sources'];c=f['case']
        prepare_baseline(f['actor'],c.pk,s['plan'].pk,b.costing_id,s['sow'].pk,rev(c))
        with self.assertRaises(ValidationError):sign_baseline(f['actor'],c.pk,s['signature'].pk,rev(c))
        for role in ['PM','Head of PMO','CEO','PMO Lead']:decide(f['actor'],c.pk,role,rev(c))
        from tests.signature_helpers import packet_for
        packet_for(f['actor'], c, s)
        sign_baseline(f['actor'],c.pk,s['signature'].pk,rev(c));p=package(f);d.bind_af13(f['actor'],c.pk,r.pk,p.pk);self.assertEqual(d.package_readiness(p,f['owner'])['status'],'local_rule_oracle_verified');self.assertFalse(r.result['native_workbook_verified'])
    def test_missing_policy_holds_only_calculation_and_legacy_costing_continues(self):
        f=self.f;transition(f['actor'],f['policy'].pk,'revoked');s=f['sources']
        with self.assertRaises(ValidationError):run(f)
        prepare_baseline(f['actor'],f['case'].pk,s['plan'].pk,s['costing'].pk,s['sow'].pk,rev(f['case']));self.assertEqual(resolve(COMPONENT,f['case']).status,'REVOKED')
    def test_unknown_inputs_persist_and_cannot_bind(self):
        f=self.f;i=evidence(f,'p14_inputs',f['values']['scenarios'][1]['inputs']);r=run(f,i);self.assertIsNone(r.result['values'][0]['value']);self.assertEqual(r.result['status'],'held')
        with self.assertRaises(ValidationError):d.bind(f['actor'],f['case'].pk,r.pk)
    def test_independent_expected_values_are_not_generated_or_silently_corrected(self):
        f=self.f;v=copy.deepcopy(f['oracle'].payload);v['scenarios'][0]['expected']['values'][0]['value']='999.00';o=d.capture_oracle(f['tester'],f['case'].pk,f['rule'].pk,'independent',evidence(f,'p14_oracle',v).pk,predecessor=f['oracle'].pk)
        self.assertFalse(d.oracle_results(f['rule'],o)[0]['matches'])
        with self.assertRaises(ValidationError):review(f,o,key='wrong-example')
        self.assertEqual(resolve(COMPONENT,f['case']).status,'INVALID')
    def test_oracle_authority_is_separate_from_case_approval_and_independent(self):
        f=self.f
        with self.assertRaises(PermissionDenied):review(f,f['oracle'],actor=f['actor'],key='case-approver')
        with self.assertRaises(PermissionDenied):review(f,f['oracle'],actor=f['owner'],key='rule-owner')
    def test_source_revocation_holds_configuration_and_bound_cost(self):
        f=self.f;r=run(f);b=d.bind(f['actor'],f['case'].pk,r.pk);Grant.objects.filter(case=f['case'],user=f['tester'],action='costing.source.read').update(active=False)
        self.assertEqual(resolve(COMPONENT,f['case']).status,'INVALID')
        with self.assertRaises(ValidationError):d.verify_costing(b.costing,f['sources']['plan'].pk)
        self.assertFalse(d.report(f['actor'],f['case'].pk,r.pk)['current_usable'])
    def test_rule_correction_preserves_history_and_invalidates_old_bound_evidence(self):
        f=self.f;r=run(f);b=d.bind(f['actor'],f['case'].pk,r.pk);v=copy.deepcopy(f['rule'].payload);v['calculator_version']='v2'
        newer=d.capture_rule(f['actor'],f['case'].pk,'calculator',evidence(f,'p14_rule',v).pk,predecessor=f['rule'].pk);self.assertEqual(newer.version,2)
        with self.assertRaises(ValidationError):d.verify_costing(b.costing,f['sources']['plan'].pk)
        self.assertEqual(CostingRun.objects.get(pk=r.pk).result['values'][0]['value'],'20.00')
    def test_typed_source_rejects_cycles_duplicate_keys_bad_units_and_executable_code(self):
        f=self.f
        for mutation in ['cycle','duplicate','unit','code']:
            v=copy.deepcopy(f['rule'].payload)
            if mutation=='cycle':v['nodes'][0]['operands'][0]='node:cost'
            elif mutation=='duplicate':v['inputs']*=2
            elif mutation=='unit':v['nodes'][0]['operation']='add'
            else:v['implementation']='eval_uploaded_python'
            with self.assertRaises(ValidationError):d.capture_rule(f['actor'],f['case'].pk,'bad-'+mutation,evidence(f,'p14_rule',v).pk)
    def test_exact_inputs_unit_case_budget_and_rounding(self):
        f=self.f;v=f['rule'].payload
        self.assertEqual(calculate(v,f['values']['scenarios'][2]['inputs'])['values'][0]['value'],'1.01')
        for inputs in [[],[{'key':'hours','unit':'day','value':'1'}],[{'key':'hours','unit':'hour','value':1}],[{'key':'hours','unit':'hour','value':'NaN'}]]:
            with self.assertRaises(ValidationError):calculate(v,inputs)
    def test_policy_reference_hash_review_and_original_artifact_shape(self):
        f=self.f;self.assertIsInstance(f['policy'].envelope['value'],dict)
        for changes in [{'rule_sha256':'0'*64},{'oracle_review_id':999}]:
            with self.assertRaises(ValidationError):
                with transaction.atomic():policy(f,dict(f['policy_value'],**changes))
    def test_duplicate_capture_review_calculation_and_binding_are_idempotent(self):
        f=self.f;self.assertEqual(d.capture_rule(f['actor'],f['case'].pk,'calculator',f['rule'].evidence_id).pk,f['rule'].pk);review(f);self.assertEqual(CostingReview.objects.count(),2);r=run(f);self.assertEqual(run(f).pk,r.pk);b=d.bind(f['actor'],f['case'].pk,r.pk);self.assertEqual(d.bind(f['actor'],f['case'].pk,r.pk).pk,b.pk)
        other=evidence(f,'p14_inputs',f['values']['scenarios'][2]['inputs'])
        with self.assertRaises(ValidationError):run(f,other)
    def test_plan_mismatch_and_policy_successor_require_new_calculation(self):
        f=self.f;r=run(f);b=d.bind(f['actor'],f['case'].pk,r.pk);other=evidence(f,'plan','Another exact plan')
        with self.assertRaises(ValidationError):d.verify_costing(b.costing,other.pk)
        policy(f)
        with self.assertRaises(ValidationError):d.current_run(r)
    def test_withdrawal_does_not_erase_proven_historical_calculation(self):
        f=self.f;r=run(f);review(f,f['oracle'],verdict='withdraw',key='withdraw-independent');self.assertEqual(CostingRun.objects.count(),1);self.assertFalse(d.report(f['actor'],f['case'].pk,r.pk)['current_usable'])
    def test_scoped_ui_report_and_private_source_guards(self):
        f=self.f;r=run(f);self.client.force_login(f['actor']);base=f"/cases/{f['case'].pk}/costing/";self.assertContains(self.client.get(base),'Commercial costing rules and independent reference examples');self.assertEqual(self.client.get(base+f'source/rule/{f["rule"].pk}/').status_code,200)
        Grant.objects.filter(case=f['case'],user=f['actor']).exclude(action__in=['case.read','costing.read']).update(active=False);self.assertContains(self.client.get(base),'Read-only access.');self.assertEqual(self.client.get(base+f'source/rule/{f["rule"].pk}/').status_code,403);value=self.client.get(base+f'report/{r.pk}/').json();self.assertNotIn('result',value);self.assertNotIn('inputs',value)
    def test_agents_and_generic_readers_cannot_repackage_private_costing(self):
        f=self.f;run(f);agent=investigate(f['actor'],f['case'].pk);self.assertFalse(agent.result['source_body_read']);self.assertFalse(agent.result['expected_outputs_generated'])
        from apps.agents.services import extract_evidence
        from apps.agents.meetings import suggest_commitments
        from apps.documents import validation as af
        from .validation_helpers import values
        with self.assertRaises(ValidationError):extract_evidence(f['actor'],f['case'].pk,f['rule'].evidence_id,'P14')
        with self.assertRaises(ValidationError):suggest_commitments(f['actor'],f['case'].pk,f['oracle'].evidence_id,rev(f['case']))
        with self.assertRaises(ValidationError):af.capture_source(f['actor'],f['case'].pk,'repackage',f['rule'].evidence_id,values()['metadata'],None)
    def test_all_six_models_have_actual_sql_immutability(self):
        f=self.f;r=run(f);d.bind(f['actor'],f['case'].pk,r.pk);p=package(f);d.bind_af13(f['actor'],f['case'].pk,r.pk,p.pk)
        for model in [CostingRule,CostingOracle,CostingReview,CostingRun,CostingBinding,CostingAF13Binding]:
            with self.assertRaises(DatabaseError):
                with transaction.atomic():
                    with connection.cursor() as cur:cur.execute('UPDATE '+model._meta.db_table+' SET id=id WHERE id=%s',[model.objects.first().pk])
    def test_af13_binding_stales_after_source_change_without_granting_acceptance(self):
        f=self.f;r=run(f);p=package(f);d.bind_af13(f['actor'],f['case'].pk,r.pk,p.pk);review(f,f['oracle'],verdict='withdraw',key='withdraw-after-binding');self.assertEqual(d.package_readiness(p,f['owner'])['status'],'reassessment_required')

    def test_pending_owner_capture_before_configuration(self):
        f=self.f;v=copy.deepcopy(f['rule'].payload);v.update(owner_id=None,owner_role=None,oracle_owner_id=None,oracle_role=None)
        r=d.capture_rule(f['actor'],f['case'].pk,'pending-owner',evidence(f,'p14_rule',v).pk)
        with self.assertRaises(ValidationError):d.review(f['owner'],f['case'].pk,r.pk,None,'confirm','unknown-owner',f['review_evidence'].pk)
        self.assertIsNone(r.payload['owner_id'])
    def test_division_by_zero_unknown_parameter_and_explicit_rounding_modes(self):
        f=self.f;v=copy.deepcopy(f['rule'].payload);v['nodes'][0].update(operation='divide',operands=['parameter:rate','input:hours'])
        result=calculate(v,[{'key':'hours','unit':'hour','value':'0'}]);self.assertEqual(result['status'],'held');self.assertIsNone(result['values'][0]['value']);self.assertEqual(result['findings'],['division_by_zero:cost'])
        v=copy.deepcopy(f['rule'].payload);v['parameters'][0]['value']=None;result=calculate(v,f['values']['scenarios'][0]['inputs']);self.assertEqual(result['findings'],['unknown:parameter:rate'])
        for mode,expected in [('half_even','1.00'),('down','1.00'),('half_up','1.01')]:
            v=copy.deepcopy(f['rule'].payload);v['nodes'][0]['rounding']=mode;self.assertEqual(calculate(v,f['values']['scenarios'][2]['inputs'])['values'][0]['value'],expected)
    def test_magnitude_duplicate_input_and_noncanonical_owner_are_held(self):
        f=self.f;v=copy.deepcopy(f['rule'].payload)
        for inputs in [f['values']['scenarios'][0]['inputs']*2,[{'key':'hours','unit':'hour','value':'999999999999999999999999'}]]:
            with self.assertRaises(ValidationError):calculate(v,inputs)
    def test_current_binding_cannot_bypass_existing_commercial_cost_approvals(self):
        from apps.pmo import commercial
        f=self.f;r=run(f);b=d.bind(f['actor'],f['case'].pk,r.pk);sources={k:f['sources'][k].pk for k in ['requirements','engineering_estimate','security_estimate','plan','costing','sow']};sources['costing']=b.costing_id
        context=f['sources']['requirements']
        proposal=commercial.propose(f['actor'],f['case'].pk,sources,context.pk,'Explicit synthetic proposal',rev(f['case']))
        with self.assertRaises(ValidationError):commercial.valid_approvals(proposal)
        review(f,f['oracle'],verdict='withdraw',key='withdraw-before-commercial')
        with self.assertRaises(ValidationError):commercial.decide_proposal(f['actor'],f['case'].pk,proposal.pk,'PM','approve','Current evidence required',rev(f['case']))

    def test_server_rendered_calculation_post_calls_real_domain(self):
        f=self.f;s=f['sources'];self.client.force_login(f['actor']);url=f"/cases/{f['case'].pk}/costing/"
        response=self.client.post(url,{'action':'calculate','revision':rev(f['case']),'plan':s['plan'].pk,'engineering':s['engineering_estimate'].pk,'security':s['security_estimate'].pk,'inputs':f['inputs'].pk,'operation_key':'ui-calculation'})
        self.assertEqual(response.status_code,302);self.assertEqual(CostingRun.objects.get().operation_key,'ui-calculation');self.assertContains(self.client.get(url),'Evidence confirmation history')

    def test_rule_confirmation_does_not_wait_for_oracle_owner_configuration(self):
        f=self.f;v=copy.deepcopy(f['rule'].payload);v.update(oracle_owner_id=None,oracle_role=None);r=d.capture_rule(f['actor'],f['case'].pk,'pending-oracle-owner',evidence(f,'p14_rule',v).pk)
        rr=d.review(f['owner'],f['case'].pk,r.pk,None,'confirm','owner-before-oracle',f['review_evidence'].pk);self.assertEqual(rr.verdict,'confirm')
    def test_costing_hold_does_not_block_independent_quality_review_or_return(self):
        from apps.pmo import commercial
        from apps.policy.services import register_reference
        from .helpers import activate
        f=self.f;r=run(f);b=d.bind(f['actor'],f['case'].pk,r.pk);c=f['case'];s=f['sources'];prepare_baseline(f['actor'],c.pk,s['plan'].pk,b.costing_id,s['sow'].pk,rev(c))
        sources={k:s[k].pk for k in ['requirements','engineering_estimate','security_estimate','plan','costing','sow']};sources['costing']=b.costing_id
        proposal=commercial.propose(f['actor'],c.pk,sources,s['requirements'].pk,'Explicit synthetic proposal',rev(c))
        decision=register_reference(f['actor'],c.pk,'synthetic-return','schema:psl/decision-actions/v1',{'rules':[{'role':'PM','actions':['return']}]},s['policy_decision'].pk);activate(f['actor'],c,'D05.decision_action_matrix',{'artifact_ref':decision.ref,'artifact_version':decision.version,'schema_ref':decision.schema_ref,'sha256':decision.sha256},s['policy_decision'])
        review(f,f['oracle'],verdict='withdraw',key='hold-before-quality')
        returned=commercial.decide_proposal(f['actor'],c.pk,proposal.pk,'PM','return','Return stale costing for fresh evidence',rev(c));self.assertEqual(returned.verdict,'return')
    def test_agent_reports_actual_independent_mismatch_without_generating_expectations(self):
        f=self.f;v=copy.deepcopy(f['oracle'].payload);v['scenarios'][0]['expected']['values'][0]['value']='999.00';o=d.capture_oracle(f['tester'],f['case'].pk,f['rule'].pk,'independent',evidence(f,'p14_oracle',v).pk,predecessor=f['oracle'].pk)
        agent=investigate(f['actor'],f['case'].pk);self.assertEqual(agent.result['independent_comparisons'][0]['oracle'],o.pk);self.assertFalse(agent.result['independent_comparisons'][0]['checks'][0]['matches']);self.assertFalse(agent.result['expected_outputs_generated']);self.assertNotIn('999.00',str(agent.result))

    def test_independent_sow_quality_review_remains_available_during_costing_hold(self):
        f=self.f;r=run(f);b=d.bind(f['actor'],f['case'].pk,r.pk);c=f['case'];s=f['sources'];prepare_baseline(f['actor'],c.pk,s['plan'].pk,b.costing_id,s['sow'].pk,rev(c));review(f,f['oracle'],verdict='withdraw',key='hold-quality')
        quality=decide(f['actor'],c.pk,'PMO Lead',rev(c));self.assertEqual(quality.evidence_id,s['sow'].pk)
        with self.assertRaises(ValidationError):decide(f['actor'],c.pk,'PM',rev(c))
    def test_adapter_rejects_duplicate_json_properties(self):
        from adapters.costing import read,RULE
        with self.assertRaises(ValidationError):read('{"implementation":"declared_decimal_graph_v1","implementation":"changed"}',RULE)
    def test_stored_agent_diagnostics_do_not_retain_private_source_keys(self):
        f=self.f;v=copy.deepcopy(f['oracle'].payload);v['scenarios'][0]['key']='private-client-rate-scenario';v['scenarios'][0]['expected']['values'][0]['value']='999.00';d.capture_oracle(f['tester'],f['case'].pk,f['rule'].pk,'independent',evidence(f,'p14_oracle',v).pk,predecessor=f['oracle'].pk)
        agent=investigate(f['actor'],f['case'].pk);self.assertNotIn('private-client-rate-scenario',str(agent.result));self.assertNotIn('999.00',str(agent.result))
        Grant.objects.filter(case=f['case'],user=f['actor'],action='costing.source.read').update(active=False);self.client.force_login(f['actor']);response=self.client.get(f"/cases/{f['case'].pk}/costing/");self.assertNotContains(response,'private-client-rate-scenario');self.assertNotContains(response,'999.00')

    def test_af13_hash_projection_hides_source_controlled_scenario_names(self):
        f=dict(self.f);v=copy.deepcopy(f['oracle'].payload);v['scenarios'][0]['key']='private-customer-scenario';o=d.capture_oracle(f['tester'],f['case'].pk,f['rule'].pk,'independent',evidence(f,'p14_oracle',v).pk,predecessor=f['oracle'].pk);rr=review(f,o,key='private-scenario-reviewed');f['oracle']=o;f['policy_value']=dict(f['policy_value'],oracle_id=o.pk,oracle_sha256=o.sha256,oracle_review_id=rr.pk);policy(f);r=run(f);p=package(f);d.bind_af13(f['actor'],f['case'].pk,r.pk,p.pk)
        self.assertEqual(d.package_readiness(p,f['owner'])['status'],'local_rule_oracle_verified');self.client.force_login(f['actor']);response=self.client.get(f"/cases/{f['case'].pk}/validation/");self.assertNotContains(response,'private-customer-scenario');self.assertContains(response,'local_rule_oracle_verified')

class PendingCostingTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=fixture(configured=False)
    def test_missing_original_policy_keeps_source_capture_available(self):
        f=self.f;self.assertEqual(resolve(COMPONENT,f['case']).status,'MISSING')
        with self.assertRaises(ValidationError):run(f)
        self.assertEqual(CostingRule.objects.count(),1);self.assertEqual(CostingOracle.objects.count(),1)
        v=copy.deepcopy(f['rule'].payload);v.update(owner_id=None,owner_role=None,oracle_owner_id=None,oracle_role=None);r=d.capture_rule(f['actor'],f['case'].pk,'pending-owner',evidence(f,'p14_rule',v).pk);self.assertIsNone(r.payload['owner_id'])
    def test_operational_case_rejects_synthetic_contract(self):
        f=self.f;f['case'].synthetic=False;f['case'].save(update_fields=['synthetic']);v=copy.deepcopy(f['rule'].payload)
        with self.assertRaises(ValidationError):d.capture_rule(f['actor'],f['case'].pk,'operational',evidence(f,'p14_rule',v).pk)
