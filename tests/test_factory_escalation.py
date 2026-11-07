"""P44 native factory diagnostics. Only publication transport is fault-injected."""
import json
from pathlib import Path
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError,connection
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition,register_reference
from apps.identity.models import Grant
from apps.documents.models import Publication,PublicationJob,PublicationReceipt,ControlledReview
from apps.documents.controlled import reserve_publication
from apps.pmo import escalations as native
from apps.pmo.models import EscalationDecision,EscalationRequest,EscalationDocumentBinding
from apps.pmo.issues import log_issue,update_issue
from apps.workflows import factory,factory_escalation as domain
from apps.workflows.models import FactoryWork,FactoryAttempt
from adapters.publications import InternalPublicationAdapter,PublicationTimeoutAfterAccept
from tests.test_escalations import fixture,profile
from tests.helpers import rev,activate
from tests.document_helpers import artifact

class FactoryEscalationTests(TestCase):
    def setUp(self):
        self.a,self.c,self.owner,self.e,self.t,self.recipient,self.state=fixture()
        value=json.loads(Path('fixtures/factory-escalation.json').read_text());value.pop('classification');value.update(preparer_id=self.a.pk,executor_id=self.a.pk)
        config=draft_operator_policy(self.a,self.c.pk,'OPS.factory_escalation_execution',value,self.owner.pk,timezone.now())
        transition(self.a,config.pk,'validated');transition(self.a,config.pk,'active')
    def start(self,direction='escalate',target='Client'):
        self.p=profile(self.a,self.c,self.state,self.e,'client_dependent' if target=='Client' else 'internal',True)
        self.r=native.request_escalation(self.a,self.c.pk,self.p.pk,direction,target,self.e.pk,'Human requested communication',rev(self.c))
        self.w=domain.start(self.a,self.c.pk,'P44-1',self.r.pk,self.t.pk,'Source-bound communication',rev(self.c));return self.w
    def advance(self):factory.run_until_wait(self.w.pk);self.w.refresh_from_db()
    def decision(self,verdict='approve'):
        self.w.refresh_from_db();return domain.decide(self.a,self.w.pk,self.w.revision,rev(self.c),self.r.pk,'Head of PMO',verdict,'Human decision on exact client request')
    def review(self,verdict='approve'):
        self.w.refresh_from_db();v=domain.document(self.w);self.assertIsNotNone(v,self.w.finding)
        return domain.review(self.a,self.w.pk,self.w.revision,rev(self.c),v.pk,verdict,'Human review of exact communication')
    def ready(self):self.start();self.advance();self.decision();self.advance();self.review()
    def finish(self):
        self.advance();self.assertEqual(self.w.status,'verified',self.w.finding);proof=domain.verify(self.w)
        self.assertFalse(proof['issue_resolution_verified']);self.assertEqual(proof['verification_scope'],'reviewed_escalation_communication');return proof
    def test_immediate_missing_clocks_owned_decision_and_full_client_communication(self):
        self.start();self.advance();n=domain.report(self.w)
        self.assertTrue(n['timing']['immediate']);self.assertEqual(n['timing']['clock_status'],'UNCONFIGURED');self.assertEqual(n['stage'],'decision')
        self.assertFalse(EscalationDecision.objects.exists());self.assertFalse(Publication.objects.exists())
        self.assertIn(self.a.username,domain.projection(self.a,self.w)['owner_names'])
        observed=FactoryAttempt.objects.get(activity__work=self.w,activity__kind='ACT04',phase='observed')
        self.assertEqual([x['profile_id'] for x in observed.result['investigation']['findings']],[self.p.pk])
        self.assertFalse(observed.result['approval_granted']);self.decision();self.advance();self.review();proof=self.finish()
        self.state.issue.refresh_from_db();self.assertEqual(self.state.issue.current.status,'Open');self.assertEqual(len(proof['receipt_ids']),1)
    def test_client_deescalation_requires_its_current_approval(self):
        self.start('de_escalate');self.advance();self.assertIsNone(domain.document(self.w));self.decision();self.advance();self.review();proof=self.finish();self.assertEqual(proof['direction'],'de_escalate')
    def test_internal_route_has_no_invented_business_decision(self):
        ref=register_reference(self.a,self.c.pk,'role:internal-pmo','schema:psl/role-assignment/v1',{'role':'PMO','user_id':self.a.pk},self.owner.pk)
        from apps.policy.services import active_component
        pc=active_component('D05.role_principal_assignments',self.c);activate(self.a,self.c,'D05.role_principal_assignments',pc.envelope['value']+[ref.ref],self.owner)
        rec=register_reference(self.a,self.c.pk,'recipient:pmo','schema:psl/document-recipient/v1',{'audience':'internal','user_id':self.a.pk},self.owner.pk)
        activate(self.a,self.c,'D11.recipient_grant_refs',[rec.ref],self.owner)
        self.start(target='PMO');self.advance();self.review();proof=self.finish();self.assertIsNone(proof['decision']);self.assertFalse(EscalationDecision.objects.exists())
    def test_investigation_is_scoped_not_case_wide(self):
        other=log_issue(self.a,self.c.pk,'ESC-2','Other blocker','Delivery',self.a.pk,'Inspect',self.e.pk,'Source',rev(self.c),'Low')
        profile(self.a,self.c,other,self.e,'client_dependent',True);self.start();self.advance()
        result=FactoryAttempt.objects.get(activity__work=self.w,activity__kind='ACT04',phase='observed').result
        self.assertEqual(len(result['investigation']['findings']),1)
    def test_returned_client_decision_requires_explicit_successor_and_keeps_budget(self):
        artifact(self.a,self.c,'D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'Head of PMO','actions':['return']}]},self.owner)
        self.start();self.advance();self.decision('return');self.advance();spent=self.w.budget_used;old=self.r
        with self.assertRaises(ValidationError):self.decision()
        self.p=profile(self.a,self.c,self.state,self.e,'client_dependent',True)
        self.r=native.request_escalation(self.a,self.c.pk,self.p.pk,'escalate','Client',self.e.pk,'Corrected source and human request',rev(self.c))
        domain.correct(self.a,self.w.pk,self.w.revision,rev(self.c),self.r.pk,self.t.pk,'Explicit source successor');self.w.refresh_from_db()
        self.assertEqual(self.w.budget_used,spent);self.assertEqual(old.decisions.get().verdict,'return');self.decision();self.advance();self.review();self.finish()
    def test_returned_document_requires_deliberate_successor_without_resetting_history(self):
        artifact(self.a,self.c,'D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'PMO Lead','actions':['return']}]},self.owner)
        self.start();self.decision();self.advance();old=domain.document(self.w);self.review('return');self.advance();spent=self.w.budget_used
        domain.correct(self.a,self.w.pk,self.w.revision,rev(self.c),self.r.pk,self.t.pk,'Human requests new reviewed communication');self.w.refresh_from_db();self.assertEqual(self.w.budget_used,spent)
        self.advance();self.assertNotEqual(old.pk,domain.document(self.w).pk);self.review();self.finish();self.assertEqual(old.reviews.get().verdict,'return')
    def test_same_source_cannot_reset_pending_native_review(self):
        self.start();self.decision();self.advance()
        with self.assertRaisesMessage(ValidationError,'pending'):domain.correct(self.a,self.w.pk,self.w.revision,rev(self.c),self.r.pk,self.t.pk,'Do not erase review wait')
    def test_unbound_publication_and_forged_verified_status_rejected_by_database(self):
        self.ready();v=domain.document(self.w)
        with self.assertRaises(DatabaseError),transaction.atomic():reserve_publication(self.a,self.c.pk,v.pk,rev(self.c))
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.w.pk).update(status='verified')
    def test_revoked_client_decision_stops_native_and_direct_sql_publication(self):
        self.ready();v=domain.document(self.w);p=reserve_publication(self.a,self.c.pk,v.pk,rev(self.c),factory_work_id=self.w.pk)
        Grant.objects.filter(case=self.c,user=self.a,action='issue.escalation_decide').update(active=False)
        from apps.documents.delivery import run_publication_once
        run_publication_once(job_id=p.job.pk);self.assertEqual(PublicationJob.objects.get(publication=p).status,'held');self.assertFalse(PublicationReceipt.objects.exists())
        with connection.cursor() as cur:
            cur.execute('SELECT psl_escalation_document(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)',[self.w.pk,v.pk,p.review_id,p.actor_id,p.factory_policy_id,p.factory_source_id,json.dumps(p.recipient_ids),json.dumps(p.policies)])
            self.assertFalse(cur.fetchone()[0])
    def test_unknown_original_receipt_reconciles_without_new_delivery(self):
        self.ready();self.assertTrue(factory.run_once(self.w.pk));self.w.refresh_from_db()
        # A stable investigation can precede dispatch. Drive only until the native publication exists.
        for _ in range(8):
            if Publication.objects.filter(factory_work=self.w).exists():break
            factory.run_once(self.w.pk);self.w.refresh_from_db()
        job=PublicationJob.objects.get(publication__factory_work=self.w)
        from apps.documents.delivery import run_publication_once
        run_publication_once(PublicationTimeoutAfterAccept(),job_id=job.pk);job.refresh_from_db();self.assertEqual(job.status,'unknown');receipt=PublicationReceipt.objects.get(publication=job.publication)
        self.w.refresh_from_db();domain.reconcile(self.a,self.w.pk,self.w.revision);self.w.refresh_from_db();self.finish()
        self.assertEqual(Publication.objects.filter(factory_work=self.w).count(),1);self.assertEqual(PublicationReceipt.objects.get().pk,receipt.pk)
    def test_unknown_no_receipt_lookup_never_resends_or_allows_source_replacement(self):
        class Unknown(InternalPublicationAdapter):
            def deliver(self,*args):raise AssertionError('Receipt-only reconciliation must never resend')
        self.ready();v=domain.document(self.w);p=reserve_publication(self.a,self.c.pk,v.pk,rev(self.c),factory_work_id=self.w.pk)
        PublicationJob.objects.filter(publication=p).update(status='unknown');self.w.refresh_from_db()
        domain.reconcile(self.a,self.w.pk,self.w.revision,Unknown());self.w.refresh_from_db();self.assertEqual(self.w.status,'waiting_effect')
        with self.assertRaisesMessage(ValidationError,'original effects'):domain.correct(self.a,self.w.pk,self.w.revision,rev(self.c),self.r.pk,self.t.pk,'No replacement of uncertain delivery')
        self.assertEqual(Publication.objects.count(),1);self.assertFalse(PublicationReceipt.objects.exists())
    def test_changed_source_invalidates_verified_claim_and_preserves_receipts(self):
        self.ready();self.finish();receipt=PublicationReceipt.objects.get();spent=self.w.budget_used
        state=update_issue(self.a,self.c.pk,self.state.issue_id,self.state.pk,'acknowledge',self.e.pk,'Actual owner acknowledgement',rev(self.c))
        with self.assertRaises(ValidationError):domain.verify(self.w)
        self.assertTrue(domain.projection(self.a,self.w)['readiness_changed']);self.assertEqual(PublicationReceipt.objects.get().pk,receipt.pk);self.w.refresh_from_db();self.assertEqual(self.w.budget_used,spent)
    def test_primary_http_intake_decisions_review_and_get_preserves_rows(self):
        self.start();self.client.force_login(self.a);url=reverse('factory_detail',args=[self.w.pk]);self.advance()
        count=FactoryAttempt.objects.count();revision=self.w.revision;self.assertContains(self.client.get(url),'Client escalation or de-escalation decision');self.assertEqual(FactoryAttempt.objects.count(),count);self.w.refresh_from_db();self.assertEqual(self.w.revision,revision)
        self.assertEqual(self.client.post(url,{'action':'decision','revision':self.w.revision,'case_revision':rev(self.c),'request':self.r.pk,'role':'Head of PMO','verdict':'approve','note':'Human approves client communication'}).status_code,302)
        self.advance();v=domain.document(self.w)
        response=self.client.get(url);self.assertContains(response,'Awaiting exact document review');self.assertIn('no-store',response['Cache-Control'])
        self.assertEqual(self.client.post(url,{'action':'review','revision':self.w.revision,'case_revision':rev(self.c),'version':v.pk,'verdict':'approve','note':'Human approves exact projection'}).status_code,302)
        self.finish();self.assertContains(self.client.get(url),'Issue resolution is tracked separately')
        self.assertContains(self.client.get(reverse('factory_configuration',args=[self.c.pk])+'?definition=pmo-escalation/v1'),'Existing escalation communication preparer')
        Grant.objects.filter(case=self.c,user=self.a,action='issue.read').update(active=False);self.assertEqual(self.client.get(url).status_code,404)
    def test_role_assignment_change_preserves_generic_grant_but_rejects_current_publication(self):
        from apps.policy.services import active_component
        self.ready();v=domain.document(self.w);p=reserve_publication(self.a,self.c.pk,v.pk,rev(self.c),factory_work_id=self.w.pk)
        current=active_component('D05.role_principal_assignments',self.c)
        # Remove only the exact Head role used by the client decision. Document PMO Lead remains.
        from apps.policy.models import RegisteredReference
        refs=[ref for ref in current.envelope['value'] if RegisteredReference.objects.get(case=self.c,ref=ref,version=1).content['role']!='Head of PMO']
        activate(self.a,self.c,'D05.role_principal_assignments',refs,self.owner)
        self.assertTrue(Grant.objects.filter(case=self.c,user=self.a,action='issue.escalation_decide',active=True).exists())
        with connection.cursor() as cur:
            cur.execute('SELECT psl_escalation_document(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)',[self.w.pk,v.pk,p.review_id,p.actor_id,p.factory_policy_id,p.factory_source_id,json.dumps(p.recipient_ids),json.dumps(p.policies)])
            self.assertFalse(cur.fetchone()[0])
        from apps.documents.delivery import run_publication_once
        run_publication_once(job_id=p.job.pk);self.assertFalse(PublicationReceipt.objects.exists())
    def test_all_recipient_receipts_and_current_destination_required(self):
        from django.contrib.auth import get_user_model
        from apps.policy.services import active_component
        second=get_user_model().objects.create_user('second-escalation-recipient')
        Grant.objects.create(case=self.c,user=second,action='document.receive:client')
        current=active_component('D11.recipient_grant_refs',self.c)
        ref=register_reference(self.a,self.c.pk,'recipient:second','schema:psl/document-recipient/v1',{'audience':'client','user_id':second.pk},self.owner.pk)
        activate(self.a,self.c,'D11.recipient_grant_refs',current.envelope['value']+[ref.ref],self.owner)
        self.ready();proof=self.finish();self.assertEqual(len(proof['receipt_ids']),2)
        Grant.objects.filter(case=self.c,user=second,action='document.receive:client').update(active=False)
        with self.assertRaises(PermissionDenied):domain.verify(self.w)
        self.assertEqual(PublicationReceipt.objects.count(),2)
    def test_internal_no_review_policy_does_not_acquire_business_or_document_approval(self):
        from apps.documents.controlled import register_template
        from apps.policy.services import active_component
        ref=register_reference(self.a,self.c.pk,'role:internal-cto','schema:psl/role-assignment/v1',{'role':'CTO','user_id':self.a.pk},self.owner.pk)
        current=active_component('D05.role_principal_assignments',self.c);activate(self.a,self.c,'D05.role_principal_assignments',current.envelope['value']+[ref.ref],self.owner)
        ref=register_reference(self.a,self.c.pk,'recipient:internal-cto','schema:psl/document-recipient/v1',{'audience':'internal','user_id':self.a.pk},self.owner.pk)
        activate(self.a,self.c,'D11.recipient_grant_refs',[ref.ref],self.owner)
        definition=dict(self.t.definition,internal_review_required=False)
        self.t=register_template(self.a,self.c.pk,'Internal quality configuration',definition,self.owner.pk,rev(self.c))
        artifact(self.a,self.c,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[self.t.pk],'repository':'internal-versioned','retention_days':30},self.owner)
        Grant.objects.filter(case=self.c,user=self.a,action='document.request_review').update(active=False)
        self.start(target='CTO');proof=self.finish();self.assertIsNone(proof['decision']);self.assertFalse(ControlledReview.objects.exists())
    def test_read_only_detail_and_projection_preserve_every_native_table(self):
        self.ready();self.finish();self.client.force_login(self.a)
        def rows():
            result={}
            with connection.cursor() as cur:
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'django_session' ORDER BY tablename")
                names=[row[0] for row in cur.fetchall()]
                for name in names:
                    cur.execute('SELECT count(*),md5(COALESCE(string_agg(to_jsonb(t)::text,\'\' ORDER BY to_jsonb(t)::text),\'\')) FROM "'+name+'" t')
                    result[name]=cur.fetchone()
            return result
        before=rows();domain.projection(self.a,self.w)
        self.assertContains(self.client.get(reverse('factory_detail',args=[self.w.pk])),'Issue resolution is tracked separately')
        self.assertEqual(rows(),before)
    def test_unknown_original_cannot_be_cancelled_to_allow_a_replacement(self):
        self.ready();v=domain.document(self.w);p=reserve_publication(self.a,self.c.pk,v.pk,rev(self.c),factory_work_id=self.w.pk)
        PublicationJob.objects.filter(publication=p).update(status='unknown');self.w.refresh_from_db()
        with self.assertRaisesMessage(ValidationError,'receipt-only'):domain.operate(self.a,self.w.pk,self.w.revision,rev(self.c),p.job.pk,'cancel','Do not erase uncertainty')
        self.assertEqual(PublicationJob.objects.get(publication=p).status,'unknown')
    def test_raw_publication_insert_rejects_withdrawn_exact_client_authority(self):
        from apps.documents.controlled import publication_requirements,validate_review
        self.ready();v=domain.document(self.w);review=validate_review(self.c,v);pins,recipients,retention=publication_requirements(self.c,v)
        Grant.objects.filter(case=self.c,user=self.a,action='issue.escalation_decide').update(active=False)
        with self.assertRaisesMessage(DatabaseError,'Exact same-case registered factory publication'),transaction.atomic():
            Publication.objects.create(version=v,review=review,actor=self.a,policies=pins,recipient_ids=recipients,retention_days=retention,operation_key='forged-current-authority',factory_work=self.w,factory_policy_id=self.w.policy_id,factory_source_id=self.w.source_head_id)
        self.assertFalse(Publication.objects.exists())
    def test_verified_database_guard_rechecks_current_role_assignment(self):
        from apps.policy.services import active_component
        self.ready();self.finish();current=active_component('D05.role_principal_assignments',self.c)
        from apps.policy.models import RegisteredReference
        refs=[ref for ref in current.envelope['value'] if RegisteredReference.objects.get(case=self.c,ref=ref,version=1).content['role']!='Head of PMO']
        activate(self.a,self.c,'D05.role_principal_assignments',refs,self.owner)
        with self.assertRaisesMessage(DatabaseError,'communication and every receipt'),transaction.atomic():FactoryWork.objects.filter(pk=self.w.pk).update(status='verified')
        self.assertEqual(PublicationReceipt.objects.count(),1)
    def test_unrelated_plain_text_and_non_intake_json_are_not_cast_by_guard(self):
        from apps.core.services import add_evidence
        add_evidence(self.a,self.c.pk,'ordinary','This is valid ordinary text, not JSON','synthetic:ordinary')
        e=add_evidence(self.a,self.c.pk,'ordinary_json','{"request_id":"not-an-integer","profile_id":false}','synthetic:ordinary-json')
        with connection.cursor() as cur:
            cur.execute('SELECT psl_escalation_intake(%s)',[e.pk]);self.assertIsNone(cur.fetchone()[0])
        self.ready();self.finish()
    def test_source_successor_cannot_open_fresh_work_and_reset_allowance(self):
        self.start();self.advance();spent=self.w.budget_used
        p=profile(self.a,self.c,self.state,self.e,'client_dependent',True)
        r=native.request_escalation(self.a,self.c.pk,p.pk,'escalate','Client',self.e.pk,'New human source successor',rev(self.c))
        with self.assertRaises(ValidationError):domain.start(self.a,self.c.pk,'NEW-WORK',r.pk,self.t.pk,'Replacement intent',rev(self.c))
        self.assertEqual(FactoryWork.objects.count(),1);self.w.refresh_from_db();self.assertEqual(self.w.budget_used,spent)
    def test_distinct_head_client_decision_and_pmo_lead_document_review(self):
        from django.contrib.auth import get_user_model
        from apps.policy.services import active_component
        from apps.policy.models import RegisteredReference
        head=get_user_model().objects.create_user('distinct-head')
        for action in ['case.read','issue.read','factory.read','issue.escalation_decide']:Grant.objects.create(case=self.c,user=head,action=action)
        current=active_component('D05.role_principal_assignments',self.c)
        refs=[ref for ref in current.envelope['value'] if RegisteredReference.objects.get(case=self.c,ref=ref,version=1).content['role']!='Head of PMO']
        ref=register_reference(self.a,self.c.pk,'role:distinct-head','schema:psl/role-assignment/v1',{'role':'Head of PMO','user_id':head.pk},self.owner.pk)
        activate(self.a,self.c,'D05.role_principal_assignments',refs+[ref.ref],self.owner)
        self.start();self.advance();domain.decide(head,self.w.pk,self.w.revision,rev(self.c),self.r.pk,'Head of PMO','approve','Distinct accountable client decision')
        self.advance();review=self.review();proof=self.finish();self.assertNotEqual(EscalationDecision.objects.get(pk=proof['decision']).actor_id,review.actor_id)
    def test_native_worker_unknown_and_expired_lease_are_receipt_only(self):
        from datetime import timedelta
        from apps.documents.delivery import run_publication_once
        class Counter(InternalPublicationAdapter):
            calls=0
            def deliver(self,*args):self.calls+=1;return super().deliver(*args)
        self.ready();v=domain.document(self.w);p=reserve_publication(self.a,self.c.pk,v.pk,rev(self.c),factory_work_id=self.w.pk)
        for status in ['unknown','leased']:
            PublicationJob.objects.filter(publication=p).update(status=status,lease_until=timezone.now()-timedelta(seconds=1))
            adapter=Counter();self.assertTrue(run_publication_once(adapter,job_id=p.job.pk));self.assertEqual(adapter.calls,0)
            self.assertEqual(PublicationJob.objects.get(publication=p).status,'unknown');self.assertFalse(PublicationReceipt.objects.exists())
    def test_native_operator_cannot_cancel_or_retry_unknown_bound_publication(self):
        from apps.documents.delivery import operate_publication
        self.ready();v=domain.document(self.w);p=reserve_publication(self.a,self.c.pk,v.pk,rev(self.c),factory_work_id=self.w.pk)
        PublicationJob.objects.filter(publication=p).update(status='unknown')
        for action in ['cancel','retry']:
            with self.assertRaisesMessage(ValidationError,'receipt-only'):operate_publication(self.a,self.c.pk,p.job.pk,action,'Native operator path must preserve original uncertainty',rev(self.c))
        self.assertEqual(PublicationJob.objects.get(publication=p).status,'unknown')
    def test_non_factory_native_unknown_retains_existing_idempotent_delivery(self):
        from apps.documents.delivery import run_publication_once
        from tests.document_helpers import reserved
        class Counter(InternalPublicationAdapter):
            calls=0
            def deliver(self,*args):self.calls+=1;return super().deliver(*args)
        p=reserved(self.a,self.c,self.t,self.e);PublicationJob.objects.filter(publication=p).update(status='unknown')
        adapter=Counter();self.assertTrue(run_publication_once(adapter,job_id=p.job.pk));self.assertEqual(adapter.calls,1)
        self.assertEqual(PublicationJob.objects.get(publication=p).status,'confirmed');self.assertEqual(PublicationReceipt.objects.filter(publication=p).count(),1)
    def test_failed_native_receipt_lookup_preserves_unknown_original(self):
        from apps.documents.delivery import run_publication_once,operate_publication
        class FailedLookup(InternalPublicationAdapter):
            def lookup(self,publication):raise ValidationError('Synthetic receipt verification failed')
            def deliver(self,*args):raise AssertionError('An inconclusive lookup never authorises delivery')
        self.ready();v=domain.document(self.w);p=reserve_publication(self.a,self.c.pk,v.pk,rev(self.c),factory_work_id=self.w.pk)
        PublicationJob.objects.filter(publication=p).update(status='unknown')
        run_publication_once(FailedLookup(),job_id=p.job.pk)
        job=PublicationJob.objects.get(publication=p);self.assertEqual(job.status,'unknown');self.assertIn('verification failed',job.error)
        with self.assertRaisesMessage(ValidationError,'receipt-only'):operate_publication(self.a,self.c.pk,job.pk,'cancel','Lookup failure is not confirmed absence',rev(self.c))
        self.assertFalse(PublicationReceipt.objects.exists())
    def test_unrelated_out_of_range_json_is_not_parsed_as_intake(self):
        from apps.core.services import add_evidence
        evidence=add_evidence(self.a,self.c.pk,'ordinary_json_range','{"number":1e1000000}','synthetic:unrelated-json-range')
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_escalation_intake(%s)',[evidence.pk]);self.assertIsNone(cursor.fetchone()[0])
        self.ready();self.finish()
