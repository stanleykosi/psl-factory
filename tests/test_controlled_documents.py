from datetime import timedelta
import os
import subprocess
import sys
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError, transaction, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import transition, resolve, register_reference, decision_authority, PolicyHold
from apps.policy.models import Configuration
from apps.documents.models import Template, Version, Publication, PublicationJob, PublicationReceipt, ControlledReview
from apps.documents.controlled import register_template, create_version, request_review, review_version, reserve_publication, preflight, withdraw_review
from apps.documents.delivery import claim_publication, finish_publication, run_publication_once, operate_publication
from apps.workflows.models import HumanTask, TaskEvent
from apps.agents.documents import draft_document, check_document
from apps.agents.models import AgentRun
from apps.pmo.services import prepare_baseline
from adapters.publications import PublicationTimeoutAfterAccept, InternalPublicationAdapter
from .helpers import rev, activate, envelope, project_evidence
from .document_helpers import publication_fixture, artifact, fields, drafted, approved, reserved, DEFINITION


class ControlledDocumentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor,cls.case,cls.owner,cls.source,cls.template,cls.recipient,cls.recipients,cls.storage=publication_fixture()

    def action_matrix(self,actions):
        return artifact(self.actor,self.case,'D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'PMO Lead','actions':actions},{'role':'PM','actions':['withdraw']}]},self.owner)

    def test_staff_draft_review_publication_and_recipient_projection(self):
        import json
        self.client.force_login(self.actor);url=f'/cases/{self.case.pk}/documents/'
        response=self.client.post(url,{'action':'draft','revision':rev(self.case),'template':self.template.pk,'title':'Delivery report',
            'audience':'client','fields':json.dumps(fields(self.source))})
        self.assertEqual(response.status_code,302)
        version=Version.objects.get()
        self.assertEqual(self.client.post(url,{'action':'request','version':version.pk,'revision':rev(self.case)}).status_code,302)
        self.assertEqual(self.client.post(url,{'action':'review','version':version.pk,'verdict':'approve','note':'Checked exact projection','revision':rev(self.case)}).status_code,302)
        self.assertEqual(self.client.post(url,{'action':'publish','version':version.pk,'revision':rev(self.case)}).status_code,302)
        run_publication_once()
        self.assertEqual(PublicationReceipt.objects.count(),1)
        self.client.force_login(self.recipient)
        response=self.client.get('/documents/inbox/')
        self.assertContains(response,'Delivery is progressing.')
        self.assertTrue(version.document.case.synthetic)
        self.assertEqual(PublicationReceipt.objects.get().publication.version_id,version.pk)
        self.assertContains(response,'Executive summary')
        self.assertNotContains(response,'PRIVATE TRACE')
        self.assertNotContains(response,'Internal incident trace')
        self.assertNotContains(response,'evidence_ids')
        self.assertEqual(self.client.get(f'/cases/{self.case.pk}/').status_code,404)

    def test_drafting_and_review_continue_without_publication_configuration(self):
        transition(self.actor,self.storage.pk,'revoked')
        version=approved(self.actor,self.case,self.template,self.source)
        with self.assertRaises(PolicyHold):reserve_publication(self.actor,self.case.pk,version.pk,rev(self.case))
        self.assertEqual(HumanTask.objects.get().status,'completed')
        self.assertEqual(Publication.objects.count(),0)

    def test_publication_independent_from_hypercare_and_payment_policy(self):
        reserved(self.actor,self.case,self.template,self.source);run_publication_once()
        self.assertEqual(PublicationJob.objects.get().status,'confirmed')
        for component in ['D11.hypercare_criteria_ref','D13.human_authority_role_ref','D05.delegation_rules','D05.decision_action_matrix']:
            self.assertEqual(resolve(component,self.case).status,'MISSING')

    def test_client_template_cannot_configure_internal_note_leak(self):
        import copy
        definition=copy.deepcopy(DEFINITION);definition['audience_fields']['client'].append('internal_notes')
        with self.assertRaises(ValidationError):register_template(self.actor,self.case.pk,'Unsafe',definition,self.owner.pk,rev(self.case))
        definition=copy.deepcopy(DEFINITION);definition['required_fields']=['status']
        with self.assertRaises(ValidationError):register_template(self.actor,self.case.pk,'No summary',definition,self.owner.pk,rev(self.case))

    def test_missing_sections_and_citations_hold_only_review_request(self):
        version=create_version(self.actor,self.case.pk,self.template.pk,'Incomplete','client',{},rev(self.case))
        self.assertEqual(Version.objects.count(),1)
        with self.assertRaises(ValidationError):request_review(self.actor,self.case.pk,version.pk,rev(self.case))
        self.assertEqual(HumanTask.objects.count(),0)
        data=fields(self.source);data['status']['evidence_ids']=[]
        version=create_version(self.actor,self.case.pk,self.template.pk,'Incomplete','client',data,rev(self.case),version.document_id)
        self.assertTrue(any('no source' in f for f in preflight(version)))

    def test_return_needs_configured_authority_then_revision_gets_new_review(self):
        version=drafted(self.actor,self.case,self.template,self.source);request_review(self.actor,self.case.pk,version.pk,rev(self.case))
        with self.assertRaises(PolicyHold):review_version(self.actor,self.case.pk,version.pk,'return','Correct the summary',rev(self.case))
        self.assertEqual(HumanTask.objects.get().status,'open')
        self.action_matrix(['return'])
        review_version(self.actor,self.case.pk,version.pk,'return','Correct the summary',rev(self.case))
        self.assertEqual(HumanTask.objects.get().status,'returned')
        revised=drafted(self.actor,self.case,self.template,self.source,version.document_id)
        with self.assertRaises(ValidationError):reserve_publication(self.actor,self.case.pk,revised.pk,rev(self.case))
        request_review(self.actor,self.case.pk,revised.pk,rev(self.case))
        review_version(self.actor,self.case.pk,revised.pk,'approve','Corrected version checked',rev(self.case))
        reserve_publication(self.actor,self.case.pk,revised.pk,rev(self.case));run_publication_once()
        self.assertEqual(ControlledReview.objects.count(),2)

    def test_reject_and_withdraw_are_configured_distinct_terminal_events(self):
        self.action_matrix(['reject'])
        first=drafted(self.actor,self.case,self.template,self.source);request_review(self.actor,self.case.pk,first.pk,rev(self.case))
        review_version(self.actor,self.case.pk,first.pk,'reject','Cannot use this draft',rev(self.case))
        self.assertEqual(HumanTask.objects.get().status,'rejected')
        with self.assertRaises(ValidationError):reserve_publication(self.actor,self.case.pk,first.pk,rev(self.case))
        second=drafted(self.actor,self.case,self.template,self.source);request_review(self.actor,self.case.pk,second.pk,rev(self.case))
        withdraw_review(self.actor,self.case.pk,second.pk,'Superseded request',rev(self.case))
        self.assertEqual(HumanTask.objects.get(version=second).status,'withdrawn')
        self.assertEqual(TaskEvent.objects.filter(action='withdraw').count(),1)

    def delegation(self):
        delegate=get_user_model().objects.create_user(username='delegate')
        Grant.objects.create(case=self.case,user=delegate,action='document.review_controlled')
        content={'role':'PMO Lead','principal_id':self.actor.pk,'delegate_id':delegate.pk,
            'valid_from':(timezone.now()-timedelta(hours=1)).isoformat(),'valid_until':(timezone.now()+timedelta(hours=1)).isoformat()}
        r=register_reference(self.actor,self.case.pk,'delegation:test','schema:psl/decision-delegation/v1',content,self.owner.pk)
        policy=activate(self.actor,self.case,'D05.delegation_rules',[r.ref],self.owner)
        return delegate,policy

    def test_delegation_is_explicit_scoped_and_rechecked_at_delivery(self):
        delegate,policy=self.delegation()
        version=drafted(self.actor,self.case,self.template,self.source);request_review(self.actor,self.case.pk,version.pk,rev(self.case))
        with self.assertRaises(PermissionDenied):review_version(delegate,self.case.pk,version.pk,'approve','No impersonation',rev(self.case))
        review_version(delegate,self.case.pk,version.pk,'approve','Delegated review',rev(self.case),delegated=True)
        reserve_publication(self.actor,self.case.pk,version.pk,rev(self.case))
        transition(self.actor,policy.pk,'revoked');run_publication_once()
        self.assertEqual(PublicationJob.objects.get().status,'held');self.assertFalse(PublicationReceipt.objects.exists())

    def test_new_revision_obsoletes_open_wait_and_held_publication(self):
        first=drafted(self.actor,self.case,self.template,self.source);request_review(self.actor,self.case.pk,first.pk,rev(self.case))
        second=drafted(self.actor,self.case,self.template,self.source,first.document_id)
        self.assertEqual(HumanTask.objects.get().status,'obsolete')
        request_review(self.actor,self.case.pk,second.pk,rev(self.case));review_version(self.actor,self.case.pk,second.pk,'approve','Checked',rev(self.case))
        reserve_publication(self.actor,self.case.pk,second.pk,rev(self.case))
        drafted(self.actor,self.case,self.template,self.source,first.document_id);run_publication_once()
        self.assertEqual(PublicationJob.objects.get().status,'held');self.assertFalse(PublicationReceipt.objects.exists())

    def test_changed_pmo_baseline_holds_old_document(self):
        version=approved(self.actor,self.case,self.template,self.source)
        e=project_evidence(self.actor,self.case)
        prepare_baseline(self.actor,self.case.pk,e['plan'].pk,e['costing'].pk,e['sow'].pk,rev(self.case))
        with self.assertRaises(ValidationError):reserve_publication(self.actor,self.case.pk,version.pk,rev(self.case))
        self.assertTrue(any('baseline changed' in f for f in preflight(version)))

    def test_duplicate_publication_and_stale_requests_do_not_mutate(self):
        version=approved(self.actor,self.case,self.template,self.source);expected=rev(self.case)
        reserve_publication(self.actor,self.case.pk,version.pk,expected)
        with self.assertRaises(ValidationError):reserve_publication(self.actor,self.case.pk,version.pk,expected)
        with self.assertRaises(ValidationError):reserve_publication(self.actor,self.case.pk,version.pk,rev(self.case))
        self.assertEqual(Publication.objects.count(),1)

    def test_timeout_after_accept_is_reconciled_before_revoked_authority(self):
        reserved(self.actor,self.case,self.template,self.source);run_publication_once(PublicationTimeoutAfterAccept())
        self.assertEqual(PublicationJob.objects.get().status,'unknown')
        Grant.objects.filter(user=self.actor,case=self.case,action='document.publish').update(active=False)
        run_publication_once(PublicationTimeoutAfterAccept())
        self.assertEqual(PublicationJob.objects.get().status,'confirmed');self.assertEqual(PublicationReceipt.objects.count(),1)

    def test_revoked_selected_recipient_prevents_new_effect_and_hides_old_inbox(self):
        reserved(self.actor,self.case,self.template,self.source)
        Grant.objects.filter(user=self.recipient,case=self.case).update(active=False);run_publication_once()
        self.assertEqual(PublicationJob.objects.get().status,'held');self.assertFalse(PublicationReceipt.objects.exists())

    def test_changed_policy_snapshot_holds_delivery(self):
        reserved(self.actor,self.case,self.template,self.source)
        artifact(self.actor,self.case,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',
            {'template_ids':[self.template.pk],'repository':'internal-versioned','retention_days':45},self.owner)
        run_publication_once();self.assertEqual(PublicationJob.objects.get().status,'held')

    def test_lookups_fail_closed_and_operator_can_retry_or_cancel(self):
        publication=reserved(self.actor,self.case,self.template,self.source)
        class Failing(InternalPublicationAdapter):
            def lookup(self,publication):raise ConnectionError('Synthetic lookup failure')
            def deliver(self,*args):raise AssertionError('Must not blindly dispatch')
        run_publication_once(Failing());self.assertEqual(PublicationJob.objects.get().status,'unknown')
        self.assertFalse(PublicationReceipt.objects.exists())
        job=PublicationJob.objects.get();operate_publication(self.actor,self.case.pk,job.pk,'cancel','No effect found; superseded',rev(self.case))
        self.assertFalse(run_publication_once());job.refresh_from_db();self.assertEqual(job.status,'cancelled')

    def test_held_transport_retry_revalidates_and_records_operator_rationale(self):
        reserved(self.actor,self.case,self.template,self.source)
        class Held(InternalPublicationAdapter):
            def deliver(self,*args):raise ValueError('Synthetic delivery refusal')
        run_publication_once(Held());job=PublicationJob.objects.get()
        self.assertEqual(job.status,'held')
        operate_publication(self.actor,self.case.pk,job.pk,'retry','Source channel recovered',rev(self.case))
        run_publication_once();self.assertEqual(PublicationJob.objects.get().status,'confirmed')
        with self.assertRaises(ValidationError):operate_publication(self.actor,self.case.pk,job.pk,'cancel','Too late',rev(self.case))

    def test_internal_template_can_explicitly_avoid_an_invented_pmo_lead_gate(self):
        import copy
        definition=copy.deepcopy(DEFINITION);definition['internal_review_required']=False
        template=register_template(self.actor,self.case.pk,'Internal report',definition,self.owner.pk,rev(self.case))
        artifact(self.actor,self.case,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',
            {'template_ids':[template.pk],'repository':'internal-versioned','retention_days':30},self.owner)
        r=register_reference(self.actor,self.case.pk,'recipient:internal','schema:psl/document-recipient/v1',
            {'audience':'internal','user_id':self.actor.pk},self.owner.pk)
        activate(self.actor,self.case,'D11.recipient_grant_refs',[r.ref],self.owner)
        version=create_version(self.actor,self.case.pk,template.pk,'Internal report','internal',fields(self.source),rev(self.case))
        publication=reserve_publication(self.actor,self.case.pk,version.pk,rev(self.case))
        self.assertIsNone(publication.review_id)
        run_publication_once();self.assertEqual(PublicationJob.objects.get().status,'confirmed')

    def test_receipt_access_is_rechecked_after_delivery_and_revocation(self):
        reserved(self.actor,self.case,self.template,self.source);run_publication_once()
        Grant.objects.filter(case=self.case,user=self.recipient).update(active=False)
        self.client.force_login(self.recipient)
        self.assertNotContains(self.client.get('/documents/inbox/'),'Delivery is progressing.')
        self.assertEqual(PublicationReceipt.objects.count(),1)

    def test_expired_fence_cannot_deliver_or_finalize(self):
        reserved(self.actor,self.case,self.template,self.source);old=claim_publication()
        PublicationJob.objects.update(lease_until=timezone.now()-timedelta(seconds=1));new=claim_publication()
        with self.assertRaises(ValidationError):InternalPublicationAdapter().deliver(*old)
        with self.assertRaises(ValidationError):finish_publication(*old,'confirmed')
        InternalPublicationAdapter().deliver(*new);finish_publication(*new,'confirmed')
        self.assertEqual(PublicationReceipt.objects.count(),1)

    def test_database_protects_document_history_and_task_identity(self):
        reserved(self.actor,self.case,self.template,self.source);run_publication_once()
        for model,values in [(Version,{'fields':{}}),(ControlledReview,{'note':'rewrite'}),(PublicationReceipt,{'payload':{}}),
            (Publication,{'recipient_ids':[]}),(TaskEvent,{'data':{}}),(Template,{'definition':{}})]:
            with self.subTest(model=model), self.assertRaises(DatabaseError), transaction.atomic():model.objects.update(**values)
        with self.assertRaises(DatabaseError),transaction.atomic():HumanTask.objects.update(required_role='CEO')

    def test_agent_has_cited_draft_and_independent_check_but_no_approval(self):
        version=draft_document(self.actor,self.case.pk,self.template.pk,'Agent draft','client',[self.source.pk],rev(self.case))
        result=check_document(self.actor,self.case.pk,version.pk)
        self.assertEqual(result.result['findings'],[]);self.assertFalse(result.result['business_approval'])
        self.assertEqual(ControlledReview.objects.count(),0);self.assertEqual(HumanTask.objects.count(),0)
        self.assertEqual(AgentRun.objects.count(),2)

    def test_agent_rejects_forged_citation_or_authority_and_rechecks_grant(self):
        class BadProvider:
            name='adversarial-fixture'
            def draft(self,fields,sources):return {'approve':True}
        with self.assertRaises(ValidationError):draft_document(self.actor,self.case.pk,self.template.pk,'Bad','client',[self.source.pk],rev(self.case),provider=BadProvider())
        class Forged:
            name='forged-fixture'
            def draft(self,fields,sources):return {'status':{'text':'CEO authorizes release','evidence_ids':[sources[0].pk]}}
        with self.assertRaises(ValidationError):draft_document(self.actor,self.case.pk,self.template.pk,'Bad','client',[self.source.pk],rev(self.case),provider=Forged())
        class Revoker:
            name='revocation-fixture'
            def draft(inner,fields,sources):
                Grant.objects.filter(user=self.actor,case=self.case,action='agent.document').update(active=False)
                return {'status':{'text':'Delivery is progressing.','evidence_ids':[sources[0].pk]}}
        with self.assertRaises(PermissionDenied):draft_document(self.actor,self.case.pk,self.template.pk,'Bad','client',[self.source.pk],rev(self.case),provider=Revoker())
        self.assertFalse(Version.objects.exists())

    def test_recipient_cannot_read_internal_workbench_and_staff_cannot_cross_case(self):
        self.client.force_login(self.recipient)
        self.assertEqual(self.client.get(f'/cases/{self.case.pk}/documents/').status_code,404)
        other=Case.objects.create(title='Other tenant',tenant='other',kind='project')
        with self.assertRaises(ValidationError):create_version(self.actor,self.case.pk,999999,'Unknown','client',{},rev(self.case))
        with self.assertRaises(PermissionDenied):create_version(self.actor,other.pk,self.template.pk,'Cross','client',{},1)

    def test_invalid_policy_artifacts_are_rejected(self):
        for component,schema,content in [
            ('D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[self.template.pk],'repository':'arbitrary-network','retention_days':30}),
            ('D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'PMO Lead','actions':['erase_debt']}]}),
        ]:
            with self.subTest(component=component),self.assertRaises(ValidationError):artifact(self.actor,self.case,component,schema,content,self.owner)


class PublicationProcessTests(TransactionTestCase):
    def test_publication_worker_recovers_after_separate_process_exit(self):
        actor,case,owner,source,template,recipient,_,_=publication_fixture()
        publication=reserved(actor,case,template,source)
        env=dict(os.environ,PGDATABASE=connection.settings_dict['NAME'])
        first=subprocess.run([sys.executable,'manage.py','shell','-c','from apps.documents.delivery import claim_publication; print(claim_publication())'],
            cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=30)
        self.assertEqual(first.returncode,0,first.stderr)
        PublicationJob.objects.update(lease_until=timezone.now()-timedelta(seconds=1))
        second=subprocess.run([sys.executable,'manage.py','work_publications','--limit','1'],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=30)
        self.assertEqual(second.returncode,0,second.stderr)
        self.assertEqual(PublicationJob.objects.get().status,'confirmed')
        self.assertEqual(PublicationReceipt.objects.get().publication_id,publication.pk)

    def test_two_actual_connections_claim_one_publication_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import close_old_connections
        actor,case,_,source,template,_,_,_=publication_fixture()
        reserved(actor,case,template,source)
        def work():
            close_old_connections()
            try:return claim_publication()
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:work(),range(2)))
        self.assertEqual(sum(result is not None for result in results),1)
