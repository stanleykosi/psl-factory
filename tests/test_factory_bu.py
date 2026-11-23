"""Connected BU scope, actual native reviews and aggregate-only receipts."""
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import connection,transaction,DatabaseError
from django.urls import reverse
from django.utils import timezone
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.policy.bu_validators import DISCLOSE,SOURCE
from apps.workflows import factory,factory_bu as bu
from apps.workflows.models import FactoryWork,FactoryAttempt,FactoryProgress
from apps.finance.bu_models import BUReport,BUReceipt,BUWork
from tests.bu_helpers import fixture,rule,review,source,policy
from tests.helpers import check_investigation_progress, rev

class FactoryBUTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        f=fixture();cls.f=f
        value=json.loads(Path('fixtures/factory-bu.json').read_text());value.pop('classification')
        p=draft_operator_policy(f['preparer'],f['case'].pk,'OPS.factory_bu_execution',value,f['e']['policy_decision'].pk,timezone.now());transition(f['preparer'],p.pk,'validated');transition(f['preparer'],p.pk,'active');cls.profile=p
        Grant.objects.get_or_create(case=f['case'],user=f['manager'],action='factory.read')
    def start(self,mode='staff',approved=True):
        f=self.f
        if mode=='staff':
            self.rule=rule(f)
            if approved:review(f,self.rule)
            self.inputs={'mode':'staff','payroll_id':f['match'].pk,'source_id':None,'rule_ids':[self.rule.pk],'comparison':None}
        else:
            self.source=source(f)
            if approved:review(f,self.source)
            self.inputs={'mode':'event','payroll_id':None,'source_id':self.source.pk,'rule_ids':[],'comparison':None}
        self.work=bu.start(f['preparer'],f['case'].pk,'BU-1',self.inputs,'September reviewed aggregate',rev(f['case']));return self.work
    def advance(self):factory.run_until_wait(self.work.pk);self.work.refresh_from_db();return self.work
    def pipeline(self,mode='staff'):
        f=self.f;self.start(mode);self.advance();r=bu.result(self.work);self.assertIsNotNone(r,self.work.finding)
        self.assertEqual(bu.report(self.work)['stage'],'result_review');self.assertFalse(BUReport.objects.exists());review(f,r);self.advance()
        p=bu.human_action(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),'publish',{});self.advance();self.assertNotEqual(self.work.status,'verified');return p
    def finish(self,p):
        f=self.f;bu.human_action(f['manager'],self.work.pk,self.work.revision,rev(f['case']),'receive',{'publication_id':p.pk});self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
    def rowsets(self):
        result={}
        with connection.cursor() as cur:
            for table in connection.introspection.table_names():
                if table.startswith(('core_','finance_','workflows_','agents_','policy_','pmo_','documents_','identity_')):
                    cur.execute("SELECT count(*),md5(coalesce(string_agg(row_to_json(t)::text,chr(10) ORDER BY row_to_json(t)::text),'')) FROM "+connection.ops.quote_name(table)+' t');result[table]=cur.fetchone()
        return result
    def test_event_full_chain_selected_population_no_ledger_or_source_writes(self):
        p=self.pipeline('event');self.finish(p);value=bu.native.read_report(self.f['manager'],p.pk)
        self.assertTrue(value['conserved']);self.assertFalse(value['source_written']);self.assertEqual(value['coverage'],'selected_supplied_population_only');self.assertEqual(Decimal(value['company_source_total']),Decimal(value['allocated_total']))

    def test_api_private_event_through_reviewed_aggregate_and_original_recipient(self):
        from tests.bu_helpers import body

        f = self.f
        self.client.force_login(f['preparer'])
        case = f['case']
        intake = f'/api/v1/projects/{case.pk}/business-unit-intake'
        value = json.loads(body(f))
        scope = {key: value[key] for key in ('entity', 'period', 'currency')}
        created = self.client.post(intake, {'case_revision': rev(case), 'reference': 'BU-event-api',
            'operation_key': 'BU-test-1', 'scope': scope, 'export': value}, content_type='application/json')
        self.assertEqual(created.status_code, 201, created.content)
        self.assertTrue(created.json()['accepted'])
        row = BUWork.objects.get(pk=created.json()['id'])
        choices = self.client.get(intake)
        self.assertEqual(choices.status_code, 200, choices.content)
        self.assertIn(row.pk, [entry['id'] for entry in choices.json()['events']])
        inputs = {'mode': 'event', 'payroll_id': None, 'source_id': row.pk, 'rule_ids': [], 'comparison': None}
        self.work = bu.start(f['preparer'], case.pk, 'BU-event-api-work', inputs, 'BU event source', rev(case))
        self.advance()
        url = f'/api/v1/work/{self.work.pk}/business-units'
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200, page.content)
        self.assertEqual(page.json()['stage'], 'source_review')
        review(f, row)
        self.advance()
        prepared = bu.result(self.work)
        self.assertIsNotNone(prepared)
        review(f, prepared)
        self.advance()
        page = self.client.get(url).json()
        self.assertTrue(page['can_publish'])
        published = self.client.post(url, {'action': 'publish', 'expected_revision': page['expected_revision'],
            'case_revision': page['case_revision']}, content_type='application/json')
        self.assertEqual(published.status_code, 201, published.content)
        report_id = published.json()['record_id']
        self.client.force_login(f['manager'])
        receipt = self.client.get(url)
        self.assertEqual(receipt.status_code, 200, receipt.content)
        self.assertTrue(receipt.json()['recipient_only'])
        self.assertIsNone(receipt.json()['inputs'])
        self.assertIsNone(receipt.json()['result'])
        saved = self.client.post(f'/api/v1/work/{self.work.pk}/aggregate-receipt', {'publication_id': report_id},
                                 content_type='application/json')
        self.assertEqual(saved.status_code, 200, saved.content)
        self.advance()
        self.assertEqual(self.work.status, 'verified')
        self.assertEqual(self.client.get(url).json()['receipt_id'], saved.json()['receipt_id'])
    def test_unreviewed_rule_wait_and_no_automatic_approval(self):
        self.start(approved=False);self.advance();self.assertEqual(bu.report(self.work)['stage'],'source_review');self.assertIsNone(bu.result(self.work));self.assertFalse(self.rule.reviews.exists())
        review(self.f,self.rule);self.advance();self.assertIsNotNone(bu.result(self.work))
    def test_unreviewed_event_source_wait(self):
        self.start('event',False);self.advance();self.assertIsNone(bu.result(self.work));self.assertEqual(bu.report(self.work)['stage'],'source_review')
    def test_focused_staff_reviews_publication_and_private_recipient_receipt(self):
        self.start(approved=False);self.advance();f=self.f
        decision=reverse('factory_invoice_decision',args=[self.work.pk])
        publication=reverse('factory_work_response',args=[self.work.pk])
        recovery=reverse('factory_invoice_recovery',args=[self.work.pk])
        self.client.force_login(f['reviewer']);self.assertContains(self.client.get(decision),'Review exception rule')
        self.assertNotContains(self.client.get(decision),'Publish exact aggregate')
        command={'action':'review','revision':self.work.revision,'case_revision':rev(f['case']),
                 'work_id':self.rule.pk,'purpose':'rule','verdict':'approve','operation_key':'http-staff-rule',
                 'evidence_id':f['e']['bu_review'].pk}
        self.assertContains(self.client.post(publication,command),'Choose an available action on this page.')
        self.assertFalse(self.rule.reviews.exists())
        self.assertEqual(self.client.post(decision,command).status_code,302)
        self.advance();result=bu.result(self.work)
        self.assertContains(self.client.get(decision),'Review business-unit totals')
        self.assertEqual(self.client.post(decision,{**command,'revision':self.work.revision,'case_revision':rev(f['case']),
                         'work_id':result.pk,'purpose':result.kind,'operation_key':'http-staff-result'}).status_code,302)
        self.client.force_login(f['preparer'])
        self.assertContains(self.client.get(publication),'Publish exact aggregate')
        self.assertEqual(self.client.post(publication,{'action':'publish','revision':self.work.revision,
                         'case_revision':rev(f['case'])}).status_code,302)
        report=bu.publication(self.work)
        self.assertContains(self.client.get(recovery),'Waiting for recipient receipts')
        self.client.force_login(f['manager'])
        page=self.client.get(recovery);self.assertContains(page,'Acknowledge receipt as myself')
        self.assertNotContains(page,'Inspect restricted subject')
        self.assertEqual(self.client.get(decision).status_code,403)
        FactoryWork.objects.filter(pk=self.work.pk).update(revision=self.work.revision+1,lease_until=timezone.now()+timedelta(minutes=1))
        queued=FactoryProgress.objects.create(work=self.work,requested_by=f['preparer'],status='waiting',
                                             available_at=timezone.now()+timedelta(minutes=2),observation='awaiting-receipt')
        self.assertEqual(self.client.post(recovery,{'action':'receive','revision':self.work.revision,
                         'case_revision':rev(f['case']),'publication_id':report.pk}).status_code,302)
        self.assertEqual(BUReceipt.objects.get(report=report).actor,f['manager'])
        previous_due=queued.available_at;queued.refresh_from_db()
        self.assertLess(queued.available_at,previous_due);self.assertEqual(queued.observation,'')
        FactoryWork.objects.filter(pk=self.work.pk).update(lease_until=None)
        self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
    def test_small_group_hold_hides_publication_while_review_survives(self):
        f=self.f;policy(f,DISCLOSE,dict(f['bu_config']['disclosure'],minimum_staff=10))
        self.start();self.advance();review(f,bu.result(self.work));self.advance()
        self.client.force_login(f['preparer'])
        url=reverse('factory_work_response',args=[self.work.pk]);page=self.client.get(url)
        self.assertContains(page,'Small-group protection holds the whole report')
        self.assertNotContains(page,'Publish exact aggregate')
        self.assertFalse(BUReport.objects.exists())
        projection = self.client.get(f'/api/v1/work/{self.work.pk}/business-units')
        self.assertEqual(projection.status_code, 200, projection.content)
        api = projection.json()
        self.assertFalse(api['can_publish'])
        self.assertEqual(api['result']['id'], bu.result(self.work).pk)
    def test_known_exception_omitted_holds_not_zero_or_previous_ratio(self):
        self.start();self.inputs['rule_ids']=[]
        bu.correct(self.f['preparer'],self.work.pk,self.work.revision,rev(self.f['case']),self.inputs,'Explicit changed exclusion selection');self.work.refresh_from_db();self.advance()
        r=bu.result(self.work);self.assertIn('known_exception_omitted',r.metadata['codes'])
        with self.assertRaises(ValidationError):review(self.f,r)
    def test_required_comparison_absent_is_native_hold(self):
        f=self.f;v=deepcopy(f['bu_config']['source']);v['company_comparison']='finance_allocation_required';policy(f,SOURCE,v)
        self.start('event');self.advance();r=bu.result(self.work);self.assertIn('finance_company_comparison_missing',r.metadata['codes'])
        with self.assertRaises(ValidationError):review(f,r)
    def test_event_conflicting_tags_remain_held(self):
        f=self.f;s=source(f,rows=[{'event_id':'E1','amount':'100','tags':['DIRECT-A','DIRECT-B']}],control_total='100');review(f,s)
        inputs={'mode':'event','payroll_id':None,'source_id':s.pk,'rule_ids':[],'comparison':None};self.work=bu.start(f['preparer'],f['case'].pk,'CONFLICT',inputs,'Conflicting tags',rev(f['case']));self.advance();r=bu.result(self.work);self.assertEqual(r.metadata['status'],'held')
    def test_exact_intake_retry_and_database_verified_forgery_denied(self):
        self.start();self.assertEqual(bu.start(self.f['preparer'],self.f['case'].pk,'OTHER',self.inputs,'Same scope').pk,self.work.pk)
        with self.assertRaises(ValidationError):bu.start(self.f['preparer'],self.f['case'].pk,'BU-1',self.inputs,'Changed description')
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')

    def test_drawer_requires_current_sources_and_refreshes_its_choices(self):
        from apps.workflows.factory_bu_views import InputsForm

        f = self.f
        sample_event = source(f)
        self.client.force_login(f['preparer'])
        url = reverse('factory_create') + '?definition=' + bu.DEFINITION + '&case=' + str(f['case'].pk)
        available = self.client.get(url)
        self.assertContains(available, f'Payroll match {f["match"].pk}')
        self.assertContains(available, f'Accepted event source {sample_event.pk}')
        later = timezone.now() + timedelta(days=90)
        with patch('apps.finance.payroll.timezone.now', return_value=later):
            # Simulate source age at the form boundary without expiring the test login session.
            unavailable = InputsForm(f['case'], f['preparer'], starting=True)
        self.assertFalse(unavailable.has_current_sources)
        self.assertFalse(unavailable.fields['payroll_id'].queryset.exists())
        self.assertFalse(unavailable.fields['source_id'].queryset.exists())
        self.assertFalse(FactoryWork.objects.exists())
    def test_cross_case_and_wrong_native_kind_inputs_denied(self):
        self.start();bad=dict(self.inputs,payroll_id=999999)
        with self.assertRaises(ValidationError):bu.inputs_checked(self.f['preparer'],self.f['case'],bad)
        bad=dict(self.inputs,rule_ids=[source(self.f,key='wrong-kind').pk])
        with self.assertRaises(ValidationError):bu.inputs_checked(self.f['preparer'],self.f['case'],bad)
    def test_factory_read_does_not_grant_source_access(self):
        self.start();f=self.f
        with self.assertRaises(PermissionDenied):bu.source(self.work,f['manager'])
        self.client.force_login(f['manager']);self.assertIn(self.client.get(reverse('factory_detail',args=[self.work.pk])).status_code,[403,404])
    def test_revoked_private_reader_denies_detail_and_execution(self):
        self.start();f=self.f;Grant.objects.filter(case=f['case'],user=f['preparer'],action='bu.private.read').update(active=False)
        with self.assertRaises(PermissionDenied):bu.source(self.work,f['preparer'])
        self.client.force_login(f['preparer']);self.assertIn(self.client.get(reverse('factory_detail',args=[self.work.pk])).status_code,[403,404]);self.advance();self.assertNotEqual(self.work.status,'verified')
    def test_cancel_restart_preserves_identity_spend_and_historical_activity(self):
        self.start(approved=False);self.advance();f=self.f;spent=self.work.budget_used;head=self.work.source_head_id;pk=self.work.pk
        bu.cancel(f['preparer'],pk,self.work.revision);self.work.refresh_from_db();self.assertEqual(self.work.status,'cancelled')
        args=(f['preparer'],pk,self.work.revision,rev(f['case']),self.inputs,self.profile.pk,'fresh-bu','Fresh instruction')
        bu.restart(*args);self.work.refresh_from_db();self.assertEqual(self.work.pk,pk);self.assertEqual(self.work.budget_used,spent);self.assertNotEqual(self.work.source_head_id,head);self.assertTrue(self.work.activities.exists());bu.restart(*args)
    def test_returned_result_can_rebuild_reviewed_successor_preserving_old_result(self):
        f = self.f
        self.start()
        check_investigation_progress(self, f['preparer'], self.work,
                                     'Investigating the selected business-unit sources and exception rules.')
        self.advance()
        old = bu.result(self.work)
        self.client.force_login(f['reviewer'])
        url = f'/api/v1/work/{self.work.pk}'
        opened = self.client.get(url + '/business-units')
        self.assertEqual(opened.status_code, 200, opened.content)
        plan = opened.json()
        body = {'kind': 'business_unit', 'work_id': old.pk, 'purpose': old.kind, 'verdict': 'return',
                'operation_key': 'api-bu-return', 'evidence_id': f['e']['bu_review'].pk,
                **{key: plan[key] for key in ('expected_revision', 'case_revision')}}
        decision = self.client.post(url + '/reviews', body, content_type='application/json')
        self.assertEqual(decision.status_code, 200, decision.content)
        returned = old.reviews.get(verdict='return')
        spent = self.work.budget_used
        original_due = timezone.now() + timedelta(minutes=2)
        progress = FactoryProgress.objects.create(work=self.work, requested_by=f['preparer'], status='waiting',
                                                  available_at=original_due, observation='awaiting-result')
        bu.correct(f['preparer'], self.work.pk, self.work.revision, rev(f['case']), self.inputs, 'Source-owned rework')
        self.work.refresh_from_db()
        progress.refresh_from_db()
        self.assertEqual(self.work.budget_used, spent)
        self.assertEqual(progress.requested_by_id, f['preparer'].pk)
        self.assertEqual(progress.status, 'waiting')
        self.assertLess(progress.available_at, original_due)
        self.assertEqual(progress.observation, '')
        self.advance()
        replacement = bu.result(self.work)
        self.assertNotEqual(replacement.pk, old.pk)
        self.assertFalse(replacement.reviews.exists())
        self.assertTrue(old.reviews.filter(pk=returned.pk, verdict='return').exists())
        current = self.client.get(url + '/business-units').json()
        self.assertEqual(current['result']['id'], replacement.pk)
        approved = self.client.post(url + '/reviews', {**body, 'work_id': replacement.pk, 'verdict': 'approve',
            'operation_key': 'api-bu-successor', **{key: current[key] for key in ('expected_revision', 'case_revision')}},
            content_type='application/json')
        self.assertEqual(approved.status_code, 200, approved.content)
    def test_primary_intake_form_is_typed_and_rejects_extra_fields(self):
        f=self.f;self.client.force_login(f['preparer']);url=reverse('factory_create')+'?definition='+bu.DEFINITION+'&case='+str(f['case'].pk)
        response=self.client.get(url);self.assertEqual(response.status_code,200);self.assertContains(response,'Exceptions to exclude');self.assertNotContains(response,'JSON')
    def test_typed_rule_preparation_requires_explicit_weights_and_actual_review(self):
        self.start();f=self.f
        from apps.workflows.factory_bu_views import RuleForm
        blank={'reference':'second-rule','operation_key':'typed-rule','subject':'0','rationale_evidence_id':f['e']['bu_review'].pk}
        form=RuleForm(self.work,f['preparer'],blank);self.assertFalse(form.is_valid())
        data=dict(blank,weight_0='70',weight_1='30');form=RuleForm(self.work,f['preparer'],data);self.assertTrue(form.is_valid(),form.errors)
        r=bu.human_action(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),'prepare_rule',form.values());self.assertFalse(r.reviews.exists());self.assertEqual(r.payroll_id,f['match'].pk)
        self.assertEqual(r.payload['weights'],[{'bu':'BU-A','weight':'70'},{'bu':'BU-B','weight':'30'}])
    def test_recipient_revocation_keeps_original_receipt_but_denies_current_verification(self):
        p=self.pipeline('event');self.finish(p);f=self.f;Grant.objects.filter(case=f['case'],user=f['manager'],action='bu.report.read').update(active=False)
        with self.assertRaises(PermissionDenied):bu.verify(self.work)
        self.assertEqual(BUReceipt.objects.filter(report=p).count(),1)
    def test_source_owner_revocation_stops_event_execution(self):
        self.start('event');f=self.f;Grant.objects.filter(case=f['case'],user=f['preparer'],action='bu.capture').update(active=False)
        with self.assertRaises(PermissionDenied):bu.source(self.work)
        self.advance();self.assertIsNone(bu.result(self.work))
    def test_source_replacement_cannot_change_canonical_period_or_mode(self):
        self.start();f=self.f;s=source(f);review(f,s);other={'mode':'event','payroll_id':None,'source_id':s.pk,'rule_ids':[],'comparison':None}
        with self.assertRaises(ValidationError):bu.correct(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),other,'Different business identity')
    def test_cross_case_existing_native_source_is_not_a_valid_intake(self):
        from tests.helpers import setup_case
        f=self.f;s=source(f);a,c=setup_case(username='other-bu-case')
        inputs={'mode':'event','payroll_id':None,'source_id':s.pk,'rule_ids':[],'comparison':None}
        with self.assertRaises(ValidationError):bu.start(a,c.pk,'foreign',inputs,'Foreign source',rev(c))
    def test_no_unchanged_source_replay_and_no_budget_reset(self):
        self.start();f=self.f;head=self.work.source_head_id
        with self.assertRaises(ValidationError):bu.correct(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),self.inputs,'Unchanged')
        self.work.refresh_from_db();self.assertEqual(self.work.source_head_id,head)

    def observe(self):
        self.work.refresh_from_db();self.work.case.refresh_from_db()
        value=factory.profile(self.work)[1]
        return value,bu.snapshot(self.work,value)
    def execute_observed(self,observed):
        value,state=observed
        self.work.refresh_from_db();self.work.case.refresh_from_db()
        return bu.act(self.work,{'activity':'ACT08','citations':[self.work.source_head_id]},value,state[1],state[2],state[4],state[5])
    def test_execution_reader_revoked_after_observation_cannot_calculate(self):
        self.start();observed=self.observe();f=self.f
        Grant.objects.filter(case=f['case'],user=f['preparer'],action='bu.private.read').update(active=False)
        with self.assertRaises(PermissionDenied):self.execute_observed(observed)
        self.assertIsNone(bu.result(self.work))
    def test_source_reviewer_revoked_after_observation_cannot_calculate(self):
        self.start('event');observed=self.observe();f=self.f
        Grant.objects.filter(case=f['case'],user=f['reviewer'],action='bu.review').update(active=False)
        with self.assertRaises((PermissionDenied,ValidationError)):self.execute_observed(observed)
        self.assertIsNone(bu.result(self.work))
    def test_exact_rule_revoked_after_observation_cannot_calculate(self):
        self.start();observed=self.observe();review(self.f,self.rule,'revoke')
        with self.assertRaises(ValidationError):self.execute_observed(observed)
        self.assertIsNone(bu.result(self.work))
    def test_staff_policy_revoked_after_observation_cannot_calculate(self):
        from apps.policy.bu_validators import STAFF
        self.start();observed=self.observe();f=self.f;transition(f['preparer'],f['bu_policies'][STAFF].pk,'revoked')
        with self.assertRaises(ValidationError):self.execute_observed(observed)
        self.assertIsNone(bu.result(self.work))
    def test_different_native_source_owner_revoked_after_observation(self):
        f=self.f;s=source(f);review(f,s);self.inputs={'mode':'event','source_id':s.pk,'payroll_id':None,'rule_ids':[],'comparison':None}
        self.work=bu.start(f['reviewer'],f['case'].pk,'DIFFERENT-SOURCE-OWNER',self.inputs,'Explicitly different source and intake owners',rev(f['case']));observed=self.observe()
        self.assertNotEqual(self.work.actor_id,s.actor_id)
        Grant.objects.filter(case=f['case'],user=f['preparer'],action='bu.capture').update(active=False)
        with self.assertRaises(PermissionDenied):self.execute_observed(observed)
        self.assertIsNone(bu.result(self.work))
    def test_different_intake_owner_revoked_after_observation(self):
        self.start('event');f=self.f;s=source(f,key='replacement',source_version='events-v2');review(f,s);self.inputs=dict(self.inputs,source_id=s.pk)
        bu.correct(f['reviewer'],self.work.pk,self.work.revision,rev(f['case']),self.inputs,'Native source-owned version replacement');self.work.refresh_from_db();observed=self.observe()
        self.assertNotEqual(self.work.actor_id,self.work.source_head.created_by_id)
        Grant.objects.filter(case=f['case'],user=f['reviewer'],action='factory.manage').update(active=False)
        with self.assertRaises(PermissionDenied):self.execute_observed(observed)
        self.assertIsNone(bu.result(self.work))
    def test_investigation_does_not_scan_other_native_bu_work(self):
        f=self.f;unrelated=source(f,key='unrelated',reference='unrelated',rows=[{'event_id':'E2','amount':'100','tags':['DIRECT-A']}]);self.start();self.advance()
        findings=[item for result in FactoryAttempt.objects.filter(activity__work=self.work,phase='observed').values_list('result',flat=True) for item in result.get('findings',[])]
        self.assertTrue(findings);self.assertNotIn(unrelated.pk,{item['work_id'] for item in findings})


class FactoryBUPublishedTests(TestCase):
    """One real native prefix, transaction-isolated independent publication negatives."""
    start=FactoryBUTests.start
    advance=FactoryBUTests.advance
    finish=FactoryBUTests.finish
    rowsets=FactoryBUTests.rowsets
    @classmethod
    def setUpTestData(cls):
        FactoryBUTests.setUpTestData.__func__(cls)
        setup=FactoryBUTests(methodName='runTest');setup.f=cls.f;setup.profile=cls.profile
        cls.saved_publication=setup.pipeline();cls.saved_work=setup.work;cls.saved_inputs=setup.inputs;cls.saved_rule=setup.rule
    def setUp(self):
        self.work=self.saved_work;self.inputs=self.saved_inputs;self.rule=self.saved_rule
    def pipeline(self,mode='staff'):
        self.assertEqual(mode,'staff');return self.saved_publication
    def test_staff_full_chain_exact_exception_and_exclusion_then_aggregate_receipt(self):
        p=self.pipeline();self.finish(p);value=bu.native.read_report(self.f['manager'],p.pk)
        self.assertEqual(value['by_bu'],{'BU-A':'220.00','BU-B':'30.00'});self.assertEqual(Decimal(value['company_source_total']),Decimal('250.00'));self.assertEqual(value['disclosure'],'aggregate_only');self.assertFalse(value['ledger_posted'])
        text=json.dumps(list(FactoryAttempt.objects.filter(activity__work=self.work).values('observation','result')))
        for secret in ['E900','E002','employee_id','BASIC','weights']:self.assertNotIn(secret,text)
        self.assertEqual(bu.verify(self.work)['publication'],p.pk)

    def test_recipient_own_receipt_http_and_repeat_are_idempotent(self):
        p=self.pipeline();f=self.f;self.client.force_login(f['manager']);url=reverse('factory_detail',args=[self.work.pk]);response=self.client.get(url);self.assertContains(response,'Acknowledge receipt as myself');self.assertNotContains(response,'Inspect restricted subject')
        data={'action':'receive','revision':self.work.revision,'case_revision':rev(f['case']),'publication_id':p.pk};self.assertEqual(self.client.post(url,data).status_code,302)
        data['case_revision']=rev(f['case']);self.assertEqual(self.client.post(url,data).status_code,302);self.assertEqual(BUReceipt.objects.filter(report=p).count(),1);self.assertContains(self.client.get(url),'Your receipt is recorded')

    def test_preparer_cannot_impersonate_recipient(self):
        p=self.pipeline();f=self.f
        with self.assertRaises(PermissionDenied):bu.human_action(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),'receive',{'publication_id':p.pk})
        self.assertFalse(BUReceipt.objects.exists())

    def test_get_preserves_all_application_rows_for_preparer_and_recipient(self):
        p=self.pipeline();f=self.f;url=reverse('factory_detail',args=[self.work.pk])
        for actor in [f['preparer'],f['manager']]:
            self.client.force_login(actor);before=self.rowsets();self.assertEqual(self.client.get(url).status_code,200,actor.username);self.assertEqual(before,self.rowsets())

    def test_review_revocation_invalidates_verified_output_without_erasing_receipt(self):
        p=self.pipeline();self.finish(p);review(self.f,bu.result(self.work),'revoke')
        with self.assertRaises(ValidationError):bu.verify(self.work)
        self.assertEqual(BUReceipt.objects.filter(report=p).count(),1)

    def test_published_history_cannot_restart_after_source_replacement(self):
        p=self.pipeline();f=self.f;review(f,bu.result(self.work),'return');bu.correct(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),self.inputs,'Returned native result');self.work.refresh_from_db();bu.cancel(f['preparer'],self.work.pk,self.work.revision);self.work.refresh_from_db();self.assertEqual(self.work.status,'followup_needed')
        with self.assertRaises(ValidationError):bu.restart(f['preparer'],self.work.pk,self.work.revision,rev(f['case']),self.inputs,self.profile.pk,'bad-restart','Cannot erase history')
        self.assertTrue(BUReport.objects.filter(pk=p.pk).exists())

    def test_ordinary_factory_reader_without_bu_grant_cannot_find_work(self):
        from django.contrib.auth import get_user_model
        from apps.workflows.factory_views import visible
        f=self.f;actor=get_user_model().objects.create_user(username='ordinary-bu-outsider',password='synthetic-only')
        for action in ['case.read','factory.read','finance.read']:Grant.objects.create(case=f['case'],user=actor,action=action)
        self.assertFalse(visible(actor).filter(pk=self.work.pk).exists())
        self.client.force_login(actor);self.assertEqual(self.client.get(reverse('factory_detail',args=[self.work.pk])).status_code,404)
    def test_bu_reader_without_native_recipient_or_private_grant_cannot_inspect(self):
        from django.contrib.auth import get_user_model
        from apps.workflows.factory_bu_views import presentation
        f=self.f;actor=get_user_model().objects.create_user(username='nonrecipient-bu-reader',password='synthetic-only')
        for action in ['case.read','factory.read','bu.read','bu.report.read','bu.receive']:Grant.objects.create(case=f['case'],user=actor,action=action)
        panel=presentation(actor,self.work);self.assertEqual(panel['bu'],{'restricted':True})
        self.client.force_login(actor);response=self.client.get(reverse('factory_detail',args=[self.work.pk]));self.assertEqual(response.status_code,403)
        for private in ['E900','E002','BASIC','standard_pool_ref','weight_0','Inspect restricted subject']:self.assertNotIn(private,response.content.decode())
        with self.assertRaises(PermissionDenied):bu.human_action(actor,self.work.pk,self.work.revision,rev(f['case']),'receive',{'publication_id':self.saved_publication.pk})
        self.assertFalse(BUReceipt.objects.filter(report=self.saved_publication,actor=actor).exists())
    def test_native_recipient_get_has_no_private_business_fields_and_is_read_only(self):
        f=self.f;self.client.force_login(f['manager']);before=self.rowsets();response=self.client.get(reverse('factory_detail',args=[self.work.pk]));self.assertEqual(response.status_code,200)
        self.assertEqual(before,self.rowsets());self.assertContains(response,'Inspect your aggregate report')
        self.assertContains(response,'Received aggregate report');self.assertNotContains(response,self.work.request['reference'])
        for private in ['E900','E002','BASIC','standard_pool_ref','weight_0','Inspect restricted subject','source_id','payroll_id','rule_ids','comparison_id']:self.assertNotContains(response,private)
