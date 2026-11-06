"""Separate post699 fresh-instruction proof; no new schema or external effects."""
import json
from pathlib import Path
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import PermissionDenied,ValidationError
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Audit
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory,factory_payroll as payroll
from apps.finance import payroll as native
from tests import test_factory_payroll as baseline
from tests.payroll_helpers import approve,capture
from tests.helpers import rev

class PayrollRestartTests(TestCase):
    setUpTestData=classmethod(baseline.FactoryPayrollTests.setUpTestData.__func__)
    start=baseline.FactoryPayrollTests.start
    advance=baseline.FactoryPayrollTests.advance
    rowsets=baseline.FactoryPayrollTests.rowsets
    def cancelled(self):
        self.start();self.advance();payroll.cancel(self.f['preparer'],self.work.pk,self.work.revision);self.work.refresh_from_db()
        self.assertEqual(self.work.status,'cancelled')
    def restart(self,**overrides):
        f=self.f
        args=dict(actor=f['preparer'],work_id=self.work.pk,expected=self.work.revision,case_expected=rev(f['case']),request_id=f['request'].pk,inputs=self.inputs,configuration_id=self.work.policy_id,instruction_key='fresh-instruction-1',reason='Explicit fresh preparation instruction')
        args.update(overrides);return payroll.restart(**args)
    def new_profile(self):
        f=self.f;value=json.loads(Path('fixtures/factory-payroll.json').read_text());value.pop('classification')
        p=draft_operator_policy(f['owner'],f['case'].pk,'OPS.factory_payroll_execution',value,f['e']['policy_decision'].pk,timezone.now())
        transition(f['owner'],p.pk,'validated');transition(f['owner'],p.pk,'active');return p
    def test_restart_retains_identity_allowance_and_idempotent_instruction(self):
        self.cancelled();old=self.work.source_head_id;budget=(self.work.budget_used,self.work.budget_limit);identity=(self.work.pk,self.work.business_key)
        original_revision=self.work.revision;case_revision=rev(self.f['case'])
        w=self.restart();self.assertEqual((w.pk,w.business_key),identity);self.assertNotEqual(w.source_head_id,old)
        self.assertEqual((w.budget_used,w.budget_limit),budget);self.assertEqual(w.status,'ready');self.assertFalse(w.cancel_requested)
        self.assertTrue(w.activities.exists());before=self.rowsets()
        self.assertEqual(self.restart(expected=original_revision,case_expected=case_revision).source_head_id,w.source_head_id)
        self.assertEqual(before,self.rowsets())
        with self.assertRaises(ValidationError):self.restart(reason='Changed intent reuses instruction')
        self.assertEqual(before,self.rowsets())
    def test_native_profile_adoption_preserves_lifetime_allowance(self):
        self.cancelled();budget=(self.work.budget_used,self.work.budget_limit);p=self.new_profile()
        w=self.restart(configuration_id=p.pk);self.assertEqual(w.policy_id,p.pk);self.assertEqual((w.budget_used,w.budget_limit),budget)
        self.assertTrue(Audit.objects.filter(case=self.f['case'],action='factory.profile_adopted').exists())
    def test_denied_native_adoption_rolls_back_entire_restart(self):
        self.cancelled();p=self.new_profile();Grant.objects.filter(case=self.f['case'],user=self.f['preparer'],action='policy.activate').update(active=False)
        before=self.rowsets();old=(self.work.source_head_id,self.work.revision,self.work.budget_used,self.work.budget_limit)
        with self.assertRaises(PermissionDenied):self.restart(configuration_id=p.pk)
        self.assertEqual(before,self.rowsets());self.work.refresh_from_db();self.assertEqual(self.work.status,'cancelled');self.assertTrue(self.work.cancel_requested)
        self.assertEqual(old,(self.work.source_head_id,self.work.revision,self.work.budget_used,self.work.budget_limit))
        self.assertFalse(Audit.objects.filter(action='factory.payroll_restarted').exists())
    def test_exact_revisions_private_access_profile_and_lease_required(self):
        self.cancelled()
        for overrides in [{'expected':0},{'case_expected':0},{'configuration_id':0},{'inputs':dict(self.inputs,input_ids=self.inputs['input_ids'][:1])}]:
            before=self.rowsets()
            with self.assertRaises(ValidationError):self.restart(**overrides)
            self.assertEqual(before,self.rowsets())
        self.work.lease_until=timezone.now()+timedelta(minutes=5);self.work.save();before=self.rowsets()
        with self.assertRaises(ValidationError):self.restart()
        self.assertEqual(before,self.rowsets());self.work.lease_until=None;self.work.save()
        Grant.objects.filter(case=self.f['case'],user=self.f['preparer'],action='payroll.private.read').update(active=False);before=self.rowsets()
        with self.assertRaises(PermissionDenied):self.restart()
        self.assertEqual(before,self.rowsets())
    def test_prior_source_publication_prevents_restart_and_requires_followup(self):
        f=self.f;self.start()
        for i in f['inputs']:approve(f,i)
        a=f['preparer'];r=native.combine(a,f['case'].pk,f['request'].pk,self.inputs['input_ids'],payroll.key(self.work,'combine'),rev(f['case']));approve(f,r)
        r=native.match(a,f['case'].pk,r.pk,f['hr'].pk,payroll.key(self.work,'match'),rev(f['case']));approve(f,r)
        r=native.aggregate(a,f['case'].pk,r.pk,payroll.key(self.work,'aggregate'),rev(f['case']));approve(f,r)
        p=native.publish(a,f['case'].pk,r.pk,payroll.key(self.work,'publish'),rev(f['case']))
        new=capture(f,0,'fresh-provider',source_version='A-v2');self.inputs=dict(self.inputs,input_ids=[new.pk,f['inputs'][1].pk])
        payroll.correct(a,self.work.pk,self.work.revision,rev(f['case']),f['request'].pk,self.inputs,'Source owner replacement after publication');self.work.refresh_from_db()
        self.assertIsNone(payroll.publication(self.work));self.assertTrue(payroll.publication_history(self.work).filter(pk=p.pk).exists())
        payroll.cancel(a,self.work.pk,self.work.revision);self.work.refresh_from_db();self.assertEqual(self.work.status,'followup_needed');before=self.rowsets()
        with self.assertRaises(ValidationError):self.restart()
        self.assertEqual(before,self.rowsets())
    def test_restart_console_get_is_read_only_and_post_is_explicit(self):
        self.cancelled();f=self.f;self.client.force_login(f['preparer']);url=reverse('factory_detail',args=[self.work.pk]);before=self.rowsets()
        response=self.client.get(url);self.assertContains(response,'Fresh preparation instruction');self.assertEqual(before,self.rowsets())
        response=self.client.post(url,{'action':'restart','revision':self.work.revision,'case_revision':rev(f['case']),'request_id':f['request'].pk,'input_ids':self.inputs['input_ids'],'hr_snapshot_id':f['hr'].pk,'configuration_id':self.work.policy_id,'instruction_key':'console-restart','reason':'Fresh console instruction'})
        self.assertEqual(response.status_code,302);self.work.refresh_from_db();self.assertEqual(self.work.status,'ready')

    def test_restart_by_other_manager_preserves_original_executor_and_revoked_grants(self):
        from apps.finance.payroll_models import PayrollRun
        from apps.workflows.models import FactoryExecutionBinding
        self.cancelled();f=self.f
        for i in f['inputs']:approve(f,i)
        Grant.objects.filter(case=f['case'],user=f['preparer'],action='factory.execute').update(active=False)
        grants=list(Grant.objects.order_by('pk').values());bindings=FactoryExecutionBinding.objects.count()
        old=(self.work.actor_id,self.work.execution_binding_id,self.work.budget_used,self.work.budget_limit)
        w=self.restart(actor=f['reviewer'])
        self.assertEqual((w.actor_id,w.execution_binding_id,w.budget_used,w.budget_limit),old)
        self.assertEqual(w.execution_actor_id,f['preparer'].pk)
        self.assertFalse(factory.run_once(w.pk));w.refresh_from_db();self.assertEqual(w.status,'blocked')
        self.assertFalse(PayrollRun.objects.exists());self.assertEqual(FactoryExecutionBinding.objects.count(),bindings)
        self.assertEqual(list(Grant.objects.order_by('pk').values()),grants)
        self.assertEqual((w.budget_used,w.budget_limit),old[2:])

    def test_restart_refuses_actual_unresolved_planner_and_preserves_original_recovery(self):
        from tests.readiness_helpers import endpoint
        from apps.core.services import add_evidence
        from apps.policy.readiness_drafts import draft_readiness_policy
        from apps.policy.readiness_validators import PROVIDER
        from apps.policy.factory_coordinator_validators import PROTOCOL,SCOPE
        from apps.workflows import readiness,readiness_delivery
        from apps.workflows.models import FactoryPlanningReceipt
        from apps.agents import factory_coordinator as coordinator
        from apps.finance.payroll_models import PayrollRun
        f=self.f;a=f['preparer'];case=f['case'];proof=lambda kind:add_evidence(a,case.pk,kind,'Synthetic opaque payroll planner evidence only','synthetic:payroll-planner')
        with endpoint() as state:
            state['contract_version']=PROTOCOL
            rules=json.loads(Path('fixtures/integration-readiness.json').read_text())['rules']
            rules.update(probe_user_id=a.pk,reviewer_id=a.pk,probe_role='Finance',reviewer_role='Finance',independent_review=False)
            p=draft_readiness_policy(a,case.pk,PROVIDER,rules,f['e']['policy_decision'].pk,timezone.now())
            transition(a,p.pk,'validated');transition(a,p.pk,'active')
            contract=readiness.capture(a,case.pk,'payroll-planner',{'kind':'provider','family':'provider','implementation':'authenticated_json_v1','target_key':'endpoint:fixture','credential_ref':'secret:fixture','credential_revision':'fixture-v1','principal_ref':'principal:fixture','contract_version':PROTOCOL,'model_id':'fixture-model','capabilities':['health','receipt_lookup','evaluation'],'data_scope':'public_canary_and_scoped_receipt_metadata_only'},proof('integration_contract').pk)
            for kind in ['health','evaluation']:
                job=readiness_delivery.reserve(a,case.pk,contract.pk,'payroll-planner-'+kind,kind);readiness_delivery.run_once(case_id=case.pk);job.refresh_from_db();self.assertEqual(job.status,'confirmed')
            assessment=readiness.assess(a,case.pk,contract.pk,'payroll-planner-ready');self.assertTrue(assessment.result['capability_ready'])
            readiness.review(a,case.pk,assessment.pk,'confirm','payroll-planner-ready',proof('integration_review').pk);readiness.select(a,case.pk,contract.pk,proof('integration_selection').pk)
            p=draft_operator_policy(a,case.pk,'OPS.factory_coordinator',{'mode':'authenticated_planner_v1','contract_id':contract.pk,'planner_id':a.pk,'data_scope':SCOPE,'max_output_chars':2048},f['e']['policy_decision'].pk,timezone.now())
            transition(a,p.pk,'validated');transition(a,p.pk,'active')
            profile=json.loads(Path('fixtures/factory-payroll.json').read_text());profile.pop('classification');profile['provider']='governed_factory_v1'
            p=draft_operator_policy(a,case.pk,'OPS.factory_payroll_execution',profile,f['e']['policy_decision'].pk,timezone.now());transition(a,p.pk,'validated');transition(a,p.pk,'active')
            self.start();state['lose_planning_response']=True
            self.assertFalse(factory.run_once(self.work.pk));self.work.refresh_from_db();self.assertEqual(self.work.status,'waiting_effect',self.work.finding)
            spent=self.work.budget_used;self.assertEqual(state['planning_calls'],1)
            new=capture(f,0,'uncertain-source-replacement',source_version='A-v2')
            with self.assertRaises(ValidationError):payroll.correct(a,self.work.pk,self.work.revision,rev(case),f['request'].pk,dict(self.inputs,input_ids=[new.pk,f['inputs'][1].pk]),'Source owner supplied a new native version')
            payroll.cancel(a,self.work.pk,self.work.revision);self.work.refresh_from_db();self.assertEqual(self.work.status,'waiting_effect')
            before=self.rowsets()
            with self.assertRaises(ValidationError):self.restart()
            self.assertEqual(before,self.rowsets());self.assertEqual(state['planning_calls'],1)
            # A stale/corrupted status must not bypass the independent pending receipt guard.
            self.work.status='cancelled';self.work.save();before=self.rowsets()
            with self.assertRaisesMessage(ValidationError,'Reconcile the original planning response'):self.restart()
            self.assertEqual(before,self.rowsets());self.assertEqual(state['planning_calls'],1)
            coordinator.reconcile(a,self.work.pk,self.work.revision);self.work.refresh_from_db()
            self.assertEqual(self.work.status,'cancelled');self.assertEqual(self.work.budget_used,spent);self.assertEqual(state['planning_calls'],1)
            self.assertEqual(FactoryPlanningReceipt.objects.count(),1);self.assertFalse(PayrollRun.objects.exists());self.assertFalse(PayrollPublication.objects.exists());self.assertFalse(PayrollReportReceipt.objects.exists())
            for body in state['planning_inputs']:
                self.assertEqual(set(body),{'protocol','model_id','data_scope','eligible','citation_handles','tools','token_limit','max_output_chars'})
                for private in ['E001','E002','employee_id','BU-A',str(case.pk),a.username]:self.assertNotIn(private,json.dumps(body))

