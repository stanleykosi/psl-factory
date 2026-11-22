"""Native restricted payroll factory integration; requires accepted payroll schema."""
import json
from datetime import timedelta
from pathlib import Path
from django.test import TestCase
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,DatabaseError,connection
from django.urls import reverse
from django.utils import timezone
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.finance import payroll as native
from apps.finance.payroll_models import PayrollPublication,PayrollReportReceipt
from apps.finance.hrfinance_models import HRHandoffRecord
from apps.workflows import factory,factory_payroll as payroll
from apps.workflows.models import FactoryWork,FactoryAttempt
from tests.payroll_helpers import fixture,approve,capture
from tests.helpers import rev

class FactoryPayrollTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=fixture();f=cls.f
        value=json.loads(Path('fixtures/factory-payroll.json').read_text());value.pop('classification')
        p=draft_operator_policy(f['owner'],f['case'].pk,'OPS.factory_payroll_execution',value,f['e']['policy_decision'].pk,timezone.now())
        transition(f['owner'],p.pk,'validated');transition(f['owner'],p.pk,'active')
        Grant.objects.create(case=f['case'],user=f['manager'],action='factory.read')
    def rowsets(self):
        tables=[name for name in connection.introspection.table_names() if name.startswith(('core_','finance_','workflows_','agents_','policy_','pmo_','documents_','identity_'))]
        result={}
        with connection.cursor() as cursor:
            for name in tables:
                cursor.execute("SELECT count(*), md5(COALESCE(string_agg(row_to_json(t)::text, chr(10) ORDER BY row_to_json(t)::text),'')) FROM "+connection.ops.quote_name(name)+' t')
                result[name]=cursor.fetchone()
        return result
    def start(self,hr=True):
        f=self.f;self.inputs={'input_ids':[i.pk for i in f['inputs']],'hr_snapshot_id':f['hr'].pk if hr else None}
        self.work=payroll.start(f['preparer'],f['case'].pk,'PAYROLL-1',f['request'].pk,self.inputs,'September staff-cost work',rev(f['case']));return self.work
    def advance(self):factory.run_until_wait(self.work.pk);self.work.refresh_from_db();return self.work
    def pipeline(self):
        f=self.f;self.start();self.advance();self.assertEqual(payroll.report(self.work)['stage'],'input_review')
        for i in f['inputs']:approve(f,i)
        for stage in ['combine','match','aggregate']:
            self.advance();r=payroll.run(self.work,stage);self.assertIsNotNone(r,self.work.finding);approve(f,r)
        self.advance();self.assertEqual(payroll.report(self.work)['stage'],'publish');self.assertFalse(PayrollPublication.objects.exists())
        p=payroll.human_action(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),'publish',{})
        self.advance();self.assertNotEqual(self.work.status,'verified');return p
    def test_complete_native_path_requires_reviews_human_publication_and_actual_recipient_receipt(self):
        f=self.f;p=self.pipeline();self.assertFalse(PayrollReportReceipt.objects.exists())
        payroll.human_action(f['manager'],self.work.pk,self.work.revision,rev(f['case']),'receive',{'publication_id':p.pk})
        self.advance();self.assertEqual(self.work.status,'verified',self.work.finding);result=payroll.verify(self.work)
        self.assertEqual(result['publication'],p.pk);self.assertEqual(len(result['receipt_ids']),1);self.assertFalse(result['hr_written'])
        self.assertEqual(native.read_publication(f['manager'],p.pk)['by_bu'],{'BU-A':'250.00'});self.assertEqual(connection.vendor,'postgresql')
        text=json.dumps(list(FactoryAttempt.objects.filter(activity__work=self.work).values('observation','result')))
        for secret in ['E001','E002','employee_id','effective_from','BASIC']:self.assertNotIn(secret,text)
    def test_focused_reviews_bind_each_subject_and_publication_has_recipient_status(self):
        self.start();self.advance();f=self.f
        url=reverse('factory_invoice_decision',args=[self.work.pk])
        publication=reverse('factory_work_response',args=[self.work.pk])
        recovery=reverse('factory_invoice_recovery',args=[self.work.pk])
        self.client.force_login(f['reviewer'])
        page=self.client.get(url);self.assertContains(page,'Review payroll input',count=2)
        self.assertNotContains(page,'Exact subject ID')
        def approve_on_screen(kind,item):
            payload={'action':'review','kind':kind,'subject_id':item.pk,'evidence_id':f['e']['payroll_review'].pk,
                     'verdict':'approve','operation_key':f'http-{kind}-{item.pk}','revision':self.work.revision,
                     'case_revision':rev(f['case'])}
            self.assertContains(self.client.post(publication,payload),'Choose an available action on this page.')
            self.assertEqual(self.client.post(url,payload).status_code,302)
        for item in f['inputs']:approve_on_screen('input',item)
        for stage,title in [('combine','Review combined payroll'),('match','Review staff match'),('aggregate','Review payroll totals')]:
            self.advance();self.assertContains(self.client.get(url),title);approve_on_screen('run',payroll.run(self.work,stage))
        self.client.force_login(f['preparer']);self.assertContains(self.client.get(publication),'Publish exact reviewed aggregate')
        self.assertEqual(self.client.post(publication,{'action':'publish','revision':self.work.revision,
                         'case_revision':rev(f['case'])}).status_code,302)
        report=payroll.publication(self.work)
        self.assertContains(self.client.get(recovery),'Waiting for payroll receipts')
        self.client.force_login(f['manager']);page=self.client.get(recovery)
        self.assertContains(page,'Acknowledge receipt as myself');self.assertNotContains(page,'Inspect restricted payroll input')
        self.assertEqual(self.client.get(url).status_code,403)
        FactoryWork.objects.filter(pk=self.work.pk).update(revision=self.work.revision+1,lease_until=timezone.now()+timedelta(minutes=1))
        self.assertEqual(self.client.post(recovery,{'action':'receive','revision':self.work.revision,
                         'case_revision':rev(f['case']),'publication_id':report.pk}).status_code,302)
        FactoryWork.objects.filter(pk=self.work.pk).update(lease_until=None)
        self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
    def test_missing_hr_receipt_requires_exact_matcher_and_new_match(self):
        from unittest.mock import patch
        from tests import payroll_helpers

        from tests.helpers import setup_case
        owner,case=setup_case(username='missing-receipt-owner')
        from django.contrib.auth import get_user_model
        def principal(role):return get_user_model().objects.create_user(username='missing-receipt-'+role)
        with patch.object(payroll_helpers,'setup_case',return_value=(owner,case)):
            f=fixture(principal=principal,preparer_receipt=False)
        value=json.loads(Path('fixtures/factory-payroll.json').read_text());value.pop('classification')
        policy=draft_operator_policy(owner,case.pk,'OPS.factory_payroll_execution',value,f['e']['policy_decision'].pk,timezone.now())
        transition(owner,policy.pk,'validated');transition(owner,policy.pk,'active')
        self.f=f;self.start()
        for item in f['inputs']:approve(f,item)
        self.advance();approve(f,payroll.run(self.work,'combine'));self.advance()
        held=payroll.run(self.work,'match');self.assertIn('hr_receipt_missing',held.metadata['codes'])
        url=reverse('factory_invoice_recovery',args=[self.work.pk]);data={'action':'receive_hr','revision':self.work.revision,
                'case_revision':rev(case),'snapshot_id':f['hr'].pk,'evidence_id':f['e']['hr_disclosure_decision'].pk}
        self.client.force_login(f['reviewer']);self.assertNotContains(self.client.get(url),'Confirm HR snapshot receipt')
        self.assertContains(self.client.post(url,data),'The assigned matcher must confirm')
        self.client.force_login(f['preparer']);self.assertContains(self.client.get(url),'Confirm HR snapshot receipt')
        self.assertContains(self.client.post(url,{**data,'snapshot_id':999999}),'The assigned matcher must confirm')
        api = f'/api/v1/work/{self.work.pk}/payroll-operations'
        options = self.client.get(api)
        self.assertEqual(options.status_code, 200, options.content)
        self.assertTrue(options.json()['hr_receipt']['can_acknowledge'])
        command = {key: value for key, value in data.items() if key != 'revision'} | {'expected_revision': data['revision']}
        received = self.client.post(api, command, content_type='application/json')
        self.assertEqual(received.status_code, 200, received.content)
        self.assertEqual(self.client.get(api).json()['hr_receipt']['receipt_id'], received.json()['record_id'])
        self.assertTrue(HRHandoffRecord.objects.filter(snapshot=f['hr'],kind='receipt',actor=f['preparer']).exists())
        payroll.correct(f['preparer'],self.work.pk,self.work.revision,rev(case),f['request'].pk,self.inputs,'Confirmed the assigned matcher receipt')
        self.advance();approve(f,payroll.run(self.work,'combine'));self.advance()
        new=payroll.run(self.work,'match');self.assertNotEqual(new.pk,held.pk)
        self.assertEqual(new.metadata['status'],'complete');self.assertFalse(new.reviews.exists())
    def test_exact_sources_idempotency_and_database_verified_guard(self):
        f=self.f;self.start()
        self.assertEqual(payroll.start(f['preparer'],f['case'].pk,'OTHER',f['request'].pk,self.inputs,'Same native request').pk,self.work.pk)
        with self.assertRaises(ValidationError):payroll.start(f['preparer'],f['case'].pk,'PAYROLL-2',f['request'].pk,dict(self.inputs,input_ids=[f['inputs'][0].pk]*2),'Wrong two inputs')
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_private_source_access_is_not_conferred_by_factory_read(self):
        f=self.f;self.start();Grant.objects.filter(case=f['case'],user=f['preparer'],action='payroll.private.read').update(active=False)
        with self.assertRaises(PermissionDenied):payroll.source(self.work,f['preparer'])
        self.client.force_login(f['preparer']);self.assertIn(self.client.get(reverse('factory_detail',args=[self.work.pk])).status_code,[403,404])
    def test_minimal_hr_selection_required_without_guessed_matching(self):
        f=self.f;self.start(hr=False)
        for i in f['inputs']:approve(f,i)
        self.advance();approve(f,payroll.run(self.work,'combine'));self.advance()
        self.assertIsNone(payroll.run(self.work,'match'));self.assertIn('HR',self.work.finding)
    def test_source_owned_replacement_preserves_history_and_budget(self):
        f=self.f;self.start();self.advance();old=self.work.source_head_id;spent=self.work.budget_used
        new=capture(f,0,'replacement',source_version='A-v2')
        inputs=dict(self.inputs,input_ids=[new.pk,f['inputs'][1].pk])
        payroll.correct(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),f['request'].pk,inputs,'Source owner supplied corrected version')
        self.work.refresh_from_db();self.assertNotEqual(self.work.source_head_id,old);self.assertEqual(self.work.budget_used,spent);self.assertTrue(self.work.activities.exists())
        with self.assertRaises(ValidationError):payroll.correct(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),f['request'].pk,inputs,'Unchanged retry not a replacement')
    def test_recipient_console_is_aggregate_only_and_get_preserves_revision(self):
        f=self.f;p=self.pipeline();self.client.force_login(f['manager']);url=reverse('factory_detail',args=[self.work.pk]);before=self.work.revision
        response=self.client.get(url);self.assertContains(response,'Acknowledge receipt as myself');self.assertNotContains(response,'Inspect restricted payroll input')
        self.work.refresh_from_db();self.assertEqual(self.work.revision,before)
        self.assertEqual(self.client.post(url,{'action':'receive','revision':before,'case_revision':rev(f['case']),'publication_id':p.pk}).status_code,302)
        self.assertEqual(PayrollReportReceipt.objects.get(publication=p).actor_id,f['manager'].pk)
    def test_preparer_cannot_impersonate_recipient(self):
        f=self.f;p=self.pipeline()
        with self.assertRaises(PermissionDenied):payroll.human_action(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),'receive',{'publication_id':p.pk})
        self.assertFalse(PayrollReportReceipt.objects.exists())
    def test_current_review_revocation_invalidates_verification(self):
        f=self.f;p=self.pipeline();native.receive_report(f['manager'],f['case'].pk,p.pk,rev(f['case']));self.advance();self.assertEqual(self.work.status,'verified')
        approve(f,payroll.run(self.work,'aggregate'),'revoke-aggregate','revoke')
        with self.assertRaises(ValidationError):payroll.verify(self.work)
        self.assertEqual(PayrollReportReceipt.objects.filter(publication=p).count(),1)
    def test_cancel_after_publication_retains_native_effect_and_receipt_route(self):
        f=self.f;p=self.pipeline();payroll.cancel(f['preparer'],self.work.pk,self.work.revision);self.work.refresh_from_db()
        self.assertEqual(self.work.status,'followup_needed');self.assertTrue(PayrollPublication.objects.filter(pk=p.pk).exists())
        self.assertFalse(PayrollReportReceipt.objects.exists())
        payroll.human_action(f['manager'],self.work.pk,self.work.revision,rev(f['case']),'receive',{'publication_id':p.pk})
        self.work.refresh_from_db();self.assertEqual(self.work.status,'followup_needed')
        self.assertEqual(PayrollReportReceipt.objects.get(publication=p).actor_id,f['manager'].pk)
    def test_withdrawal_preserves_original_receipt_and_requires_new_reviewed_sources(self):
        f=self.f;p=self.pipeline();self.work.refresh_from_db()
        payroll.human_action(f['manager'],self.work.pk,self.work.revision,rev(f['case']),'receive',{'publication_id':p.pk})
        payroll.cancel(f['preparer'],self.work.pk,self.work.revision);self.work.refresh_from_db()
        url=reverse('factory_invoice_recovery',args=[self.work.pk])
        api = f'/api/v1/work/{self.work.pk}/payroll-operations'

        def command(action, **fields):
            self.work.refresh_from_db()
            return self.client.post(api, {'action': action, 'expected_revision': self.work.revision,
                'case_revision': rev(f['case']), **fields}, content_type='application/json')

        self.client.force_login(f['preparer'])
        self.assertNotContains(self.client.get(url),'Withdraw original report')
        with self.assertRaisesMessage(ValidationError,'An independent withdrawal'):
            payroll.prepare_successor(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),p.pk,
                                      f['request'].pk,self.inputs,'Attempt before exact withdrawal')
        self.client.force_login(f['reviewer']);self.assertContains(self.client.get(url),'Withdraw original report')
        withdrawn = command('withdraw', publication_id=p.pk, evidence_id=f['e']['payroll_review'].pk,
                            reason='A provider supplied a correction for this period.')
        self.assertEqual(withdrawn.status_code, 200, withdrawn.content)
        self.work.refresh_from_db();self.assertTrue(payroll.withdrawal(self.work,p.pk))
        self.client.force_login(f['manager']);page=self.client.get(url)
        self.assertContains(page,'Your published payroll report was withdrawn')
        self.assertNotContains(page,'Acknowledge receipt as myself');self.assertNotContains(page,'Amounts by business unit')
        with self.assertRaisesMessage(ValidationError,'This published payroll version was withdrawn'):
            approve(f,p.run,'replay-withdrawn-publication')
        with self.assertRaisesMessage(ValidationError,'Choose a corrected provider input'):
            payroll.prepare_successor(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),p.pk,
                                      f['request'].pk,self.inputs,'Attempt with original sources')
        replacement=capture(f,0,'publication-correction',source_version='A-v2')
        corrected=[replacement.pk,f['inputs'][1].pk]
        self.client.force_login(f['preparer']);self.assertContains(self.client.get(url),'Start corrected run')
        revised = command('successor', publication_id=p.pk, request_id=f['request'].pk,
                          inputs={'input_ids': corrected, 'hr_snapshot_id': f['hr'].pk},
                          reason='The provider supplied a corrected version.')
        self.assertEqual(revised.status_code, 200, revised.content)
        self.work.refresh_from_db();self.assertFalse(self.work.cancel_requested)
        self.assertIsNone(payroll.publication(self.work));self.assertTrue(PayrollReportReceipt.objects.filter(publication=p).exists())
        self.client.force_login(f['manager']);self.assertContains(self.client.get(url),'Your published payroll report was withdrawn')
        approve(f,replacement)
        for stage in ['combine','match','aggregate']:
            self.advance();approve(f,payroll.run(self.work,stage))
        self.advance()
        self.client.force_login(f['preparer'])
        published = command('publish')
        self.assertEqual(published.status_code, 200, published.content)
        new = PayrollPublication.objects.get(pk=published.json()['record_id'])
        self.assertGreater(new.version,p.version)
        payroll.human_action(f['manager'],self.work.pk,self.work.revision,rev(f['case']),'receive',{'publication_id':new.pk})
        self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        self.assertEqual(PayrollReportReceipt.objects.filter(publication__in=[p,new]).count(),2)
    def test_returned_work_rebuilds_without_erasing_prior_native_result(self):
        f=self.f;self.start()
        for i in f['inputs']:approve(f,i)
        self.advance();old=payroll.run(self.work,'combine');approve(f,old,'return-first-combine','return');spent=self.work.budget_used
        payroll.correct(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),f['request'].pk,self.inputs,'Reviewer returned the exact working result for controlled preparation')
        self.work.refresh_from_db();self.assertEqual(self.work.budget_used,spent);self.advance();new=payroll.run(self.work,'combine')
        self.assertNotEqual(new.pk,old.pk);self.assertTrue(old.reviews.filter(verdict='return').exists());self.assertFalse(PayrollPublication.objects.exists())
    def test_preparer_console_is_available_without_get_mutation(self):
        f=self.f;self.start();self.client.force_login(f['preparer']);before=self.work.revision
        response=self.client.get(reverse('factory_detail',args=[self.work.pk]));self.assertContains(response,'Continue permitted agent work');self.assertContains(response,'Exactly two accepted provider versions')
        self.work.refresh_from_db();self.assertEqual(self.work.revision,before)
    def test_foreign_native_review_subject_is_not_a_work_decision(self):
        f=self.f;self.start()
        with self.assertRaises(ValidationError):payroll.human_action(f['reviewer'],self.work.pk,self.work.revision,rev(f['case']),'review',{'kind':'input','subject_id':999999,'verdict':'approve','operation_key':'foreign-review','evidence_id':f['e']['payroll_review'].pk})

    def test_observation_and_get_preserve_all_native_rows_revisions_attempts_and_audit(self):
        f=self.f;p=self.pipeline();self.client.force_login(f['preparer']);before=self.rowsets()
        _,profile=factory.profile(self.work)
        state,*_=payroll.snapshot(self.work,profile,reader=f['preparer'])
        self.assertEqual(state['native']['stage'],'receipt')
        response=self.client.get(reverse('factory_detail',args=[self.work.pk]));self.assertEqual(response.status_code,200)
        self.assertEqual(self.rowsets(),before)
        self.client.force_login(f['manager']);before=self.rowsets()
        self.assertEqual(self.client.get(reverse('factory_detail',args=[self.work.pk])).status_code,200)
        self.assertEqual(self.rowsets(),before)

    def test_native_operation_identity_is_scoped_to_exact_selected_request(self):
        from tests.payroll_helpers import body
        f=self.f;self.start()
        other=native.request(f['preparer'],f['case'].pk,'other-staff-costs',f['config']['request'],f['e']['payroll_need'].pk,rev(f['case']))
        inputs=[native.capture(f['owner'],f['case'].pk,other.pk,f['config']['exports'][i]['provider'],'other-input-'+str(i),body(f,i),rev(f['case'])) for i in [0,1]]
        for i in inputs:approve(f,i)
        c=native.combine(f['preparer'],f['case'].pk,other.pk,[i.pk for i in inputs],payroll.key(self.work,'combine'),rev(f['case']));approve(f,c)
        m=native.match(f['preparer'],f['case'].pk,c.pk,f['hr'].pk,'other-match',rev(f['case']));approve(f,m)
        a=native.aggregate(f['preparer'],f['case'].pk,m.pk,'other-aggregate',rev(f['case']));approve(f,a)
        p=native.publish(f['preparer'],f['case'].pk,a.pk,payroll.key(self.work,'publish'),rev(f['case']))
        self.client.force_login(f['manager']);before=self.rowsets()
        self.assertIsNone(payroll.run(self.work,'combine'));self.assertIsNone(payroll.publication(self.work))
        response=self.client.get(reverse('factory_detail',args=[self.work.pk]));self.assertIn(response.status_code,[403,404]);self.assertNotContains(response,'BU-A',status_code=response.status_code)
        with self.assertRaises(ValidationError):payroll.human_action(f['manager'],self.work.pk,self.work.revision,rev(f['case']),'receive',{'publication_id':p.pk})
        self.assertEqual(self.rowsets(),before);self.assertFalse(PayrollReportReceipt.objects.exists())
    def test_uncertain_planning_blocks_replacement_and_recovers_original_receipt_after_cancel(self):
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
            coordinator.reconcile(a,self.work.pk,self.work.revision);self.work.refresh_from_db()
            self.assertEqual(self.work.status,'cancelled');self.assertEqual(self.work.budget_used,spent);self.assertEqual(state['planning_calls'],1)
            self.assertEqual(FactoryPlanningReceipt.objects.count(),1);self.assertFalse(PayrollRun.objects.exists());self.assertFalse(PayrollPublication.objects.exists());self.assertFalse(PayrollReportReceipt.objects.exists())
            for body in state['planning_inputs']:
                self.assertEqual(set(body),{'protocol','model_id','data_scope','eligible','citation_handles','tools','token_limit','max_output_chars'})
                for private in ['E001','E002','employee_id','BU-A',str(case.pk),a.username]:self.assertNotIn(private,json.dumps(body))

    def test_shared_schema_uses_exact_accepted_emergency_predecessor(self):
        from importlib import import_module
        migration=import_module('apps.workflows.migrations.0066_factory_payroll')
        previous=import_module('apps.workflows.migrations.0065_factory_emergency').SQL
        self.assertEqual(migration.PREVIOUS,previous)
        self.assertEqual(migration.Migration.dependencies,[('workflows','0065_factory_emergency')])
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM django_migrations WHERE app='workflows' AND name='0066_factory_payroll'")
            self.assertEqual(cursor.fetchone()[0],1)
