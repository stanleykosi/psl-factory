import json
from pathlib import Path
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection, transaction, DatabaseError
from django.contrib.auth import get_user_model
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo import progress, escalations, delivery
from apps.pmo.models import DeliveryProgressSource, DeliveryProgressObservation, DeliveryProgressCorrelation, EscalationSignal, EscalationRequest, Baseline
from apps.pmo.issues import log_issue, update_issue
from apps.workflows import factory, factory_delivery, factory_escalation
from apps.documents.models import Publication, PublicationReceipt, PublicationJob
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from tests.test_delivery import DeliveryFixture
from tests.helpers import rev


class DeliveryProgressTests(DeliveryFixture,TestCase):
    @classmethod
    def setUpTestData(cls):
        f=DeliveryFixture();f.setup_delivery();f.approved=f.plan()
        for key,value in vars(f).items():setattr(cls,key,value)

    def source(self,kind=None,payload=None,evidence=None,verify=True):
        # Preserve the delivery fixture interface for plan corrections.
        if kind:return super().source(kind,payload,evidence,verify)
        return progress.configure(self.actor,self.case.pk,self.d.pk,'Engineering','Supplied Engineering Board','DEP-28',self.actor.pk,'synthetic_mock',self.e['requirements'].pk,rev(self.case))

    def observe(self,source,previous=None,version='eng-7',timeline=True,scope=False,availability='available'):
        fields={'activity_ref':'Activity-A / milestone M2','dependency_ref':'Dependency-D','summary':'Private Engineering delay: Dependency-D blocks Activity-A', 'timeline_impact':timeline,'scope_change':scope} if availability=='available' else {}
        return progress.observe(self.actor,self.case.pk,source.pk,previous.pk if previous else None,version,timezone.now(),availability,fields,rev(self.case))

    def issue(self):
        return log_issue(self.actor,self.case.pk,'P28-ISSUE','Dependency-D delay','Dependency',self.actor.pk,'Obtain dependency owner recovery evidence',self.e['requirements'].pk,'Authoritative PM/owner issue',rev(self.case))

    def link(self,obs,previous=None,state=None):
        state=state or self.issue()
        profile=escalations.capture_profile(self.actor,self.case.pk,state.issue_id,state.pk,'unclassified',obs.fields.get('timeline_impact'),None,self.e['requirements'].pk,'Source timeline impact; no invented trigger or route',rev(self.case))
        return progress.correlate(self.actor,self.case.pk,obs.pk,previous.pk if previous else None,self.approved.pk,state.issue_id,state.pk,profile.pk,'Activity-A cannot proceed until Dependency-D; completion date remains unknown',self.e['requirements'].pk,rev(self.case))

    def test_delayed_dependency_source_issue_plan_escalation__P28_M01(self):
        baseline=list(Baseline.objects.filter(case=self.case).values())
        source=self.source();obs=self.observe(source);row=self.link(obs)
        report=progress.report(self.actor,self.d)['sources'][0]
        self.assertEqual(report['issue_id'],row.issue_state.issue_id);self.assertEqual(report['owner_id'],self.actor.pk)
        self.assertEqual(report['planning_id'],self.approved.pk);self.assertIn('Dependency-D',report['impact'])
        self.assertTrue(report['escalation']['immediate']);self.assertEqual(report['escalation']['clock_status'],'UNCONFIGURED')
        self.assertEqual(EscalationSignal.objects.get(profile=row.profile).kind,'immediate')
        self.assertIsNone(row.issue_state.severity);self.assertIsNone(row.profile.trigger_at)
        self.assertFalse(EscalationRequest.objects.exists());self.assertFalse(Publication.objects.exists())
        self.assertEqual(list(Baseline.objects.filter(case=self.case).values()),baseline)
        from apps.agents.progress import investigate
        result=investigate(self.actor,self.case.pk,self.d.pk,rev(self.case)).result
        self.assertFalse(result['approval_granted']);self.assertFalse(result['suggestions_are_decisions'])
        with connection.cursor() as cur:
            cur.execute('SELECT psl_progress_profile(%s)',[row.profile_id]);self.assertTrue(cur.fetchone()[0])

    def test_capture_and_investigation_continue_without_plan_or_role_policy(self):
        delivery.capture_source(self.actor,self.case.pk,self.d.pk,'technical_design','new-design',self.e['requirements'].pk,{},rev(self.case))
        source=self.source();obs=self.observe(source,timeline=None)
        from apps.agents.progress import investigate
        result=investigate(self.actor,self.case.pk,self.d.pk,rev(self.case)).result
        self.assertEqual(result['sources'][0]['correlation_status'],'unlinked')
        self.assertTrue(any('unknown' in q for q in result['sources'][0]['questions']))
        with self.assertRaises(ValidationError):self.link(obs)
        self.assertEqual(DeliveryProgressObservation.objects.count(),1)

    def test_independent_observation_revision_and_unrelated_newer_draft_do_not_rewrite_baseline(self):
        obs=self.observe(self.source());row=self.link(obs)
        add_evidence(self.actor,self.case.pk,'plan','Unapproved new plan draft','synthetic:draft')
        add_evidence(self.actor,self.case.pk,'engineering_estimate','Unrelated revised estimate','synthetic:draft')
        self.assertEqual(progress.correlation_current(row).pk,row.pk)
        with connection.cursor() as cur:
            cur.execute('SELECT psl_progress_profile(%s)',[row.profile_id]);self.assertTrue(cur.fetchone()[0])

    def test_corrected_observation_invalidates_old_correlation_request_and_sql_preserves_history(self):
        source=self.source();obs=self.observe(source);row=self.link(obs)
        request=escalations.request_escalation(self.actor,self.case.pk,row.profile_id,'escalate','Client',self.e['requirements'].pk,'Explicit recipient direction',rev(self.case))
        newer=self.observe(source,obs,'eng-8',False)
        report=progress.report(self.actor,self.d)['sources'][0]
        self.assertEqual(report['correlation_status'],'stale');self.assertEqual(report['correlated_observation_id'],obs.pk)
        self.assertFalse(report['escalation']['immediate']);self.assertTrue(report['escalation']['historical_timing']['immediate'])
        with self.assertRaises(ValidationError):escalations.current_request(self.case,request.pk)
        with self.assertRaises(DatabaseError),transaction.atomic():EscalationRequest.objects.create(profile=row.profile,direction='escalate',target='CTO',evidence=self.e['requirements'],note='Cannot bypass current source',actor=self.actor)
        with self.assertRaises(DatabaseError),transaction.atomic():DeliveryProgressObservation.objects.filter(pk=obs.pk).update(fields={})
        with self.assertRaises(DatabaseError),transaction.atomic():DeliveryProgressCorrelation.objects.filter(pk=row.pk).delete()
        successor=self.link(newer,row,row.issue_state)
        self.assertEqual(successor.previous_id,row.pk);self.assertEqual(DeliveryProgressObservation.objects.count(),2)
        self.assertEqual(progress.report(self.actor,self.d)['sources'][0]['correlation_status'],'current')

    def test_current_owner_state_and_planning_sources_require_explicit_recorrelation(self):
        obs=self.observe(self.source());row=self.link(obs)
        update_issue(self.actor,self.case.pk,row.issue_state.issue_id,row.issue_state_id,'manage',self.e['requirements'].pk,'Owner changed next action',rev(self.case),next_action='New owner action')
        with self.assertRaises(ValidationError):progress.correlation_current(row)
        with connection.cursor() as cur:
            cur.execute('SELECT psl_progress_profile(%s)',[row.profile_id]);self.assertFalse(cur.fetchone()[0])

    def test_source_participant_and_read_scope_never_inherited_from_general_delivery(self):
        source=self.source();obs=self.observe(source);self.link(obs)
        reader=get_user_model().objects.create_user('progress-general-reader')
        Grant.objects.bulk_create([Grant(user=reader,case=self.case,action=a) for a in ['case.read','delivery.read','factory.read','evidence.add']])
        with self.assertRaises(PermissionDenied):progress.report(reader,self.d)
        self.client.force_login(reader);page=self.client.get(reverse('delivery_progress',args=[self.case.pk,self.d.pk]));self.assertEqual(page.status_code,403)
        self.assertNotContains(page,'Private Engineering delay',status_code=403)
        self.assertNotContains(self.client.get(reverse('case',args=[self.case.pk])),'Private Engineering delay')
        Grant.objects.create(user=reader,case=self.case,action='delivery.progress.read');Grant.objects.create(user=reader,case=self.case,action='delivery.progress.observe')
        with self.assertRaises(PermissionDenied):progress.observe(reader,self.case.pk,source.pk,obs.pk,'forged',timezone.now(),'unknown',{},rev(self.case))

    def test_revoked_source_authority_hides_fields_and_blocks_current_sql(self):
        obs=self.observe(self.source());row=self.link(obs)
        Grant.objects.filter(case=self.case,user=self.actor,action='delivery.progress.observe').update(active=False)
        with self.assertRaises(PermissionDenied):progress.report(self.actor,self.d)
        self.assertEqual(progress.optional_report(self.actor,self.d)['status'],'restricted_or_stale')
        with connection.cursor() as cur:
            cur.execute('SELECT psl_progress_profile(%s)',[row.profile_id]);self.assertFalse(cur.fetchone()[0])

    def test_unknown_unavailable_future_forged_and_stale_commands_do_not_invent_facts(self):
        source=self.source();obs=self.observe(source,availability='unavailable')
        with self.assertRaises(ValidationError):self.link(obs)
        with self.assertRaises(ValidationError):self.observe(source,version='eng-8')
        from datetime import timedelta
        with self.assertRaises(ValidationError):progress.observe(self.actor,self.case.pk,source.pk,obs.pk,'future',timezone.now()+timedelta(days=1),'unknown',{},rev(self.case))
        with self.assertRaises(DatabaseError),transaction.atomic():
            DeliveryProgressObservation.objects.create(source=source,previous=obs,source_version='forged',observed_at=timezone.now(),availability='unknown',fields={},evidence=self.e['requirements'],source_sha256=self.e['requirements'].sha256,actor=self.actor)
        self.assertEqual(DeliveryProgressObservation.objects.count(),1)

    def test_scope_change_and_observed_impact_do_not_create_approved_change_or_dates(self):
        row=self.link(self.observe(self.source(),scope=True))
        result=progress.report(self.actor,self.d)['sources'][0]
        self.assertTrue(any('P56' in q for q in result['questions']))
        from apps.pmo.models import ChangeAuthorization,ChangeRequest
        self.assertFalse(ChangeAuthorization.objects.exists());self.assertFalse(ChangeRequest.objects.exists())
        self.assertEqual(row.planning_id,self.approved.pk)

    def test_http_capture_correlate_read_only_get_and_privacy(self):
        self.client.force_login(self.actor);url=reverse('delivery_progress',args=[self.case.pk,self.d.pk])
        source=self.source()
        response=self.client.post(url,{'action':'observe','revision':rev(self.case),'source':source.pk,'source_version':'eng-http-1','observed_at':timezone.now().isoformat(),'availability':'available','activity_ref':'Activity-A','dependency_ref':'Dependency-D','summary':'HTTP actual source update','timeline_impact':'true','scope_change':'false'})
        self.assertEqual(response.status_code,302);obs=DeliveryProgressObservation.objects.get();state=self.issue()
        profile=escalations.capture_profile(self.actor,self.case.pk,state.issue_id,state.pk,'unclassified',True,None,self.e['requirements'].pk,'Actual source profile',rev(self.case))
        response=self.client.post(url,{'action':'correlate','revision':rev(self.case),'observation':obs.pk,'planning':self.approved.pk,'issue':state.issue_id,'state':state.pk,'profile':profile.pk,'impact':'Dependency delay requires explicit owner recovery','evidence':self.e['requirements'].pk})
        self.assertEqual(response.status_code,302)
        before=(rev(self.case),DeliveryProgressCorrelation.objects.count(),EscalationSignal.objects.count())
        self.assertContains(self.client.get(url),'immediate escalation required');self.assertContains(self.client.get(url),'HTTP actual source update')
        self.assertEqual(before,(rev(self.case),DeliveryProgressCorrelation.objects.count(),EscalationSignal.objects.count()))
        self.assertEqual(self.client.post(url,{'action':'correlate','revision':rev(self.case),'observation':obs.pk,'planning':self.approved.pk,'issue':state.issue_id,'state':state.pk,'profile':profile.pk,'impact':'Repeated stale form','evidence':self.e['requirements'].pk}).status_code,200)
        self.assertEqual(DeliveryProgressCorrelation.objects.count(),1)

    def test_factory_delivery_scoped_projection_and_source_revision_invalidate_investigation_not_release_authority(self):
        source=self.source();obs=self.observe(source);self.link(obs)
        value=json.loads(Path('fixtures/factory-delivery.json').read_text());value.pop('classification')
        config=draft_operator_policy(self.actor,self.case.pk,'OPS.factory_delivery_execution',value,self.e['policy_decision'].pk,timezone.now())
        transition(self.actor,config.pk,'validated');transition(self.actor,config.pk,'active')
        work=factory_delivery.start(self.actor,self.case.pk,'P28-DELIVERY',self.d.pk,'P28 delivery',rev(self.case));factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(factory_delivery.projection(self.actor,work)['progress_tracking']['sources'][0]['observation_id'],obs.pk)
        from apps.agents.models import AgentRun
        self.assertTrue(AgentRun.objects.filter(case=self.case,provider='deterministic-delivery-progress-v1').exists())
        self.client.force_login(self.actor);page=self.client.get(reverse('factory_detail',args=[work.pk]));self.assertContains(page,'Delivery progress and authoritative issues')
        Grant.objects.filter(case=self.case,user=self.actor,action='delivery.progress.read').update(active=False)
        self.assertNotContains(self.client.get(reverse('factory_detail',args=[work.pk])),'Dependency-D')

    def escalation_ready(self,row):
        value=json.loads(Path('fixtures/factory-escalation.json').read_text());value.pop('classification');value.update(preparer_id=self.actor.pk,executor_id=self.actor.pk)
        cfg=draft_operator_policy(self.actor,self.case.pk,'OPS.factory_escalation_execution',value,self.e['policy_decision'].pk,timezone.now());transition(self.actor,cfg.pk,'validated');transition(self.actor,cfg.pk,'active')
        request=escalations.request_escalation(self.actor,self.case.pk,row.profile_id,'escalate','Client',self.e['requirements'].pk,'Explicit client escalation request',rev(self.case))
        work=factory_escalation.start(self.actor,self.case.pk,'P28-ESCALATE',request.pk,self.t.pk,'P28 correlated escalation',rev(self.case))
        factory.run_until_wait(work.pk);work.refresh_from_db();self.assertEqual(work.status,'waiting',work.finding)
        self.assertFalse(Publication.objects.exists())
        factory_escalation.decide(self.actor,work.pk,work.revision,rev(self.case),request.pk,'Head of PMO','approve','Exact human communication decision')
        factory.run_until_wait(work.pk);work.refresh_from_db();version=factory_escalation.document(work);self.assertIsNotNone(version,work.finding)
        factory_escalation.review(self.actor,work.pk,work.revision,rev(self.case),version.pk,'approve','Exact human document review')
        return request,work,version

    def test_correlated_factory_communication_actual_receipts_and_unknown_effect_recovery(self):
        source=self.source();obs=self.observe(source);row=self.link(obs);request,work,version=self.escalation_ready(row)
        from apps.documents.controlled import reserve_publication
        from apps.documents.delivery import run_publication_once
        from adapters.publications import PublicationTimeoutAfterAccept,InternalPublicationAdapter
        publication=reserve_publication(self.actor,self.case.pk,version.pk,rev(self.case),factory_work_id=work.pk)
        run_publication_once(PublicationTimeoutAfterAccept(),job_id=publication.job.pk)
        job=PublicationJob.objects.get(publication=publication);self.assertEqual(job.status,'unknown')
        receipt=PublicationReceipt.objects.get(publication=publication)
        self.observe(source,obs,'eng-after-delivery',False)
        class LookupOnly(InternalPublicationAdapter):
            def deliver(self,*args):raise AssertionError('Must reconcile existing effect, not resend')
        work.refresh_from_db();factory_escalation.reconcile(self.actor,work.pk,work.revision,LookupOnly())
        job.refresh_from_db();self.assertEqual(job.status,'confirmed')
        self.assertEqual(PublicationReceipt.objects.get().pk,receipt.pk);self.assertEqual(Publication.objects.count(),1)
        with self.assertRaises(ValidationError):factory_escalation.verify(work,self.actor)
        self.assertEqual(row.issue_state.status,'Open')

    def test_corrected_source_blocks_reserved_dispatch_and_direct_publication_not_history(self):
        source=self.source();obs=self.observe(source);row=self.link(obs);_,work,version=self.escalation_ready(row)
        from apps.documents.controlled import reserve_publication
        from apps.documents.delivery import run_publication_once
        publication=reserve_publication(self.actor,self.case.pk,version.pk,rev(self.case),factory_work_id=work.pk)
        self.observe(source,obs,'eng-corrected',False)
        run_publication_once(job_id=publication.job.pk);job=PublicationJob.objects.get(publication=publication)
        self.assertEqual(job.status,'held');self.assertFalse(PublicationReceipt.objects.exists())
        with self.assertRaises(DatabaseError),transaction.atomic():
            # Direct trigger boundary, preserving every existing publication field.
            with connection.cursor() as cur:
                cur.execute('SELECT psl_progress_profile(%s)',[row.profile_id]);self.assertFalse(cur.fetchone()[0])
                cur.execute('UPDATE workflows_factorywork SET status=%s WHERE id=%s',['verified',work.pk])

    def test_successful_correlated_factory_receipt_then_native_recheck_invalidates_stale_claim(self):
        source=self.source();obs=self.observe(source);row=self.link(obs);_,work,_=self.escalation_ready(row)
        factory.run_until_wait(work.pk);work.refresh_from_db();self.assertEqual(work.status,'verified',work.finding)
        result=factory_escalation.verify(work,self.actor);self.assertEqual(len(result['receipt_ids']),1)
        before=PublicationReceipt.objects.get().pk
        self.observe(source,obs,'eng-new',False)
        with self.assertRaises(ValidationError):factory_escalation.verify(work,self.actor)
        self.assertTrue(factory_escalation.projection(self.actor,work)['readiness_changed'])
        self.assertEqual(PublicationReceipt.objects.get().pk,before)

    def test_explicit_source_age_holds_only_correlation_and_keeps_scoped_investigation(self):
        from datetime import timedelta
        source=progress.configure(self.actor,self.case.pk,self.d.pk,'Engineering','Supplied Board','STALE-28',self.actor.pk,'synthetic_mock',self.e['requirements'].pk,rev(self.case),max_age_seconds=60)
        fields={'activity_ref':'Activity-old','dependency_ref':'Dependency-old','summary':'Source recorded two minutes ago','timeline_impact':True,'scope_change':False}
        obs=progress.observe(self.actor,self.case.pk,source.pk,None,'old-1',timezone.now()-timedelta(minutes=2),'available',fields,rev(self.case))
        self.assertEqual(progress.report(self.actor,self.d)['sources'][0]['freshness'],'stale')
        from apps.agents.progress import investigate
        self.assertEqual(investigate(self.actor,self.case.pk,self.d.pk,rev(self.case)).result['sources'][0]['freshness'],'stale')
        with self.assertRaisesMessage(ValidationError,'age threshold'):self.link(obs)
        with connection.cursor() as cur:
            cur.execute('SELECT psl_progress_observation(%s)',[obs.pk]);self.assertFalse(cur.fetchone()[0])
        current=self.observe(source,obs,'current-2');self.assertEqual(progress.freshness(current),'fresh')
        self.assertEqual(DeliveryProgressObservation.objects.count(),2)

    def test_distinct_current_source_participant_can_capture_without_pmo_decision_authority(self):
        user=get_user_model().objects.create_user('engineering-source-participant')
        Grant.objects.bulk_create([Grant(user=user,case=self.case,action=a) for a in ['case.read','delivery.read','delivery.progress.read','delivery.progress.observe','evidence.add']])
        source=progress.configure(self.actor,self.case.pk,self.d.pk,'Engineering','Supplied Board','DISTINCT-28',user.pk,'synthetic_mock',self.e['requirements'].pk,rev(self.case))
        row=progress.observe(user,self.case.pk,source.pk,None,'participant-1',timezone.now(),'unknown',{},rev(self.case))
        self.assertEqual(row.actor_id,user.pk);self.assertEqual(row.evidence.created_by_id,user.pk)
        self.assertEqual(progress.report(self.actor,self.d)['sources'][0]['availability'],'unknown')
        self.assertFalse(DeliveryProgressCorrelation.objects.exists())

    def test_cross_project_and_cross_dossier_selections_do_not_correlate(self):
        from tests.helpers import setup_case,project_evidence
        actor,case=setup_case(username='foreign-progress');e=project_evidence(actor,case)
        state=log_issue(actor,case.pk,'FOREIGN-ISSUE','Other case issue','Dependency',actor.pk,'Other action',e['requirements'].pk,'Other source',rev(case))
        obs=self.observe(self.source(),timeline=False)
        with self.assertRaises(ValidationError):progress.correlate(self.actor,self.case.pk,obs.pk,None,self.approved.pk,state.issue_id,state.pk,None,'Guessed foreign source',self.e['requirements'].pk,rev(self.case))
        private=add_evidence(self.actor,self.case.pk,'agent_private_issue_readback','Not public correlation proof','synthetic:private')
        state=self.issue()
        with self.assertRaises(ValidationError):progress.correlate(self.actor,self.case.pk,obs.pk,None,self.approved.pk,state.issue_id,state.pk,None,'Invalid private proof',private.pk,rev(self.case))
        self.assertFalse(DeliveryProgressCorrelation.objects.exists())

    def test_source_reader_without_issue_scope_can_still_capture_and_investigate_after_linking(self):
        source=self.source();obs=self.observe(source);self.link(obs)
        reader=get_user_model().objects.create_user('source-only-reader')
        Grant.objects.bulk_create([Grant(user=reader,case=self.case,action=a) for a in ['case.read','delivery.read','delivery.progress.read','agent.delivery']])
        result=progress.report(reader,self.d)['sources'][0]
        self.assertEqual(result['correlation_status'],'restricted');self.assertNotIn('issue_id',result)
        self.assertEqual(result['observation_id'],obs.pk)
        self.client.force_login(reader);self.assertContains(self.client.get(reverse('delivery_progress',args=[self.case.pk,self.d.pk])),'Private Engineering delay')
        from apps.agents.progress import investigate
        self.assertNotIn('issue_id',investigate(reader,self.case.pk,self.d.pk,rev(self.case)).result['sources'][0])

from django.test import TransactionTestCase
class ProgressConcurrencyTests(TransactionTestCase):
    def test_two_postgresql_connections_capture_only_one_exact_successor(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        f=DeliveryFixture();f.setup_delivery()
        source=progress.configure(f.actor,f.case.pk,f.d.pk,'Engineering','Concurrent supplied board','CONCURRENT',f.actor.pk,'synthetic_mock',f.e['requirements'].pk,rev(f.case))
        old=progress.observe(f.actor,f.case.pk,source.pk,None,'original',timezone.now(),'unknown',{},rev(f.case))
        expected=rev(f.case);barrier=Barrier(2)
        def writer(version):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=f.actor.pk);barrier.wait(timeout=10)
                try:return ('created',progress.observe(actor,f.case.pk,source.pk,old.pk,version,timezone.now(),'unknown',{},expected).pk)
                except ValidationError:return ('stale',None)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(writer,'version-'+str(i)) for i in range(2)];results=[item.result(timeout=40) for item in futures]
        self.assertEqual(sorted(x[0] for x in results),['created','stale'])
        self.assertEqual(DeliveryProgressObservation.objects.count(),2)
