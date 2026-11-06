import json
from pathlib import Path
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.test import TestCase,TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from apps.core.services import add_evidence
from apps.core.models import Evidence
from apps.identity.models import Grant
from apps.documents.models import Publication,PublicationJob,PublicationReceipt
from apps.documents.controlled import register_template,review_version,create_version
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.pmo.models import DeliveryRecord
from apps.workflows import factory,factory_handover as handover
from apps.workflows.models import FactoryWork,HumanTask
from adapters.publications import PublicationTimeoutAfterAccept
from tests.test_delivery import DeliveryFixture
from tests.helpers import rev,setup_case


def configure(f,owner=True,tokens=20000):
    value=json.loads(Path('fixtures/factory-handover.json').read_text());value.pop('classification')
    value.update(executor_id=f.publisher.pk if owner else None,max_tokens=tokens)
    p=draft_operator_policy(f.actor,f.case.pk,'OPS.factory_handover_execution',value,f.e['policy_decision'].pk,timezone.now())
    transition(f.actor,p.pk,'validated');transition(f.actor,p.pk,'active');return p


def setup(profile=True,owner=True,known=True,review=False):
    f=DeliveryFixture();f.setup_delivery()
    f.publisher=get_user_model().objects.create_user(username='synthetic-handover-publisher')
    Grant.objects.bulk_create([Grant(case=f.case,user=f.publisher,action=a) for a in ['case.read','delivery.read','factory.execute','document.publish']])
    f.inputs={'template_id':f.t.pk,'support_document':f.evidence('support_document','SYNTHETIC Support operations instructions').pk,
        'escalation_document':f.evidence('escalation_document','SYNTHETIC escalation contacts and route').pk}
    if review:
        t=register_template(f.actor,f.case.pk,'Reviewed support handover',dict(f.t.definition,internal_review_required=True,required_fields=['scope','next_steps'],
            audience_fields={'internal':['scope','next_steps']}),f.e['policy_decision'].pk,rev(f.case));f.inputs['template_id']=t.pk
        # This is explicit synthetic storage coverage of the chosen native template.
        from tests.document_helpers import artifact
        artifact(f.actor,f.case,'D11.template_storage_retention_rules','schema:psl/document-storage/v2',
            {'template_ids':[f.t.pk,t.pk],'repository':'internal-versioned','retention_days':30,
             'closure_inventory':{'required_kinds':['technical_document','test_results','project_artifact'],'archive_mode':'immutable_local_manifest'}},f.e['policy_decision'])
    if profile:f.profile=configure(f,owner)
    f.work=handover.start(f.actor,f.case.pk,'HANDOVER-1',f.d.pk,f.inputs if known else {k:None for k in handover.FIELDS},'Support handover',rev(f.case));return f


def ready(f):
    f.accepted();f.archive()
    if f.inputs['template_id']!=f.t.pk:
        from tests.document_helpers import artifact
        artifact(f.actor,f.case,'D11.template_storage_retention_rules','schema:psl/document-storage/v2',
            {'template_ids':[f.t.pk,f.inputs['template_id']],'repository':'internal-versioned','retention_days':30,
             'closure_inventory':{'required_kinds':['technical_document','test_results','project_artifact'],'archive_mode':'immutable_local_manifest'}},f.e['policy_decision'])
        # Re-index under the current storage version; no archive or handover approval is invented.
        from apps.pmo.delivery_closure import archive_artifacts
        old=DeliveryRecord.objects.filter(dossier=f.d,kind='archive').latest('pk')
        archive_artifacts(f.actor,f.case.pk,f.d.pk,old.data['inventory'],old.evidence_id,'Synthetic current-template archive rule',rev(f.case))


def receipt(f):return PublicationReceipt.objects.get(publication__factory_work=f.work,publication__factory_source=f.work.source_head)


def ack(f,status='received',r=None):
    f.work.refresh_from_db();r=r or receipt(f)
    return handover.acknowledge(f.actor,f.work.pk,f.work.revision,rev(f.case),r.pk,status,f.e['requirements'].pk,'Actual synthetic recipient '+status)


class FactoryHandoverTests(TestCase):
    def test_missing_recipient_rule_retains_draft_then_requests_review_of_same_version_when_configured(self):
        from tests.helpers import activate
        f=setup(review=True);ready(f)
        activate(f.actor,f.case,'D11.recipient_grant_refs',['delivery-recipient:client'],f.e['policy_decision'])
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();v=handover.document(f.work)
        self.assertIsNotNone(v);self.assertEqual(f.work.status,'waiting',f.work.finding)
        self.assertFalse(HumanTask.objects.filter(version=v).exists());self.assertFalse(Publication.objects.filter(factory_work=f.work).exists())
        activate(f.actor,f.case,'D11.recipient_grant_refs',['delivery-recipient:client','delivery-recipient:internal'],f.e['policy_decision'])
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(handover.document(f.work).pk,v.pk)
        self.assertEqual(HumanTask.objects.filter(version=v,status='open').count(),1)
        from apps.pmo.models import DeliveryDocumentBinding
        self.assertEqual(DeliveryDocumentBinding.objects.filter(dossier=f.d,purpose='handover').count(),1)
        handover.review(f.actor,f.work.pk,f.work.revision,rev(f.case),v.pk,'approve','Exact retained draft reviewed after actual recipient configuration')
        factory.run_until_wait(f.work.pk);ack(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertEqual(f.work.budget_limit,20000)

    def test_unassigned_allowance_and_missing_sources_are_plain_and_human_wait_has_no_continue_button(self):
        f=setup(profile=False,known=False);self.client.force_login(f.actor);url=reverse('factory_detail',args=[f.work.pk])
        page=self.client.get(url);self.assertContains(page,'assigned when processing begins');self.assertNotContains(page,'0 of 0')
        self.assertNotContains(page,"[&#x27;Provide");self.assertIn('Provide the controlled template',page.context['row']['next_action'])
        configure(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();page=self.client.get(url)
        self.assertEqual(f.work.status,'waiting');self.assertNotContains(page,'Continue eligible work')
        self.assertIn('Provide the controlled template',page.context['row']['next_action'])
    def test_held_original_retry_uses_same_publication_and_lifetime_allowance(self):
        from adapters.publications import InternalPublicationAdapter
        class RefuseBeforeSend(InternalPublicationAdapter):
            def deliver(self,job_id,fence):raise ValidationError('SYNTHETIC refusal before any internal delivery')
        f=setup();ready(f)
        for _ in range(16):
            factory.run_once(f.work.pk,adapter=RefuseBeforeSend());f.work.refresh_from_db()
            if PublicationJob.objects.filter(publication__factory_work=f.work,status='held').exists():break
        job=PublicationJob.objects.get(publication__factory_work=f.work);self.assertEqual(job.status,'held');spent=f.work.budget_used
        self.client.force_login(f.actor);url=reverse('factory_detail',args=[f.work.pk]);self.assertContains(self.client.get(url),'Retry original delivery')
        self.assertRedirects(self.client.post(url,{'action':'operate_delivery','revision':f.work.revision,'case_revision':rev(f.case),'job':job.pk,
            'operation':'retry','reason':'Current authority and package checked after synthetic pre-send refusal'}),url)
        f.work.refresh_from_db();self.assertEqual(f.work.budget_used,spent)
        factory.run_until_wait(f.work.pk);ack(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertEqual(f.work.budget_limit,20000)
        self.assertEqual(Publication.objects.filter(factory_work=f.work).count(),1);self.assertEqual(PublicationReceipt.objects.filter(publication=job.publication).count(),1)

    def test_cancelled_unreceived_reservation_has_reviewed_same_source_successor(self):
        f=setup();ready(f)
        for _ in range(12):
            factory.run_once(f.work.pk);f.work.refresh_from_db()
            if Publication.objects.filter(factory_work=f.work).exists():break
        job=PublicationJob.objects.get(publication__factory_work=f.work);old=job.publication
        handover.operate(f.actor,f.work.pk,f.work.revision,rev(f.case),job.pk,'cancel','Stop the unreceived local reservation before a reviewed fresh instruction')
        f.work.refresh_from_db();spent=f.work.budget_used
        handover.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),f.inputs,'Fresh reviewed package after cancellation with no internal receipt; retain old reservation')
        factory.run_until_wait(f.work.pk);ack(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();job.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertEqual(job.status,'cancelled')
        self.assertFalse(PublicationReceipt.objects.filter(publication=old).exists());self.assertEqual(Publication.objects.filter(factory_work=f.work).count(),2)
        self.assertEqual(f.work.budget_limit,20000);self.assertGreater(f.work.budget_used,spent)

    def test_current_owner_projection_does_not_assign_a_revoked_recipient(self):
        from apps.workflows.factory_views import presentation
        f=setup();ready(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        Grant.objects.filter(case=f.case,user=f.actor,action='delivery.support_receive').update(active=False)
        row=presentation(f.actor,f.work);self.assertEqual(row['owner'],f.actor.username);self.assertTrue(row['needs_me'])
        self.assertEqual(row['handover']['pending_owner_names'],[]);self.assertIn('Review changed',row['next_action'])
        self.assertFalse(any(x['can_ack'] for x in row['handover']['receipts']))
        reader=get_user_model().objects.create_user(username='synthetic-handover-read-only')
        Grant.objects.bulk_create([Grant(case=f.case,user=reader,action=a) for a in ['case.read','delivery.read','factory.read']])
        readonly=presentation(reader,f.work);self.assertEqual(readonly['owner'],'Unassigned');self.assertFalse(readonly['needs_me'])
        self.assertFalse(any(x['can_ack'] for x in readonly['handover']['receipts']));self.assertFalse(readonly['handover']['can_correct'])

    def test_current_recipient_policy_successor_requires_fresh_package_even_with_unchanged_sources(self):
        from tests.helpers import activate
        from apps.policy.services import register_reference
        f=setup();ready(f);factory.run_until_wait(f.work.pk);ack(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();old=receipt(f)
        with self.assertRaisesMessage(ValidationError,'remain current'):
            handover.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),f.inputs,'No actual source or contract change')
        # Re-review the recipient contract as a real versioned successor; actual recipients stay explicit.
        refs=[]
        for audience in ['client','internal']:
            r=register_reference(f.actor,f.case.pk,'successor-recipient:'+audience,'schema:psl/document-recipient/v1',{'audience':audience,'user_id':f.actor.pk},f.e['policy_decision'].pk);refs.append(r.ref)
        activate(f.actor,f.case,'D11.recipient_grant_refs',refs,f.e['policy_decision'])
        self.assertTrue(handover.projection(f.actor,f.work)['readiness_changed'])
        handover.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),f.inputs,'Review current versioned destination contract; retain original receipt')
        factory.run_until_wait(f.work.pk);ack(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertTrue(PublicationReceipt.objects.filter(pk=old.pk).exists())
        self.assertEqual(Publication.objects.filter(factory_work=f.work).count(),2);self.assertEqual(f.work.budget_limit,20000)

    def test_distinct_actual_recipient_uses_exact_http_receipt_and_has_no_execution_or_private_run_access(self):
        from tests.helpers import activate
        from apps.policy.services import register_reference
        f=setup();receiver=get_user_model().objects.create_user(username='synthetic-support-recipient')
        Grant.objects.bulk_create([Grant(case=f.case,user=receiver,action=a) for a in ['case.read','delivery.read','factory.read','delivery.support_receive','document.receive:internal']])
        refs=[]
        for audience,user in [('client',f.actor),('internal',receiver)]:
            r=register_reference(f.actor,f.case.pk,'actual-recipient:'+audience,'schema:psl/document-recipient/v1',{'audience':audience,'user_id':user.pk},f.e['policy_decision'].pk);refs.append(r.ref)
        activate(f.actor,f.case,'D11.recipient_grant_refs',refs,f.e['policy_decision']);ready(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();r=receipt(f)
        with self.assertRaisesMessage(ValidationError,'own exact'):
            handover.acknowledge(f.actor,f.work.pk,f.work.revision,rev(f.case),r.pk,'received',f.e['requirements'].pk,'The sender cannot impersonate actual receipt')
        self.client.force_login(receiver);url=reverse('factory_detail',args=[f.work.pk]);page=self.client.get(url)
        self.assertContains(page,'Record your actual receipt or gaps');self.assertNotContains(page,'Continue eligible work')
        generic=self.client.get(reverse('case',args=[f.case.pk]));self.assertEqual(list(generic.context['runs']),[])
        body={'action':'acknowledge','revision':f.work.revision,'case_revision':rev(f.case),'receipt':r.pk,'status':'received','evidence':f.e['requirements'].pk,'note':'Actual synthetic Support received this exact package'}
        self.assertRedirects(self.client.post(url,body),url);self.assertContains(self.client.post(url,body),'Stale revision')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='handover').get().actor_id,receiver.pk)

    def test_current_publisher_revocation_before_send_holds_original_job_and_source_edits(self):
        from apps.documents.delivery import run_publication_once,operate_publication
        f=setup();ready(f)
        for _ in range(12):
            factory.run_once(f.work.pk);f.work.refresh_from_db()
            if Publication.objects.filter(factory_work=f.work).exists():break
        job=PublicationJob.objects.get(publication__factory_work=f.work)
        Grant.objects.filter(case=f.case,user=f.publisher,action='document.publish').update(active=False)
        self.assertTrue(run_publication_once(case_id=f.case.pk,job_id=job.pk));job.refresh_from_db();self.assertEqual(job.status,'held')
        self.assertFalse(PublicationReceipt.objects.filter(publication=job.publication).exists())
        successor=f.evidence('support_document')
        with self.assertRaisesMessage(ValidationError,'Resolve original delivery'):
            handover.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),dict(f.inputs,support_document=successor.pk),'Cannot replace the unresolved original job')
        self.client.force_login(f.actor);url=reverse('factory_detail',args=[f.work.pk]);page=self.client.get(url)
        self.assertContains(page,'Cancel unreceived delivery');self.assertNotContains(page,'Retry original delivery')
        self.assertRedirects(self.client.post(url,{'action':'operate_delivery','revision':f.work.revision,'case_revision':rev(f.case),'job':job.pk,
            'operation':'cancel','reason':'No receipts exist; stop the held original reservation before reviewed source correction'}),url)
        job.refresh_from_db();self.assertEqual(job.status,'cancelled')
        self.assertEqual(Publication.objects.filter(factory_work=f.work).count(),1)

    def test_configuration_refuses_handover_approval_private_sources_and_ungranted_publisher(self):
        from types import SimpleNamespace
        from apps.policy.factory_validators import HANDOVER_COMPONENT,HANDOVER_SCHEMA,validate_reference
        f=setup(profile=False);other=get_user_model().objects.create_user(username='ungranted-handover-admin',is_superuser=True)
        value=json.loads(Path('fixtures/factory-handover.json').read_text());value.pop('classification')
        for changes in [{'review_role':'Head of PMO'},{'information_resolver_id':f.actor.pk},{'executor_id':other.pk},{'required_evidence_kinds':['p14_inputs']},{'tokens_per_call':20001},{'actual_receipt_automatic':True}]:
            with self.assertRaises(ValidationError):validate_reference(HANDOVER_COMPONENT,SimpleNamespace(schema_ref=HANDOVER_SCHEMA,content=dict(value,**changes)),f.case)
        self.assertEqual(validate_reference(HANDOVER_COMPONENT,SimpleNamespace(schema_ref=HANDOVER_SCHEMA,content=value),f.case),value)

    def test_superseded_document_false_publication_sql_and_reviewed_same_source_recovery(self):
        f=setup();ready(f);factory.run_until_wait(f.work.pk);ack(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();old=receipt(f);v=handover.document(f.work)
        replacement=create_version(f.actor,f.case.pk,v.template_id,v.document.title,v.audience,v.fields,rev(f.case),document_id=v.document_id)
        self.assertTrue(handover.projection(f.actor,f.work)['readiness_changed'])
        self.client.force_login(f.actor);self.assertEqual(self.client.get(reverse('home')+'?queue=verified').context['rows'],[])
        with self.assertRaises(DatabaseError),transaction.atomic():
            Publication.objects.create(version=replacement,review=None,actor=f.publisher,policies=old.publication.policies,recipient_ids=[f.actor.pk],
                retention_days=30,operation_key='synthetic:unbound-handover-version',factory_work=f.work,factory_policy=f.work.policy,factory_source=f.work.source_head)
        handover.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),f.inputs,'Review superseded controlled version and prepare a fresh exact native package')
        factory.run_until_wait(f.work.pk);ack(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertTrue(PublicationReceipt.objects.filter(pk=old.pk).exists())
        self.assertEqual(Publication.objects.filter(factory_work=f.work).count(),2);self.assertEqual(f.work.budget_limit,20000)

    def test_cancelled_expired_delivery_is_reconciled_without_send_then_settled_by_native_operator(self):
        from apps.documents.delivery import claim_publication
        f=setup();ready(f)
        for _ in range(12):
            factory.run_once(f.work.pk);f.work.refresh_from_db()
            if Publication.objects.filter(factory_work=f.work).exists():break
        job=PublicationJob.objects.get(publication__factory_work=f.work);self.assertIsNotNone(claim_publication(case_id=f.case.pk,job_id=job.pk))
        factory.manage(f.actor,f.work.pk,f.work.revision,'cancel');f.work.refresh_from_db();spent=f.work.budget_used
        PublicationJob.objects.filter(pk=job.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        self.client.force_login(f.actor);url=reverse('factory_detail',args=[f.work.pk]);self.assertContains(self.client.get(url),'Reconcile original delivery')
        self.assertRedirects(self.client.post(url,{'action':'reconcile','revision':f.work.revision}),url)
        f.work.refresh_from_db();job.refresh_from_db();self.assertEqual(job.status,'held');self.assertFalse(PublicationReceipt.objects.filter(publication=job.publication).exists())
        handover.operate(f.actor,f.work.pk,f.work.revision,rev(f.case),job.pk,'cancel','Settle the stopped original delivery with no internal receipts')
        f.work.refresh_from_db();self.assertEqual(f.work.status,'cancelled');self.assertEqual(f.work.budget_used,spent)

    def test_agent_prepares_and_delivers_then_waits_for_actual_gaps_and_recipient_receipt(self):
        self.assertEqual(connection.vendor,'postgresql');f=setup();ready(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'waiting',f.work.finding);v=handover.document(f.work);r=receipt(f)
        self.assertEqual(r.publication.actor_id,f.publisher.pk);self.assertFalse(HumanTask.objects.filter(case=f.case,version=v).exists())
        self.assertFalse(HumanTask.objects.filter(case=f.case,kind='factory_review').exists());self.assertEqual(Publication.objects.filter(factory_work=f.work).count(),1)
        with self.assertRaisesMessage(ValidationError,'actual receipt'):handover.verify(f.work)
        ack(f,'gaps');factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'waiting')
        old=DeliveryRecord.objects.filter(dossier=f.d,kind='handover').get();ack(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertTrue(DeliveryRecord.objects.filter(pk=old.pk,data__status='gaps').exists())
        proof=handover.verify(f.work);self.assertTrue(proof['verified'])
        for flag in ['separate_handover_approval','closure_approved','financial_release_granted','deployment_authorized','external_authenticity_verified']:self.assertIs(proof[flag],False)
        self.client.force_login(f.actor);page=self.client.get(reverse('factory_detail',args=[f.work.pk]));self.assertContains(page,'SYNTHETIC Support operations instructions')
        self.assertContains(page,'actual recipient acknowledgement');self.assertEqual(page['Cache-Control'],'no-store')

    def test_configured_native_document_review_is_exact_and_separate_from_receiving(self):
        f=setup(review=True);ready(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();v=handover.document(f.work)
        self.assertIsNotNone(v);self.assertFalse(Publication.objects.filter(factory_work=f.work).exists())
        self.assertEqual(HumanTask.objects.filter(version=v,status='open').count(),1);self.client.force_login(f.actor)
        url=reverse('factory_detail',args=[f.work.pk]);page=self.client.get(url);self.assertContains(page,'Review the exact handover document')
        self.assertContains(page,'Exact recipient document');self.assertContains(page,'SYNTHETIC Support operations instructions')
        self.assertNotContains(page,v.fields['executive_summary']['text']);self.assertNotContains(page,v.fields['status']['text'])
        self.assertNotContains(page,'Continue eligible work')
        response=self.client.post(url,{'action':'review','revision':f.work.revision,'case_revision':rev(f.case),'version':v.pk,'verdict':'approve','note':'Exact synthetic controlled package reviewed'})
        self.assertRedirects(response,url);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'waiting')
        ack(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)

    def test_unknown_intake_and_missing_profile_or_publisher_do_not_prevent_capture_and_correction(self):
        f=setup(profile=False,known=False);ready(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'configuration_needed')
        handover.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),f.inputs,'Declare exact known synthetic handover inputs')
        configure(f,owner=False);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'owner_needed',f.work.finding)
        self.assertIsNotNone(handover.document(f.work));self.assertFalse(Publication.objects.filter(factory_work=f.work).exists());spent=f.work.budget_used
        p=configure(f,tokens=40000);factory.adopt_profile(f.actor,f.work.pk,f.work.revision,p.pk,'Explicit adoption of the configured synthetic publisher')
        factory.run_until_wait(f.work.pk);ack(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertEqual(f.work.budget_limit,20000);self.assertGreater(f.work.budget_used,spent)

    def test_lost_response_reconciles_original_receipt_even_after_cancellation_without_resending(self):
        f=setup();ready(f)
        for _ in range(16):
            factory.run_once(f.work.pk,adapter=PublicationTimeoutAfterAccept());f.work.refresh_from_db()
            if PublicationJob.objects.filter(publication__factory_work=f.work,status='unknown').exists():break
        job=PublicationJob.objects.get(publication__factory_work=f.work);r=receipt(f);self.assertEqual(job.status,'unknown')
        factory.manage(f.actor,f.work.pk,f.work.revision,'cancel');f.work.refresh_from_db();spent=f.work.budget_used
        factory.reconcile(f.actor,f.work.pk,f.work.revision);f.work.refresh_from_db();job.refresh_from_db()
        self.assertEqual(job.status,'confirmed');self.assertEqual(f.work.status,'followup_needed');self.assertEqual(f.work.budget_used,spent)
        self.assertEqual(PublicationReceipt.objects.filter(publication=job.publication).count(),1);self.assertTrue(PublicationReceipt.objects.filter(pk=r.pk).exists())
        self.assertEqual(Publication.objects.filter(factory_work=f.work).count(),1)

    def test_exact_source_successor_and_old_receipts_are_preserved_with_one_lifetime_allowance(self):
        f=setup();ready(f);factory.run_until_wait(f.work.pk);ack(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();old=receipt(f);spent=f.work.budget_used
        inputs=dict(f.inputs,support_document=f.evidence('support_document','SYNTHETIC revised Support instructions').pk)
        handover.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),inputs,'Review current Support instructions; retain earlier package and receipt')
        factory.run_until_wait(f.work.pk);ack(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertTrue(PublicationReceipt.objects.filter(pk=old.pk).exists())
        self.assertEqual(Publication.objects.filter(factory_work=f.work).count(),2);self.assertGreater(f.work.budget_used,spent);self.assertEqual(f.work.budget_limit,20000)

    def test_foreign_private_typed_source_and_false_completion_guards(self):
        f=setup();other,c=setup_case(username='foreign-handover');foreign=add_evidence(other,c.pk,'support_document','Foreign source','synthetic:other')
        private=f.evidence('p14_inputs','PRIVATE-HANDOVER-COST-SECRET')
        for inputs in [dict(f.inputs,support_document=foreign.pk),dict(f.inputs,support_document=private.pk),dict(f.inputs,template_id=True),dict(f.inputs,support_document=float(f.inputs['support_document']))]:
            with self.assertRaises(ValidationError):handover.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),inputs,'Invalid handover correction')
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=f.work.pk).update(status='verified')
        self.assertFalse(Publication.objects.filter(factory_work=f.work).exists())


class FactoryHandoverConcurrencyTests(TransactionTestCase):
    def test_two_first_forms_create_one_native_handover_intake_and_work(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        f=DeliveryFixture();f.setup_delivery();inputs={'template_id':f.t.pk,**{k:f.evidence(k).pk for k in handover.FIELDS[1:]}};barrier=Barrier(2)
        def enter(n):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return handover.start(f.actor,f.case.pk,'HANDOVER-RACE-'+str(n),f.d.pk,inputs,'One actual handover intent').pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(enter,[1,2]))
        self.assertEqual(ids[0],ids[1]);self.assertEqual(FactoryWork.objects.filter(case=f.case).count(),1)
        self.assertEqual(Evidence.objects.filter(case=f.case,kind=handover.KIND).count(),1)

    def test_real_exit_after_committed_delivery_recovers_original_receipt_and_original_allowance(self):
        import os,sys,subprocess
        f=setup();ready(f);env=dict(os.environ,PGDATABASE=connection.settings_dict['NAME'])
        result=subprocess.run([sys.executable,'-m','tests.factory_worker_scenario',str(f.work.pk),'handover_interrupt_after_delivery'],env=env,capture_output=True,timeout=180)
        self.assertEqual(result.returncode,39,result.stderr.decode());f.work.refresh_from_db();spent=f.work.budget_used
        r=receipt(f);job=PublicationJob.objects.get(publication=r.publication);self.assertEqual(job.status,'leased')
        FactoryWork.objects.filter(pk=f.work.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        PublicationJob.objects.filter(pk=job.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        result=subprocess.run([sys.executable,'-m','tests.factory_worker_scenario',str(f.work.pk),'resume'],env=env,capture_output=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr.decode());job.refresh_from_db();self.assertEqual(job.status,'confirmed')
        factory.run_until_wait(f.work.pk);ack(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertGreater(f.work.budget_used,spent);self.assertEqual(f.work.budget_limit,20000)
        self.assertEqual(Publication.objects.filter(factory_work=f.work).count(),1);self.assertEqual(PublicationReceipt.objects.filter(publication=job.publication).get().pk,r.pk)
        self.assertEqual(job.attempts,2)
