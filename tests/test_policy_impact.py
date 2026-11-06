from concurrent.futures import ThreadPoolExecutor
from threading import Barrier,Event
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,DatabaseError,close_old_connections,connection
from django.test import TestCase,TransactionTestCase,Client
from django.urls import reverse
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy import impact,scopes
from apps.policy.models import ImpactAssessment,ImpactReview,Configuration
from apps.policy.services import transition,save_draft,reference_values,resolve,PolicyHold
from apps.agents.policy_impact import investigate
from adapters import policy_impact as adapter
from tests.helpers import setup_case,prepared,rev,envelope,activate
from tests.test_policy_scopes import source_version


def setup():
    actor,case=setup_case(username='impact-author');e=prepared(actor,case)
    previous=resolve('D05.role_principal_assignments',case).configuration
    from apps.pmo.services import decide
    for role in ['PM','Head of PMO','CEO','PMO Lead']:decide(actor,case.pk,role,rev(case))
    successor=activate(actor,case,previous.component,previous.envelope['value'],e['policy_decision'])
    reviewer=get_user_model().objects.create_user(username='impact-reviewer')
    Grant.objects.bulk_create([Grant(user=reviewer,case=case,action=action) for action in Grant.objects.filter(user=actor,case=case).values_list('action',flat=True)])
    return actor,reviewer,case,e,previous,successor


class PolicyImpactTests(TestCase):
    def setUp(self):self.a,self.b,self.c,self.e,self.old,self.new=setup()

    def capture(self,keys=None):
        return impact.capture(self.a,self.c.pk,self.old.pk,self.new.pk,keys or ['pmo.decisions'],self.e['policy_decision'].pk,'Review exact pending decisions against the new local policy')

    def test_actual_pmo_decisions_are_observed_and_acceptance_cannot_copy_approval(self):
        from apps.pmo.services import sign_baseline,decide
        from apps.pmo.models import Decision,Baseline
        row=self.capture();self.assertEqual(row.observation['domains']['pmo.decisions'][0]['state'],'decision_requires_current_authority')
        self.assertEqual(len(row.observation['domains']['pmo.decisions']),4)
        self.assertEqual(self.capture().pk,row.pk)
        with self.assertRaises(PermissionDenied):impact.review(self.a,self.c.pk,row.pk,'accept',self.e['policy_decision'].pk,'Self review')
        review=impact.review(self.b,self.c.pk,row.pk,'accept',self.e['policy_decision'].pk,'Observed domain heads and successor checked')
        self.assertTrue(impact.inspect(self.b,self.c.pk,row.pk)['current'])
        with self.assertRaises(ValidationError):sign_baseline(self.a,self.c.pk,self.e['signature'].pk,rev(self.c))
        self.assertEqual(Decision.objects.count(),4);self.assertIsNone(Baseline.objects.get(case=self.c).signed_id)
        for role in ['PM','Head of PMO','CEO','PMO Lead']:decide(self.a,self.c.pk,role,rev(self.c))
        sign_baseline(self.a,self.c.pk,self.e['signature'].pk,rev(self.c))
        self.assertFalse(impact.inspect(self.a,self.c.pk,row.pk)['current'])
        self.assertEqual(ImpactReview.objects.get().pk,review.pk)
        self.assertEqual(Decision.objects.count(),8)

    def test_stale_policy_evidence_case_and_unsupported_adapter_are_held(self):
        row=self.capture();transition(self.a,self.new.pk,'revoked')
        with self.assertRaises(ValidationError):impact.review(self.b,self.c.pk,row.pk,'accept',self.e['policy_decision'].pk,'Now stale')
        self.assertEqual(ImpactReview.objects.count(),0)
        impact.review(self.b,self.c.pk,row.pk,'defer',self.e['policy_decision'].pk,'Policy must be revisited')
        with self.assertRaises(ValidationError):impact.page(self.a,self.c.pk,self.old.pk,'arbitrary.models')
        with self.assertRaises(ValidationError):impact.capture(self.a,self.c.pk,self.new.pk,self.old.pk,['pmo.decisions'],self.e['policy_decision'].pk,'Wrong direction')

    def test_actual_domain_head_change_blocks_accept_then_allows_recorded_rejection(self):
        row=self.capture()
        from apps.pmo.services import sign_baseline,decide
        for role in ['PM','Head of PMO','CEO','PMO Lead']:decide(self.a,self.c.pk,role,rev(self.c))
        sign_baseline(self.a,self.c.pk,self.e['signature'].pk,rev(self.c))
        with self.assertRaises(ValidationError):impact.review(self.b,self.c.pk,row.pk,'accept',self.e['policy_decision'].pk,'Cannot ignore signed head')
        impact.review(self.b,self.c.pk,row.pk,'reject',self.e['policy_decision'].pk,'Record changed; successor assessment required')
        self.assertEqual(ImpactReview.objects.get().verdict,'reject')

    def test_new_current_human_decision_changes_head_before_signature(self):
        from apps.pmo.services import decide
        row=self.capture();decide(self.a,self.c.pk,'PM',rev(self.c))
        self.assertFalse(impact.inspect(self.a,self.c.pk,row.pk)['current'])
        with self.assertRaises(ValidationError):impact.review(self.b,self.c.pk,row.pk,'accept',self.e['policy_decision'].pk,'Head changed before signature')

    def test_paged_projection_is_actor_configuration_bound_and_cannot_hide_truncation(self):
        first=impact.page(self.a,self.c.pk,self.old.pk,'pmo.decisions',limit=2)
        second=impact.page(self.a,self.c.pk,self.old.pk,'pmo.decisions',first['next_cursor'],limit=2)
        self.assertEqual(len(first['records'])+len(second['records']),4)
        self.assertFalse(set(r['id'] for r in first['records'])&set(r['id'] for r in second['records']))
        with self.assertRaises(ValidationError):impact.page(self.b,self.c.pk,self.old.pk,'pmo.decisions',first['next_cursor'])
        with self.assertRaises(ValidationError):impact.page(self.a,self.c.pk,self.new.pk,'pmo.decisions',first['next_cursor'])
        with self.assertRaises(ValidationError):impact.page(self.a,self.c.pk,self.old.pk,'pmo.decisions','forged')
        self.assertTrue(first['uncovered']);self.assertIn('not a complete',first['coverage'])

    def test_snapshot_budget_holds_capture_but_paged_investigation_still_works(self):
        from apps.pmo.models import Decision
        # Persisted synthetic historical pins exercise the technical budget; no business approval is asserted.
        for index in range(101):
            evidence=add_evidence(self.a,self.c.pk,'costing',f'Synthetic archived costing {index}','synthetic:impact-budget')
            Decision.objects.create(case=self.c,evidence=evidence,role='PM',actor=self.a,policy=self.old)
        self.assertEqual(len(impact.page(self.a,self.c.pk,self.old.pk,'pmo.decisions',limit=50)['records']),50)
        with self.assertRaises(ValidationError):self.capture()
        self.assertFalse(ImpactAssessment.objects.exists())

    def test_source_and_domain_permissions_are_current_and_no_cross_case_ids(self):
        a,s=setup_case(username='impact-source-author');ev=add_evidence(a,s.pk,'policy_decision','Synthetic criteria','synthetic')
        for user in [self.a,self.b]:
            for action in ['case.read','policy.read']:Grant.objects.create(user=user,case=s,action=action)
        source=source_version(a,s,ev)
        old=scopes.apply(self.a,source.pk,self.c.pk,self.e['policy_decision'].pk,[]);transition(self.a,old.pk,'validated');transition(self.a,old.pk,'active')
        new=activate(self.a,self.c,old.component,'Africa/Lagos',self.e['policy_decision'])
        row=impact.capture(self.a,self.c.pk,old.pk,new.pk,['pmo.decisions'],self.e['policy_decision'].pk,'Explicit empty selected domain coverage')
        Grant.objects.filter(user=self.b,case=s,action='policy.read').update(active=False)
        with self.assertRaises(PermissionDenied):impact.inspect(self.b,self.c.pk,row.pk)
        foreign=add_evidence(a,s.pk,'policy_decision','Foreign proof','synthetic')
        with self.assertRaises(ValidationError):impact.capture(self.a,self.c.pk,old.pk,new.pk,['pmo.decisions'],foreign.pk,'Foreign evidence')
        Grant.objects.filter(user=self.a,case=self.c,action='finance.read').update(active=False)
        with self.assertRaises(PermissionDenied):impact.page(self.a,self.c.pk,self.old.pk,'finance.runs')

    def test_history_sql_guards_and_current_reviewer_authority(self):
        row=self.capture();self.assertEqual(connection.vendor,'postgresql')
        with self.assertRaises(DatabaseError),transaction.atomic():ImpactAssessment.objects.filter(pk=row.pk).update(reason='rewritten')
        with self.assertRaises(DatabaseError),transaction.atomic():ImpactReview.objects.create(assessment=row,verdict='accept',observed_sha256=row.sha256,evidence=self.e['policy_decision'],reason='Self review',actor=self.a)
        impact.review(self.b,self.c.pk,row.pk,'accept',self.e['policy_decision'].pk,'Second human review')
        with self.assertRaises(DatabaseError),transaction.atomic():ImpactReview.objects.all().delete()
        Grant.objects.filter(user=self.b,case=self.c,action='policy.activate').update(active=False)
        self.assertFalse(impact.inspect(self.a,self.c.pk,row.pk)['review_authority_current'])

    def test_revoked_author_cannot_supply_current_acceptance_and_unrelated_capture_continues(self):
        row=self.capture()
        Grant.objects.filter(user=self.a,case=self.c,action='policy.configure').update(active=False)
        with self.assertRaises(PermissionDenied):impact.review(self.b,self.c.pk,row.pk,'accept',self.e['policy_decision'].pk,'Author permission withdrawn')
        self.assertFalse(ImpactReview.objects.exists())
        self.assertTrue(add_evidence(self.a,self.c.pk,'document','Unrelated work continues','synthetic').pk)

    def test_archived_accepted_history_cannot_supply_fresh_authority(self):
        row=self.capture()
        impact.review(self.b,self.c.pk,row.pk,'accept',self.e['policy_decision'].pk,'Historical engineering review')
        get_user_model().objects.filter(pk__in=[self.a.pk,self.b.pk]).update(is_active=False,password='!')
        Grant.objects.filter(case=self.c).delete()
        self.assertEqual(ImpactAssessment.objects.count(),1);self.assertEqual(ImpactReview.objects.count(),1)
        with self.assertRaises(PermissionDenied):impact.inspect(self.a,self.c.pk,row.pk)

    def test_current_case_policy_authorization_precedes_record_existence_lookup(self):
        row=self.capture();outsider=get_user_model().objects.create_user(username='impact-outsider')
        for pk in [self.old.pk,999999999]:
            with self.assertRaises(PermissionDenied):impact.configuration(outsider,self.c.pk,pk)
        client=Client();client.force_login(outsider)
        for pk in [row.pk,999999999]:
            with self.assertRaises(PermissionDenied):impact.inspect(outsider,self.c.pk,pk)
            self.assertEqual(client.get(reverse('policy_impact_assessment',args=[self.c.pk,pk])).status_code,403)
        Grant.objects.create(user=outsider,case=self.c,action='case.read')
        for pk in [self.old.pk,999999999]:
            with self.assertRaises(PermissionDenied):impact.configuration(outsider,self.c.pk,pk)

    def test_ui_csrf_agent_and_limited_metadata(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.a);url=reverse('policy_impact',args=[self.c.pk])
        self.assertContains(client.get(url),'Domain policy impact')
        self.assertEqual(client.post(url,{}).status_code,403)
        response=client.post(url,{'previous':self.old.pk,'successor':self.new.pk,'adapters':['pmo.decisions'],'evidence':self.e['policy_decision'].pk,'reason':'Review exact heads','csrfmiddlewaretoken':client.cookies['csrftoken'].value})
        self.assertEqual(response.status_code,302)
        row=ImpactAssessment.objects.get()
        report=investigate(self.a,self.c.pk,row.pk)
        self.assertEqual(report['effect_tools'],[]);self.assertFalse(report['business_approval'])
        self.assertNotIn(self.e['costing'].body,str(report))
        self.assertContains(client.get(response.url),'Record independent review')
        client.force_login(self.b)
        reviewurl=reverse('policy_impact_assessment',args=[self.c.pk,row.pk]);client.get(reviewurl)
        result=client.post(reviewurl,{'verdict':'accept','evidence':self.e['policy_decision'].pk,'reason':'Current authorized heads reviewed','csrfmiddlewaretoken':client.cookies['csrftoken'].value})
        self.assertEqual(result.status_code,302)


class DomainImpactTests(TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.readiness_helpers import endpoint
        cls.endpoint=endpoint();cls.remote=cls.endpoint.__enter__()
        try:super().setUpClass()
        except BaseException:cls.endpoint.__exit__(None,None,None);raise

    @classmethod
    def tearDownClass(cls):
        try:super().tearDownClass()
        finally:cls.endpoint.__exit__(None,None,None)

    def test_actual_pmo_action_and_schedule_pins_and_rearming_changes_observed_head(self):
        from tests.meeting_helpers import meetings_fixture,configure_clock
        from apps.pmo.meetings import create_action
        from apps.pmo.schedules import save_schedule,arm_schedule
        from django.utils import timezone
        a,c,owner,notes,minutes,template,meeting,recipient=meetings_fixture()
        old=configure_clock(a,c,owner)
        item=create_action(a,c.pk,'IMPACT-ACTION','Actual calculated commitment',a.pk,None,notes.pk,'Synthetic commitment',rev(c),meeting.meeting_id,calculated=True)
        schedule=save_schedule(a,c.pk,'internal_tuesday',template.pk,'internal',rev(c))
        arm_schedule(a,c.pk,schedule.pk,timezone.now(),rev(c))
        new=activate(a,c,old.component,old.envelope['value'],owner)
        row=impact.capture(a,c.pk,old.pk,new.pk,['pmo.actions','pmo.schedules'],owner.pk,'Review actual pending action and schedule')
        self.assertEqual(row.observation['domains']['pmo.actions'][0]['subject'],item.pk)
        self.assertEqual(row.observation['domains']['pmo.schedules'][0]['id'],schedule.pk)
        arm_schedule(a,c.pk,schedule.pk,timezone.now(),rev(c))
        self.assertFalse(impact.inspect(a,c.pk,row.pk)['current'])

    def test_finance_billing_uses_actual_typed_pins_and_requires_rebuilt_snapshot(self):
        from tests.billing_helpers import coverage,prices,usage,prepare,policy,evidence,FIXTURE
        from apps.finance.billing import ensure_current
        import json
        a,c=setup_case(username='impact-finance');cov=coverage(a,c);configs=prices(a,c,cov);u=usage(a,c,cov);p=prepare(a,c,cov,u=u)
        old=configs[0];f=json.loads(FIXTURE.read_text(encoding='utf-8'));new=policy(a,c,old.component,[dict(f['rule'],coverage_id=cov.pk)])
        proof=evidence(a,c,'policy_decision','Synthetic impact review evidence')
        row=impact.capture(a,c.pk,old.pk,new.pk,['finance.billing'],proof.pk,'Actual billing snapshot review')
        self.assertEqual(row.observation['domains']['finance.billing'][0]['id'],p.pk)
        with self.assertRaises(ValidationError):ensure_current(p)
        newer=prepare(a,c,cov,u=u);self.assertNotEqual(newer.pk,p.pk)
        self.assertFalse(impact.inspect(a,c.pk,row.pk)['current'])

    def test_finance_run_adapter_matches_actual_mapping_preview(self):
        from tests.finance_analysis_helpers import fixture,policy
        from apps.finance import analysis
        a,c,e,f,configs,source,t,recipient=fixture(username='impact-mapping',recipient_username='impact-mapping-reader')
        run=analysis.map_source(a,c.pk,source.pk,[],rev(c));old=configs['D06.account_bu_maps']
        new=policy(a,c,old.component,f['mapping'],e['policy_decision'])
        result=impact.page(a,c.pk,old.pk,'finance.runs')
        self.assertEqual(result['records'][0]['id'],run.pk)
        self.assertNotIn('financial_metrics',str(result))

    def test_actual_invoice_effect_and_committed_receipt_survive_review_without_reissue(self):
        from tests.settlement_helpers import fixture,draft,approve
        from tests.billing_helpers import policy,evidence
        from apps.finance import invoices,invoice_delivery
        from apps.finance.models import InvoiceIssue,InvoiceJob
        a,c,cov,p,e=fixture();invoice=draft(a,c,p);approve(a,c,invoice,e)
        old=resolve('D08.adapter_contract_ref',c).configuration
        job=invoices.reserve(a,c.pk,invoice.pk,'issue','Finance',rev(c))
        self.assertEqual(impact.page(a,c.pk,old.pk,'finance.invoice_effects')['records'][0]['state'],'pending_effect')
        invoice_delivery.run_once()
        price=resolve('D08.effective_price_rule_refs',c).configuration
        billing_record=impact.page(a,c.pk,price.pk,'finance.billing')['records'][0]
        self.assertEqual(billing_record['invoice_head'],invoice.pk)
        self.assertNotIn('invoice_ids',billing_record)
        self.assertEqual(impact.page(a,c.pk,old.pk,'finance.invoice_effects')['records'][0]['state'],'committed_effect')
        new=policy(a,c,old.component,reference_values(old)[0]);proof=evidence(a,c,'policy_decision','Synthetic engineering reassessment')
        row=impact.capture(a,c.pk,old.pk,new.pk,['finance.invoice_effects'],proof.pk,'Preserve actual committed local invoice receipt')
        reviewer=get_user_model().objects.create_user(username='impact-invoice-reviewer')
        Grant.objects.bulk_create([Grant(user=reviewer,case=c,action=action) for action in ['case.read','policy.read','policy.activate','finance.read']])
        impact.review(reviewer,c.pk,row.pk,'accept',proof.pk,'No reissue; use source-owned services for further action')
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceJob.objects.get(pk=job.pk).attempts,1)

    def test_baas_event_and_report_adapters_use_real_flow_and_indirect_head_pins(self):
        from tests.support_helpers import fixture,ready,report,policy,act
        from apps.policy.support_validators import FLOW
        f=fixture('impact-support');event=ready(f);r=report(f);old=f['policies'][FLOW]
        new=policy(f,FLOW,f['v']['flow'])
        row=impact.capture(f['actor'],f['case'].pk,old.pk,new.pk,['baas.events','baas.reports'],f['e']['policy_decision'].pk,'Review actual B14 heads')
        self.assertEqual(row.observation['domains']['baas.events'][0]['id'],event.pk)
        self.assertEqual(row.observation['domains']['baas.reports'][0]['id'],r.pk)
        self.assertEqual(impact.inspect(f['actor'],f['case'].pk,row.pk)['effect_tools'],[])
        Grant.objects.filter(user=f['actor'],case=f['case'],action='support.read').update(active=False)
        with self.assertRaises(PermissionDenied):impact.inspect(f['actor'],f['case'].pk,row.pk)

    def test_private_response_pending_unknown_and_receipt_are_not_replayed(self):
        from tests.support_release_helpers import ready,release
        from tests.support_helpers import policy
        from apps.baas import support_release as d,support_release_delivery as worker
        from apps.policy.support_release_validators import COMPONENT
        from adapters.support_response import InternalSupportResponseAdapter
        f=ready('impact-response');job=release(f);old=f['release_policy']
        records=impact.page(f['actor'],f['case'].pk,old.pk,'baas.response_effects')['records']
        self.assertEqual(records[0]['state'],'pending_effect')
        class UncertainBeforeAcceptance(InternalSupportResponseAdapter):
            def deliver(self,*args):raise TimeoutError('Synthetic external transport fault')
        worker.run_once(f['case'].pk,UncertainBeforeAcceptance())
        self.assertEqual(impact.page(f['actor'],f['case'].pk,old.pk,'baas.response_effects')['records'][0]['state'],'uncertain_effect')
        class LostReplyAfterAcceptance(InternalSupportResponseAdapter):
            def deliver(self,*args):super().deliver(*args);raise TimeoutError('Synthetic reply loss')
        worker.run_once(f['case'].pk,LostReplyAfterAcceptance())
        self.assertEqual(impact.page(f['actor'],f['case'].pk,old.pk,'baas.response_effects')['records'][0]['state'],'committed_receipt_requires_reconciliation')
        new=policy(f,COMPONENT,f['release_rules'])
        row=impact.capture(f['actor'],f['case'].pk,old.pk,new.pk,['baas.response_effects'],f['e']['policy_decision'].pk,'Review uncertainty without retrying effects')
        impact.review(f['reviewer'],f['case'].pk,row.pk,'accept',f['e']['policy_decision'].pk,'Receipt-first domain recovery remains separate')
        self.assertEqual(d.Job.objects.get(pk=job.pk).attempts,2);self.assertEqual(d.Receipt.objects.count(),1)
        Grant.objects.filter(user=f['reviewer'],case=f['case'],action='support.response.release').update(active=False)
        class NoResend(InternalSupportResponseAdapter):
            def deliver(self,*args):raise AssertionError('Committed effect must not be replayed')
        worker.run_once(f['case'].pk,NoResend())
        self.assertEqual(impact.page(f['actor'],f['case'].pk,old.pk,'baas.response_effects')['records'][0]['state'],'committed_effect')
        self.assertFalse(impact.inspect(f['actor'],f['case'].pk,row.pk)['current']);self.assertEqual(d.Receipt.objects.count(),1)
        Grant.objects.filter(user=f['actor'],case=f['case'],action='support.private.read').update(active=False)
        with self.assertRaises(PermissionDenied):impact.page(f['actor'],f['case'].pk,old.pk,'baas.response_effects')


class ImpactConcurrencyTests(TransactionTestCase):
    def test_effect_lock_conflict_holds_observation_without_case_job_deadlock(self):
        from tests.settlement_helpers import fixture,draft,approve
        from tests.billing_helpers import policy,evidence
        from apps.finance import invoices
        from apps.finance.models import InvoiceJob
        a,c,cov,p,e=fixture();invoice=draft(a,c,p);approve(a,c,invoice,e)
        old=resolve('D08.adapter_contract_ref',c).configuration
        job=invoices.reserve(a,c.pk,invoice.pk,'issue','Finance',rev(c))
        new=policy(a,c,old.component,reference_values(old)[0]);proof=evidence(a,c,'policy_decision','Synthetic lock conflict evidence')
        locked,release=Event(),Event()
        def holder():
            close_old_connections()
            try:
                with transaction.atomic():
                    InvoiceJob.objects.select_for_update().get(pk=job.pk);locked.set();self.assertTrue(release.wait(15))
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(holder);self.assertTrue(locked.wait(10))
            try:
                with self.assertRaises(ValidationError):impact.capture(a,c.pk,old.pk,new.pk,['finance.invoice_effects'],proof.pk,'Do not deadlock active reconciliation')
            finally:release.set()
            future.result(timeout=20)
        self.assertFalse(ImpactAssessment.objects.exists());self.assertEqual(InvoiceJob.objects.get(pk=job.pk).attempts,0)

    def test_duplicate_capture_and_competing_review_are_serialized(self):
        a,b,c,e,old,new=setup();barrier=Barrier(2)
        def capture(_):
            close_old_connections();u=get_user_model().objects.get(pk=a.pk);barrier.wait()
            try:return impact.capture(u,c.pk,old.pk,new.pk,['pmo.decisions'],e['policy_decision'].pk,'Concurrent exact observation').pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(capture,range(2)))
        self.assertEqual(ids[0],ids[1]);barrier=Barrier(2)
        def review(_):
            close_old_connections();u=get_user_model().objects.get(pk=b.pk);barrier.wait()
            try:
                try:return impact.review(u,c.pk,ids[0],'accept',e['policy_decision'].pk,'Concurrent review').pk
                except ValidationError:return 'conflict'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(review,range(2)))
        self.assertEqual(results.count('conflict'),1);self.assertEqual(ImpactReview.objects.count(),1)
