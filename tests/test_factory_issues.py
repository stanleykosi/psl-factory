"""Actual migrated issue coordination, privacy and durable recovery tests."""
import json
from pathlib import Path
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import DatabaseError,transaction
from django.test import TestCase
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import transition
from apps.policy.operator_drafts import draft_operator_policy
from apps.pmo.issues import log_issue,update_issue
from apps.workflows import factory,factory_issues as domain
from apps.workflows.models import FactoryWork,FactoryAttempt,HumanTask
from tests.helpers import setup_case,project_evidence,rev

class FactoryIssueTests(TestCase):
    def setUp(self):
        self.a,self.c=setup_case();self.e=project_evidence(self.a,self.c)
        self.state=log_issue(self.a,self.c.pk,'ISS-FACTORY','Investigate source issue','Delivery',self.a.pk,'Find cause',self.e['requirements'].pk,'Owner intake',rev(self.c))
        value=json.loads(Path('fixtures/factory-issues.json').read_text());value.pop('classification')
        cfg=draft_operator_policy(self.a,self.c.pk,'OPS.factory_issue_execution',value,self.e['policy_decision'].pk,timezone.now())
        transition(self.a,cfg.pk,'validated');transition(self.a,cfg.pk,'active');self.config=cfg
        self.work=domain.start(self.a,self.c.pk,'ISS-WORK',self.state.issue_id,rev(self.c))
    def advance(self):factory.run_until_wait(self.work.pk);self.work.refresh_from_db()
    def respond(self):
        self.work.refresh_from_db();t=domain.tasks(self.work).get(status='open')
        issue,_=domain.source(self.work,self.a)
        operation='progress' if issue.current.acknowledged_at else 'acknowledge'
        return domain.respond(self.a,self.work.pk,self.work.revision,rev(self.c),t.pk,t.revision,operation,self.e['requirements'].pk,'I will investigate cause','Gather source-owner evidence')
    def test_scoped_investigation_owned_followup_verified_without_issue_closure(self):
        self.advance();self.assertEqual(self.work.status,'waiting',self.work.finding)
        attempt=FactoryAttempt.objects.get(activity__work=self.work,activity__kind='ACT04',phase='observed')
        self.assertEqual(attempt.result['investigation']['issue_id'],self.state.issue_id)
        self.assertFalse(attempt.result['investigation']['sla_evaluated'])
        self.respond();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        proof=domain.verify(self.work,self.a);self.assertFalse(proof['issue_resolution_verified'])
        self.state.issue.refresh_from_db();self.assertEqual(self.state.issue.current.status,'Open')
        self.assertEqual(HumanTask.objects.get().kind,'issue_followup')
    def test_stale_source_requires_explicit_refresh_and_shared_budget_is_retained(self):
        self.advance();spent=self.work.budget_used
        update_issue(self.a,self.c.pk,self.state.issue_id,self.state.pk,'manage',self.e['requirements'].pk,'New next action',rev(self.c),next_action='New source action')
        with self.assertRaises(ValidationError):self.respond()
        domain.refresh(self.a,self.work.pk,self.work.revision,rev(self.c),'Adopt current native issue');self.work.refresh_from_db()
        self.assertEqual(self.work.budget_used,spent);self.assertEqual(HumanTask.objects.get().status,'returned')
        self.advance();self.respond();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
    def test_current_owner_only_idempotency_and_forged_completion_denied(self):
        self.assertEqual(domain.start(self.a,self.c.pk,'ISS-WORK',self.state.issue_id,rev(self.c)).pk,self.work.pk)
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
        self.advance();Grant.objects.filter(case=self.c,user=self.a,action='issue.work').update(active=False)
        with self.assertRaises(PermissionDenied):self.respond()
        self.assertEqual(HumanTask.objects.get().status,'open')
    def test_cancel_and_explicit_restart_preserve_owner_task_and_budget(self):
        self.advance();spent=self.work.budget_used
        factory.manage(self.a,self.work.pk,self.work.revision,'cancel');factory.run_once(self.work.pk);self.work.refresh_from_db()
        self.assertEqual(self.work.status,'cancelled');self.assertEqual(HumanTask.objects.get().status,'returned')
        domain.refresh(self.a,self.work.pk,self.work.revision,rev(self.c),'Explicit new instruction',restart=True);self.work.refresh_from_db()
        self.assertEqual(self.work.budget_used,spent);self.advance();self.respond();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
    def test_staff_intake_detail_get_preservation_and_native_owner_post(self):
        self.client.force_login(self.a)
        before=(rev(self.c),self.work.revision,FactoryAttempt.objects.count())
        r=self.client.get(f'/work/{self.work.pk}/');self.assertEqual(r.status_code,200);self.assertContains(r,'Native issue lifecycle')
        self.assertEqual(before,(rev(self.c),FactoryWork.objects.get(pk=self.work.pk).revision,FactoryAttempt.objects.count()))
        self.advance();t=HumanTask.objects.get()
        r=self.client.post(f'/work/{self.work.pk}/',{'action':'respond','revision':self.work.revision,'case_revision':rev(self.c),'task':t.pk,'task_revision':t.revision,'operation':'acknowledge','evidence':self.e['requirements'].pk,'note':'Accountable owner response','next_action':'Gather evidence'})
        self.assertEqual(r.status_code,302);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        self.assertContains(self.client.get('/factory/new/?definition=pmo-issues/v1&case='+str(self.c.pk)),'Current authoritative issue')

    def reference(self,availability='available'):
        from apps.pmo import issue_references as refs
        contract=refs.configure(self.a,self.c.pk,'incident','Synthetic engineering registry',['status','owner'],'synthetic_mock',self.e['policy_decision'].pk,rev(self.c))
        identity=add_evidence(self.a,self.c.pk,'incident','Public reference identity','synthetic:incident')
        payload={'protocol':'issue-reference-readback/v1','source_identity':contract.source_identity,'source_ref':'INC-EXACT','availability':availability,'observed_at':timezone.now().isoformat(),'fields':{'status':'Investigating'} if availability=='available' else {}}
        e=add_evidence(self.a,self.c.pk,'agent_private_issue_readback',json.dumps(payload),'synthetic:issue-source')
        o=refs.observe(self.a,self.c.pk,self.state.issue_id,self.state.pk,contract.pk,'INC-EXACT',e.pk,rev(self.c))
        r=refs.correct(self.a,self.c.pk,self.state.issue_id,self.state.pk,None,[{'kind':'incident','source_ref':'INC-EXACT','evidence_id':identity.pk,'observation_id':o.pk}],[],self.e['requirements'].pk,'Human source selection',rev(self.c))
        domain.refresh(self.a,self.work.pk,self.work.revision,rev(self.c),'Adopt supplied read scope');self.work.refresh_from_db()
        return contract,o,r,payload

    def test_scoped_reference_unknown_availability_and_revoked_read_never_leak(self):
        self.reference('unavailable');self.advance()
        n=domain.report(self.work,self.a)
        self.assertEqual(n['references']['references'][0]['availability'],'unavailable')
        self.assertEqual(n['references']['references'][0]['freshness'],'unknown')
        self.assertFalse(n['external_lifecycle_changed'])
        self.respond();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        Grant.objects.filter(case=self.c,user=self.a,action='issue.reference.incident.read').update(active=False)
        with self.assertRaises(PermissionDenied):domain.verify(self.work,self.a)
        self.client.force_login(self.a)
        page=self.client.get(f'/work/{self.work.pk}/');self.assertEqual(page.status_code,403)
        self.assertNotContains(page,'INC-EXACT',status_code=403);self.assertNotContains(page,'Synthetic engineering registry',status_code=403)
        page=self.client.get('/');self.assertNotContains(page,'INC-EXACT')

    def test_successor_source_invalidates_verification_without_overwriting_prior_result(self):
        _,o,_,payload=self.reference();self.advance();self.respond();self.advance()
        self.assertEqual(self.work.status,'verified',self.work.finding)
        before=FactoryAttempt.objects.filter(activity__work=self.work,activity__kind='ACT13',phase='observed').count()
        payload['availability']='unavailable';payload['fields']={};payload['observed_at']=timezone.now().isoformat()
        add_evidence(self.a,self.c.pk,'agent_private_issue_readback',json.dumps(payload),'synthetic:issue-source')
        with self.assertRaises(ValidationError):domain.verify(self.work,self.a)
        self.assertTrue(domain.projection(self.a,self.work)['readiness_changed'])
        self.assertEqual(before,FactoryAttempt.objects.filter(activity__work=self.work,activity__kind='ACT13',phase='observed').count())

    def test_budget_and_model_choices_do_not_authorize_issue_commands(self):
        from apps.policy.services import reference_values
        value=dict(reference_values(self.config)[0],max_tokens=100)
        p=draft_operator_policy(self.a,self.c.pk,'OPS.factory_issue_execution',value,self.e['policy_decision'].pk,timezone.now())
        transition(self.a,p.pk,'validated');transition(self.a,p.pk,'active')
        self.advance();self.assertEqual(self.work.budget_used,100);self.assertEqual(self.work.status,'blocked')
        self.assertFalse(HumanTask.objects.exists());self.state.issue.refresh_from_db();self.assertEqual(self.state.issue.current_id,self.state.pk)

    def test_forbidden_provider_tool_and_typed_human_approval_attempt_are_denied(self):
        class Wrong:
            def choose(self,context):return {'activity':'ACT11','citations':context['evidence_ids'][:1]}
        self.assertFalse(factory.run_once(self.work.pk,provider=Wrong()));self.work.refresh_from_db();self.assertEqual(self.work.status,'blocked')
        factory.manage(self.a,self.work.pk,self.work.revision,'resume');self.advance();t=HumanTask.objects.get()
        with self.assertRaises(ValidationError):domain.respond(self.a,self.work.pk,self.work.revision,rev(self.c),t.pk,t.revision,'resolve',self.e['requirements'].pk,'No model closure','Next action')
        self.state.issue.refresh_from_db();self.assertEqual(self.state.issue.current_id,self.state.pk)

    def test_independent_native_owner_response_survives_execution_permission_loss(self):
        from django.contrib.auth import get_user_model
        owner=get_user_model().objects.create_user('distinct-issue-owner')
        for action in ['case.read','issue.read','issue.work','issue.own','evidence.add','factory.read']:Grant.objects.create(user=owner,case=self.c,action=action)
        update_issue(self.a,self.c.pk,self.state.issue_id,self.state.pk,'manage',self.e['requirements'].pk,'Assign source owner',rev(self.c),owner_id=owner.pk)
        domain.refresh(self.a,self.work.pk,self.work.revision,rev(self.c),'Adopt responsible owner');self.work.refresh_from_db();self.advance()
        Grant.objects.filter(case=self.c,user=self.a,action='factory.execute').update(active=False)
        t=HumanTask.objects.get()
        domain.respond(owner,self.work.pk,self.work.revision,rev(self.c),t.pk,t.revision,'acknowledge',self.e['requirements'].pk,'Owner acknowledges independently','Gather source evidence')
        self.assertEqual(HumanTask.objects.get().status,'completed')
        self.state.issue.refresh_from_db();self.assertEqual(self.state.issue.current.actor_id,owner.pk)
        self.assertFalse(factory.run_once(self.work.pk));self.work.refresh_from_db();self.assertNotEqual(self.work.status,'verified')

    def test_execution_configuration_ui_keeps_observation_age_unknown(self):
        self.client.force_login(self.a)
        page=self.client.get(f'/cases/{self.c.pk}/factory/configuration/?definition=pmo-issues/v1')
        self.assertEqual(page.status_code,200);self.assertContains(page,'blank means unknown')
        self.assertFalse(page.context['form'].fields['reference_max_age_seconds'].required)

    def configure_planner(self,state):
        from apps.policy.readiness_drafts import draft_readiness_policy
        from apps.policy.readiness_validators import PROVIDER
        from apps.policy.factory_coordinator_validators import PROTOCOL,SCOPE
        from apps.policy.services import reference_values
        from apps.workflows import readiness,readiness_delivery
        from tests.helpers import roles
        roles(self.a,self.c,self.e['policy_decision']);state['contract_version']=PROTOCOL
        rules=json.loads(Path('fixtures/integration-readiness.json').read_text())['rules']
        rules.update(probe_user_id=self.a.pk,reviewer_id=self.a.pk,probe_role='PM',reviewer_role='PM',independent_review=False)
        p=draft_readiness_policy(self.a,self.c.pk,PROVIDER,rules,self.e['policy_decision'].pk,timezone.now())
        transition(self.a,p.pk,'validated');transition(self.a,p.pk,'active')
        proof=lambda kind:add_evidence(self.a,self.c.pk,kind,'Explicit isolated source-independent planner proof','synthetic:issue-planner')
        contract=readiness.capture(self.a,self.c.pk,'issue-planner',{'kind':'provider','family':'provider','implementation':'authenticated_json_v1','target_key':'endpoint:fixture','credential_ref':'secret:fixture','credential_revision':'fixture-v1','principal_ref':'principal:fixture','contract_version':PROTOCOL,'model_id':'fixture-model','capabilities':['health','receipt_lookup','evaluation'],'data_scope':'public_canary_and_scoped_receipt_metadata_only'},proof('integration_contract').pk)
        for kind in ['health','evaluation']:
            job=readiness_delivery.reserve(self.a,self.c.pk,contract.pk,'issue-'+kind,kind);readiness_delivery.run_once(case_id=self.c.pk);job.refresh_from_db();self.assertEqual(job.status,'confirmed')
        assessment=readiness.assess(self.a,self.c.pk,contract.pk,'ready');self.assertTrue(assessment.result['capability_ready'])
        readiness.review(self.a,self.c.pk,assessment.pk,'confirm','issue-planner-approved',proof('integration_review').pk)
        readiness.select(self.a,self.c.pk,contract.pk,proof('integration_selection').pk)
        p=draft_operator_policy(self.a,self.c.pk,'OPS.factory_coordinator',{'mode':'authenticated_planner_v1','contract_id':contract.pk,'planner_id':self.a.pk,'data_scope':SCOPE,'max_output_chars':2048},self.e['policy_decision'].pk,timezone.now())
        transition(self.a,p.pk,'validated');transition(self.a,p.pk,'active')
        value=dict(reference_values(self.config)[0],provider='governed_factory_v1')
        p=draft_operator_policy(self.a,self.c.pk,'OPS.factory_issue_execution',value,self.e['policy_decision'].pk,timezone.now())
        transition(self.a,p.pk,'validated');transition(self.a,p.pk,'active')
        return p

    def test_real_mock_planner_lost_response_reconciles_original_without_resend(self):
        from tests.readiness_helpers import endpoint
        from apps.workflows.models import FactoryPlanningReceipt
        with endpoint() as state:
            self.configure_planner(state);state['lose_planning_response']=True
            self.assertFalse(factory.run_once(self.work.pk));self.work.refresh_from_db();spent=self.work.budget_used
            self.assertEqual(self.work.status,'waiting_effect',self.work.finding);self.assertEqual(state['planning_calls'],1)
            with self.assertRaises(ValidationError):domain.refresh(self.a,self.work.pk,self.work.revision,rev(self.c),'No blind source replacement')
            self.assertTrue(factory.run_once(self.work.pk));self.work.refresh_from_db()
            self.assertEqual(self.work.budget_used,spent);self.assertEqual(state['planning_calls'],1);self.assertEqual(FactoryPlanningReceipt.objects.count(),1)
            self.assertTrue(factory.run_once(self.work.pk));self.work.refresh_from_db();self.assertEqual(state['planning_calls'],1)
            self.assertFalse(HumanTask.objects.exists())
            for payload in state['planning_inputs']:
                self.assertEqual(payload['tools'],[]);self.assertNotIn('ISS-FACTORY',json.dumps(payload));self.assertNotIn(str(self.c.pk),json.dumps(payload))

    def test_stop_during_unknown_planning_waits_for_original_receipt(self):
        from tests.readiness_helpers import endpoint
        from apps.agents import factory_coordinator
        with endpoint() as state:
            self.configure_planner(state);state['lose_planning_response']=True
            factory.run_once(self.work.pk);self.work.refresh_from_db();spent=self.work.budget_used
            factory.manage(self.a,self.work.pk,self.work.revision,'cancel');self.work.refresh_from_db()
            self.assertEqual(self.work.status,'waiting_effect')
            with self.assertRaises(ValidationError):domain.refresh(self.a,self.work.pk,self.work.revision,rev(self.c),'No pending restart',restart=True)
            factory_coordinator.reconcile(self.a,self.work.pk,self.work.revision);self.work.refresh_from_db()
            self.assertEqual(self.work.status,'cancelled');self.assertEqual(self.work.budget_used,spent);self.assertEqual(state['planning_calls'],1)
            self.assertFalse(HumanTask.objects.exists())

    def test_direct_database_cannot_reverify_with_withdrawn_reference_scope(self):
        self.reference();self.advance();self.respond();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        Grant.objects.filter(case=self.c,user=self.a,action='issue.reference.incident.read').update(active=False)
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')

    def test_explicit_source_age_policy_reports_stale_without_inventing_sla(self):
        from datetime import timedelta
        from apps.pmo import issue_references as refs
        _,o,_,_=self.reference()
        result=refs.report(self.a,self.state.issue)
        self.assertEqual(result['references'][0]['freshness'],'unknown')
        self.assertEqual(refs.report(self.a,self.state.issue,31536000)['references'][0]['freshness'],'fresh')
        self.assertFalse(domain.report(self.work,self.a)['sla_evaluated'])
        with self.assertRaises(ValidationError):refs.report(self.a,self.state.issue,0)

    def test_exact_reference_identity_not_an_unrelated_record_from_same_export(self):
        from apps.pmo import issue_references as refs
        contract,o,revision,payload=self.reference();self.advance();self.respond();self.advance()
        self.assertEqual(self.work.status,'verified',self.work.finding)
        payload['source_ref']='A-DIFFERENT-INCIDENT';payload['observed_at']=timezone.now().isoformat()
        add_evidence(self.a,self.c.pk,'agent_private_issue_readback',json.dumps(payload),'synthetic:issue-source')
        self.assertEqual(refs.report(self.a,self.state.issue)['references'][0]['currentness'],'current')
        self.assertTrue(domain.verify(self.work,self.a)['verified'])
        with transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
        with self.assertRaises(ValidationError):refs.observation(self.a,self.c,True,self.state.issue)
        with self.assertRaises(ValidationError):refs.configure(self.a,self.c.pk,'incident','Invalid fields',[{}],'supplied',self.e['policy_decision'].pk,rev(self.c))
