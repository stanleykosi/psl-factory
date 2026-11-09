from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,DatabaseError,transaction,close_old_connections
from django.test import TestCase,TransactionTestCase
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import register_reference,transition,PolicyHold,save_draft
from apps.policy.change_drafts import draft_standard_policy
from apps.pmo.delivery import (open_dossier,capture_source,verify_source,decide_planning,record_progress,
    record_release_request,prepare_readiness,capture_release,planning_inputs,readiness_inputs,valid_release,PLANNING,UPSTREAM_GATES,GLPI_GATES)
from apps.pmo.delivery_closure import (accept_go_live,evaluate_hypercare,hypercare_inputs,archive_artifacts,
    acknowledge_handover,confirm_finance,decide_closure,finalize_closure,closure_inputs)
from apps.pmo.delivery_documents import draft_delivery_document
from apps.pmo.gates import register_candidate,record_gate,verify_gate
from apps.pmo.meetings import record_meeting
from apps.pmo.models import DeliveryRecord,DeliverySource,DeliverySourceVerification,DeliveryDocumentBinding
from apps.pmo.services import complete_milestone
from apps.documents.controlled import register_template,request_review,review_version,reserve_publication,preflight
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt,PublicationJob
from apps.agents.delivery import investigate_delivery
from apps.workflows.services import run_once
from adapters.delivery import SyntheticDeliverySourceAdapter
from .helpers import setup_case,signed,prepared,rev,activate,envelope
from .document_helpers import artifact

CRITERIA={'clock':'elapsed_hours_since_release','minimum_hours':0,'confirmation_owners':['Engineering','Infrastructure'],
    'metrics':[{'key':'errors','unit':'count','owner':'Engineering','operator':'lte','threshold':0},
        {'key':'availability','unit':'percent','owner':'Infrastructure','operator':'gte','threshold':99}], 'financial_controls':'independent'}


class DeliveryFixture:
    def setup_delivery(self):
        self.actor,self.case=setup_case();self.e=signed(self.actor,self.case)
        self.candidate=register_candidate(self.actor,self.case.pk,'delivery-build',self.e['requirements'].pk,rev(self.case))
        self.d=open_dossier(self.actor,self.case.pk,self.candidate.pk,self.e['plan'].pk,'PM scope attestation for this requirements/plan',rev(self.case))
        self.t=register_template(self.actor,self.case.pk,'Delivery artifact',{'document_type':'project_artifact','required_fields':['executive_summary','status'],
            'internal_review_required':False,'audience_fields':{a:['executive_summary','scope','risks','status','next_steps','timeline','dependencies'] for a in ['client','internal']}},self.e['policy_decision'].pk,rev(self.case))
        refs=[]
        for a in ['client','internal']:
            r=register_reference(self.actor,self.case.pk,'delivery-recipient:'+a,'schema:psl/document-recipient/v1',{'audience':a,'user_id':self.actor.pk},self.e['policy_decision'].pk);refs.append(r.ref)
        activate(self.actor,self.case,'D11.recipient_grant_refs',refs,self.e['policy_decision'])
        self.storage(False)

    def evidence(self,kind,body=None):return add_evidence(self.actor,self.case.pk,kind,body or 'Synthetic '+kind,'synthetic:delivery-test')

    def source(self,kind,payload=None,evidence=None,verify=True):
        s=capture_source(self.actor,self.case.pk,self.d.pk,kind,'owned:'+kind,(evidence or self.e['requirements']).pk,payload or {},rev(self.case))
        if verify:verify_source(self.actor,self.case.pk,s.pk,rev(self.case))
        return s

    def plan(self):
        for kind in PLANNING:self.source(kind,{'requires_ui':False,'client_signoff_required':False} if kind=='ui_applicability' else {})
        decision=decide_planning(self.actor,self.case.pk,self.d.pk,'approve',self.e['plan'].pk,'PMO Lead exact Planning exit',rev(self.case))
        m=record_meeting(self.actor,self.case.pk,'KICKOFF','kickoff',timezone.now(),'Delivery expectations','Participants aligned with approved plan',[self.actor.pk],[],self.e['requirements'].pk,rev(self.case))
        record_progress(self.actor,self.case.pk,self.d.pk,'kickoff',m.evidence_id,'Actual kickoff after plan approval',rev(self.case),m.pk)
        return decision

    def gates(self,kinds,ref=None):
        for kind in kinds:
            g=record_gate(self.actor,self.case.pk,self.candidate.pk,kind,ref or 'gate:'+kind,self.e['requirements'].pk,rev(self.case))
            verify_gate(self.actor,self.case.pk,g.pk,rev(self.case))

    def ready(self):
        self.plan();self.gates(UPSTREAM_GATES)
        record_release_request(self.actor,self.case.pk,self.d.pk,'GLPI-001',self.e['requirements'].pk,'Actual externally raised request',rev(self.case))
        self.gates(GLPI_GATES,'GLPI-001')
        return prepare_readiness(self.actor,self.case.pk,self.d.pk,rev(self.case))

    def release(self):
        ready=self.ready()
        return capture_release(self.actor,self.case.pk,self.d.pk,ready.pk,timezone.now(),'Infra-release-1',self.e['completion'].pk,'Actual Infra/DevOps release',rev(self.case))

    def publish(self,v):
        if v.audience=='client':
            request_review(self.actor,self.case.pk,v.pk,rev(self.case));review_version(self.actor,self.case.pk,v.pk,'approve','Exact client projection checked',rev(self.case))
        reserve_publication(self.actor,self.case.pk,v.pk,rev(self.case));assert run_publication_once()
        return PublicationReceipt.objects.get(publication__version=v)

    def accepted(self):
        o=self.release();data={k:self.evidence(kind).pk for k,kind in [('checklist','deployment_checklist'),('incident_reporting','incident_reporting'),('rollback','rollback_plan')]}
        v=draft_delivery_document(self.actor,self.case.pk,self.d.pk,'go_live',self.t.pk,data,rev(self.case));receipt=self.publish(v)
        pm=self.evidence('signature','Exact PM go-live signature');client=self.evidence('signature','Exact Client go-live signature')
        accept_go_live(self.actor,self.case.pk,self.d.pk,receipt.pk,pm.pk,client.pk,'PM attests exact two signatures',rev(self.case),attestation=self.attestation(receipt,pm,client));return o

    def attestation(self,receipt,pm,client,actor=None,signed_at=None):
        from tests.go_live_helpers import attestation
        return attestation(self,receipt,pm,client,actor,signed_at)

    def criteria(self,content=None):
        r=register_reference(self.actor,self.case.pk,'criteria:'+str(self.case.revision),'schema:psl/hypercare-criteria/v1',content or CRITERIA,self.e['policy_decision'].pk)
        return activate(self.actor,self.case,'D11.hypercare_criteria_ref',r.ref,self.e['policy_decision'])

    def storage(self,closure=True):
        rules={'template_ids':[self.t.pk],'repository':'internal-versioned','retention_days':30}
        if closure:rules['closure_inventory']={'required_kinds':['technical_document','test_results','project_artifact'],'archive_mode':'immutable_local_manifest'}
        return artifact(self.actor,self.case,'D11.template_storage_retention_rules','schema:psl/document-storage/v2' if closure else 'schema:psl/document-storage/v1',rules,self.e['policy_decision'])

    def observations(self,errors=0,availability=100,confirmed=True):
        for owner,metrics in [('engineering',{'errors':{'value':errors,'unit':'count'}}),('infrastructure',{'availability':{'value':availability,'unit':'percent'}})]:
            self.source('hypercare_'+owner,{'observed_at':timezone.now().isoformat(),'confirmed':confirmed,'metrics':metrics})

    def archive(self):
        self.storage();inventory={k:self.evidence(k).pk for k in ['technical_document','test_results','project_artifact']}
        from apps.core.models import Evidence
        self.source('technical_finalization',evidence=Evidence.objects.get(pk=inventory['technical_document']))
        return archive_artifacts(self.actor,self.case.pk,self.d.pk,inventory,self.e['requirements'].pk,'Immutable exact project archive',rev(self.case))

    def closing(self):
        self.accepted();self.criteria();self.observations()
        evaluate_hypercare(self.actor,self.case.pk,self.d.pk,self.e['requirements'].pk,'Source criteria evaluation',rev(self.case));self.archive()
        data={k:self.evidence(k).pk for k in ['support_document','escalation_document']}
        v=draft_delivery_document(self.actor,self.case.pk,self.d.pk,'handover',self.t.pk,data,rev(self.case));receipt=self.publish(v)
        acknowledge_handover(self.actor,self.case.pk,self.d.pk,receipt.pk,'received',self.e['requirements'].pk,'Support received exact documents',rev(self.case))
        milestone=complete_milestone(self.actor,self.case.pk,'Final delivery',self.e['completion'].pk,rev(self.case));assert run_once()
        confirm_finance(self.actor,self.case.pk,self.d.pk,[milestone.pk],True,self.e['completion'].pk,'Finance confirms full inventory and actual receipts',rev(self.case))
        meeting=record_meeting(self.actor,self.case.pk,'RETRO','retrospective',timezone.now(),'Lessons learned','Grounded delivery retrospective',[self.actor.pk],[],self.e['requirements'].pk,rev(self.case))
        report=self.evidence('closure_report','PM performance summary, risks and resolutions')
        return {'retrospective_id':meeting.pk,'report_evidence_id':report.pk}


class DeliveryTests(DeliveryFixture,TestCase):
    @classmethod
    def setUpTestData(cls):
        f=DeliveryFixture();f.setup_delivery()
        for key,value in vars(f).items():setattr(cls,key,value)

    def test_connected_planning_release_hypercare_archive_handover_finance_head_closure(self):
        data=self.closing();v=draft_delivery_document(self.actor,self.case.pk,self.d.pk,'closure',self.t.pk,data,rev(self.case))
        with self.assertRaises(ValidationError):finalize_closure(self.actor,self.case.pk,self.d.pk,rev(self.case))
        decide_closure(self.actor,self.case.pk,v.pk,'approve',self.e['requirements'].pk,'Head of PMO exact closure approval',rev(self.case))
        closed=finalize_closure(self.actor,self.case.pk,self.d.pk,rev(self.case))
        self.assertFalse(closed.snapshot['debt_waived']);self.assertFalse(closed.snapshot['deployment_authorized'])
        self.assertEqual(connection.vendor,'postgresql');self.assertEqual(PublicationReceipt.objects.count(),2)
        investigation=investigate_delivery(self.actor,self.case.pk,self.d.pk,rev(self.case)).result
        self.assertEqual(investigation['recorded_closure_id'],closed.pk)
        self.assertIn(data['report_evidence_id'],investigation['source_evidence_ids'])
        self.assertIn(self.e['policy_decision'].pk,investigation['source_evidence_ids'])
        self.assertFalse(investigation['checks']['closure']['findings'])
        with self.assertRaises(ValidationError):finalize_closure(self.actor,self.case.pk,self.d.pk,rev(self.case))
        with self.assertRaisesMessage(ValidationError,'archived'):record_progress(self.actor,self.case.pk,self.d.pk,'progress',self.e['plan'].pk,'After archive',rev(self.case))

    def test_missing_hypercare_policy_holds_only_evaluation_not_actual_release_or_archive(self):
        o=self.accepted();self.assertEqual(o.kind,'release_outcome')
        with self.assertRaises(PolicyHold):evaluate_hypercare(self.actor,self.case.pk,self.d.pk,self.e['plan'].pk,'Needs owner criteria',rev(self.case))
        a=self.archive();self.assertEqual(a.snapshot['repository'],'internal-versioned')
        self.assertFalse(a.snapshot['physical_purge_performed'])

    def test_unknown_ui_and_conditional_signoffs_do_not_become_false(self):
        for kind in PLANNING:self.source(kind,{'requires_ui':None,'client_signoff_required':None} if kind=='ui_applicability' else {})
        with self.assertRaisesMessage(ValidationError,'remain unknown'):planning_inputs(self.d)
        self.source('ui_applicability',{'requires_ui':True,'client_signoff_required':True})
        with self.assertRaisesMessage(ValidationError,'ui_target'):planning_inputs(self.d)
        from .ui_artifact_helpers import target_payload,approval_payload
        artifact=self.evidence('ui_design_artifact','Synthetic current UI design v2')
        target=target_payload(artifact)
        self.source('ui_target',target,self.evidence('ui_target_statement'))
        with self.assertRaisesMessage(ValidationError,'ui_design'):planning_inputs(self.d)
        self.source('ui_design',approval_payload(target),self.evidence('ui_owner_signoff','Design Lead receipt'))
        with self.assertRaisesMessage(ValidationError,'ui_client'):planning_inputs(self.d)
        self.source('ui_client',approval_payload(target,'client-4','Client'),self.evidence('ui_owner_signoff','Client receipt'))
        self.assertIn('ui_client',planning_inputs(self.d)['sources'])

    def test_missing_qa_uat_go_and_glpi_cannot_be_skipped_or_cross_request_reused(self):
        self.plan()
        with self.assertRaisesMessage(ValidationError,'qa_exit'):record_release_request(self.actor,self.case.pk,self.d.pk,'GLPI-1',self.e['plan'].pk,'Missing gates',rev(self.case))
        self.gates(UPSTREAM_GATES)
        record_release_request(self.actor,self.case.pk,self.d.pk,'GLPI-1',self.e['plan'].pk,'Current upstream evidence',rev(self.case))
        self.gates(GLPI_GATES,'OTHER-REQUEST')
        with self.assertRaisesMessage(ValidationError,'exact deployment request'):prepare_readiness(self.actor,self.case.pk,self.d.pk,rev(self.case))

    def test_actual_release_capture_without_readiness_preserves_exception_no_backdating(self):
        o=capture_release(self.actor,self.case.pk,self.d.pk,None,timezone.now(),'Actual-unready',self.e['completion'].pk,'Truthful external outcome',rev(self.case))
        self.assertFalse(o.snapshot['readiness_preceded'])
        with self.assertRaisesMessage(ValidationError,'cannot be backdated'):valid_release(self.d)
        with self.assertRaisesMessage(ValidationError,'later readiness'):prepare_readiness(self.actor,self.case.pk,self.d.pk,rev(self.case))

    def test_later_readiness_record_does_not_authorize_an_earlier_claimed_release(self):
        r=self.ready();capture_release(self.actor,self.case.pk,self.d.pk,r.pk,timezone.now()-timedelta(days=1),'Earlier',self.e['completion'].pk,'Earlier owner event',rev(self.case))
        with self.assertRaises(ValidationError):valid_release(self.d)

    def test_hypercare_unknown_negative_metrics_units_and_period_are_explicit(self):
        self.accepted();self.criteria(dict(CRITERIA,minimum_hours=24));self.observations(errors=None)
        r=evaluate_hypercare(self.actor,self.case.pk,self.d.pk,self.e['plan'].pk,'Unknown observations',rev(self.case))
        self.assertIsNone(r.snapshot['qualified']);self.assertTrue(any('period' in x for x in r.snapshot['findings']))
        self.criteria();self.observations(errors=2,availability=98)
        self.assertFalse(hypercare_inputs(self.d)['qualified'])
        self.observations();self.assertTrue(hypercare_inputs(self.d)['qualified'])
        self.source('hypercare_engineering',{'observed_at':timezone.now().isoformat(),'confirmed':True,'metrics':{'errors':{'value':0,'unit':'percent'}}})
        self.assertFalse(hypercare_inputs(self.d)['qualified'])

    def test_invalid_policies_reject_waivers_missing_archive_kinds_and_infinite_metrics(self):
        for change in [{'minimum_hours':-1},{'confirmation_owners':[]},{'financial_controls':'waived'},
            {'metrics':[dict(CRITERIA['metrics'][0],threshold=float('inf'))]}]:
            with self.assertRaises(ValidationError):self.criteria(dict(CRITERIA,**change))
        with self.assertRaises(ValidationError):artifact(self.actor,self.case,'D11.template_storage_retention_rules','schema:psl/document-storage/v2',
            {'template_ids':[self.t.pk],'repository':'internal-versioned','retention_days':30,'closure_inventory':{'required_kinds':['document','test_results','project_artifact'],'archive_mode':'immutable_local_manifest'}},self.e['policy_decision'])

    def test_revoked_future_expired_policy_preserves_capture_and_holds_qualification(self):
        self.accepted();config=self.criteria();self.observations()
        transition(self.actor,config.pk,'revoked')
        with self.assertRaises(PolicyHold):hypercare_inputs(self.d)
        for start,end in [(timezone.now()+timedelta(days=1),None),(timezone.now()-timedelta(days=2),timezone.now()-timedelta(days=1))]:
            env=envelope(self.case,config.component,config.envelope['value'],self.e['policy_decision']);env.update(effective_from=start.isoformat(),effective_until=end.isoformat() if end else None)
            c=save_draft(self.actor,self.case.pk,env);transition(self.actor,c.pk,'validated');transition(self.actor,c.pk,'active')
            with self.assertRaises(PolicyHold):hypercare_inputs(self.d)
        self.source('hypercare_engineering',{'observed_at':timezone.now().isoformat(),'confirmed':None,'metrics':{}})

    def test_source_change_or_verifier_revocation_holds_queued_exact_go_live(self):
        self.release();data={k:self.evidence(kind).pk for k,kind in [('checklist','deployment_checklist'),('incident_reporting','incident_reporting'),('rollback','rollback_plan')]}
        v=draft_delivery_document(self.actor,self.case.pk,self.d.pk,'go_live',self.t.pk,data,rev(self.case))
        request_review(self.actor,self.case.pk,v.pk,rev(self.case));review_version(self.actor,self.case.pk,v.pk,'approve','Exact outward artifact',rev(self.case));reserve_publication(self.actor,self.case.pk,v.pk,rev(self.case))
        Grant.objects.filter(case=self.case,user=self.actor,action='delivery.verify').update(active=False)
        self.assertTrue(run_publication_once());self.assertEqual(PublicationJob.objects.get().status,'held');self.assertFalse(PublicationReceipt.objects.exists())

    def test_engineering_finalization_exact_inventory_and_changed_policy_require_new_archive(self):
        self.accepted()
        with self.assertRaisesMessage(ValidationError,'closure_inventory'):archive_artifacts(self.actor,self.case.pk,self.d.pk,{},self.e['plan'].pk,'Missing rule',rev(self.case))
        a=self.archive();self.assertEqual(len(a.snapshot['inventory']),3)
        self.storage()
        from apps.pmo.delivery_closure import current_archive
        with self.assertRaisesMessage(ValidationError,'changed'):current_archive(self.d)

    def test_handover_actual_recipient_gap_and_new_finance_milestone_hold_closure(self):
        data=self.closing();receipt=PublicationReceipt.objects.filter(publication__version__deliverydocumentbinding__purpose='handover').get()
        acknowledge_handover(self.actor,self.case.pk,self.d.pk,receipt.pk,'gaps',self.e['plan'].pk,'Missing escalation contact',rev(self.case))
        with self.assertRaisesMessage(ValidationError,'gap resolution'):closure_inputs(self.d,data)
        acknowledge_handover(self.actor,self.case.pk,self.d.pk,receipt.pk,'received',self.e['plan'].pk,'Gap resolved against exact sources',rev(self.case))
        complete_milestone(self.actor,self.case.pk,'Additional milestone',self.e['completion'].pk,rev(self.case))
        with self.assertRaisesMessage(ValidationError,'notification receipt missing'):closure_inputs(self.d,data)

    def test_unknown_inventory_not_empty_and_admin_foreign_stale_and_postgres_immutable(self):
        with self.assertRaises(ValidationError):confirm_finance(self.actor,self.case.pk,self.d.pk,[],False,self.e['plan'].pk,'Unknown inventory',rev(self.case))
        with self.assertRaises(ValidationError):capture_source(self.actor,self.case.pk,self.d.pk,'registration','ref',self.e['plan'].pk,{},rev(self.case)-1)
        admin=get_user_model().objects.create_superuser('delivery-admin','admin@example.test','test-only')
        with self.assertRaises(PermissionDenied):decide_planning(admin,self.case.pk,self.d.pk,'approve',self.e['plan'].pk,'Admin flag',rev(self.case))
        with self.assertRaises(DatabaseError),transaction.atomic():self.d.__class__.objects.filter(pk=self.d.pk).update(baseline={})
        other,c=setup_case(username='other-delivery');self.client.force_login(other);self.assertEqual(self.client.get(f'/cases/{self.case.pk}/delivery/').status_code,404)

    def test_operational_source_verification_cannot_use_synthetic_adapter(self):
        s=self.source('registration',verify=False)
        self.case.synthetic=False;self.case.save(update_fields=['synthetic'])
        with self.assertRaisesMessage(ValidationError,'authoritative verification'):verify_source(self.actor,self.case.pk,s.pk,rev(self.case))

    def test_staff_ui_agent_policy_draft_and_cited_unknowns(self):
        self.client.force_login(self.actor);url=f'/cases/{self.case.pk}/delivery/'
        self.assertContains(self.client.get(url),'Delivery, release evidence and project closure')
        self.assertEqual(self.client.post(url,{'action':'investigate','revision':rev(self.case),'dossier':self.d.pk}).status_code,302)
        run=investigate_delivery(self.actor,self.case.pk,self.d.pk,rev(self.case));self.assertFalse(run.result['approval_granted'])
        self.assertIn(self.e['requirements'].pk,run.result['source_evidence_ids']);self.assertTrue(run.result['checks']['planning']['findings'])
        cfg=draft_standard_policy(self.actor,self.case.pk,'D11.hypercare_criteria_ref',CRITERIA,self.e['policy_decision'].pk,timezone.now());transition(self.actor,cfg.pk,'validated');transition(self.actor,cfg.pk,'active')

    def test_shared_reporting_freshness_binds_delivery_sources_signals_and_current_policy(self):
        from adapters.pmo_reporting import LocalPMOReportingAdapter
        adapter=LocalPMOReportingAdapter();now=timezone.now()
        before=adapter.read(self.case,now-timedelta(days=1),now+timedelta(days=1),now)['manifest']
        self.source('registration')
        after=adapter.read(self.case,now-timedelta(days=1),now+timedelta(days=1),now)['manifest']
        self.assertNotEqual(before,after);self.assertTrue(after['delivery_history']['sources'])

    def test_complete_planning_exit_does_not_require_client_signature(self):
        a,c=setup_case(username='unsigned-planning');e=prepared(a,c)
        candidate=register_candidate(a,c.pk,'unsigned-candidate',e['requirements'].pk,rev(c))
        d=open_dossier(a,c.pk,candidate.pk,e['plan'].pk,'Complete planning before signing',rev(c))
        for kind in PLANNING:
            payload={'requires_ui':False,'client_signoff_required':False} if kind=='ui_applicability' else {}
            source=capture_source(a,c.pk,d.pk,kind,'source:'+kind,e['requirements'].pk,payload,rev(c));verify_source(a,c.pk,source.pk,rev(c))
        result=decide_planning(a,c.pk,d.pk,'approve',e['plan'].pk,'Approved unsigned Planning exit',rev(c))
        self.assertEqual(result.data['verdict'],'approve')
        from apps.pmo.models import Baseline
        self.assertIsNone(Baseline.objects.get(case=c).signed_id)

    def test_bad_adapter_binding_future_observation_and_wrong_recipient_are_rejected(self):
        class WrongOwner(SyntheticDeliverySourceAdapter):
            def read(self,s):return dict(super().read(s),owner='PM')
        s=self.source('registration',verify=False)
        with self.assertRaises(ValidationError):verify_source(self.actor,self.case.pk,s.pk,rev(self.case),WrongOwner())
        with self.assertRaises(ValidationError):self.source('hypercare_engineering',{'observed_at':(timezone.now()+timedelta(days=1)).isoformat(),'confirmed':True,'metrics':{}})
        self.accepted();self.archive()
        data={k:self.evidence(k).pk for k in ['support_document','escalation_document']}
        receipt=self.publish(draft_delivery_document(self.actor,self.case.pk,self.d.pk,'handover',self.t.pk,data,rev(self.case)))
        other=get_user_model().objects.create_user('wrong-support-recipient')
        Grant.objects.create(case=self.case,user=other,action='delivery.support_receive')
        with self.assertRaisesMessage(ValidationError,'actual Support'):acknowledge_handover(other,self.case.pk,self.d.pk,receipt.pk,'received',self.e['plan'].pk,'Not my receipt',rev(self.case))


class DeliveryConcurrencyTests(DeliveryFixture,TransactionTestCase):
    def setUp(self):self.setup_delivery()
    def test_two_real_connections_record_one_actual_outcome(self):
        ready=self.ready();expected=rev(self.case);instant=timezone.now()
        def work():
            close_old_connections()
            try:
                capture_release(get_user_model().objects.get(pk=self.actor.pk),self.case.pk,self.d.pk,ready.pk,instant,'Actual once',self.e['completion'].pk,'Recorded actual release',expected);return 'recorded'
            except ValidationError:return 'stale'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:work(),range(2)))
        self.assertCountEqual(results,['recorded','stale']);self.assertEqual(DeliveryRecord.objects.filter(kind='release_outcome').count(),1)

    def test_separate_processes_resume_hypercare_scan_without_duplicate_or_effect(self):
        import subprocess,sys,os
        from django.conf import settings
        from apps.pmo.models import DeliverySignal,DeliveryScanCursor
        capture_release(self.actor,self.case.pk,self.d.pk,None,timezone.now(),'Actual outcome',self.e['completion'].pk,'Truthful external release',rev(self.case))
        for _ in range(2):
            result=subprocess.run([sys.executable,str(settings.BASE_DIR/'manage.py'),'work_delivery_obligations','--limit','1'],
                capture_output=True,text=True,cwd=settings.BASE_DIR,env=dict(os.environ,PGDATABASE=connection.settings_dict['NAME']),timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
        signal=DeliverySignal.objects.get();self.assertEqual(signal.kind,'hypercare_policy_missing')
        self.assertEqual(DeliveryScanCursor.objects.get().last_dossier_id,self.d.pk);self.assertFalse(PublicationReceipt.objects.exists())
        with self.assertRaises(DatabaseError),transaction.atomic():DeliverySignal.objects.filter(pk=signal.pk).update(snapshot={})

    def test_two_connections_generate_one_due_signal_and_never_close(self):
        from apps.pmo.delivery_obligations import scan_delivery
        from apps.pmo.models import DeliverySignal
        capture_release(self.actor,self.case.pk,self.d.pk,None,timezone.now(),'Actual',self.e['completion'].pk,'Actual owner outcome',rev(self.case));self.criteria()
        def work():
            close_old_connections()
            try:return len(scan_delivery(get_user_model().objects.get(pk=self.actor.pk),self.case.pk,self.d.pk))
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:counts=list(pool.map(lambda _:work(),range(2)))
        self.assertEqual(sum(counts),1);self.assertEqual(DeliverySignal.objects.get().kind,'hypercare_due')
        self.assertFalse(DeliveryRecord.objects.filter(kind='closure').exists())
