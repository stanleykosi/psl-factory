"""Real PostgreSQL client testing path. Only storage and model provider are fake."""
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection,DatabaseError,transaction,close_old_connections
from django.test import TestCase,TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from adapters import client_uat as contract
from apps.agents import upload_jobs
from apps.agents.upload_views import upload_file
from apps.core import client_contacts
from apps.core.models import ClientContactRevision
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.client_uat_validators import COMPONENT,SCHEMA_REF
from apps.policy.services import transition
from apps.pmo import client_uat as domain,delivery
from apps.pmo.models import DeliverySource,ClientUATGateBinding
from tests.test_delivery import DeliveryFixture
from tests.helpers import rev,activate
from tests.document_helpers import artifact


class ClientUATFixture(DeliveryFixture):
    def setup_uat(self):
        self.setup_delivery();self.memory={}
        fixture=self
        class Bucket:
            def put_object(self,**kw):fixture.memory[kw['Key']]=kw['Body']
            def get_object(self,**kw):return {'Body':BytesIO(fixture.memory[kw['Key']])}
        self.storage_patch=patch('adapters.case_uploads.bucket',return_value=(Bucket(),'synthetic-bucket'))
        self.storage_patch.start();self.addCleanup(self.storage_patch.stop)
        self.contact=client_contacts.save(self.actor,self.case,'project',{
            'customer':'','client_name':'SAMPLE Client','name':'SAMPLE Client Witness','email':'sample@example.invalid',
            'role':'SAMPLE Contact','evidence':self.e['policy_decision'],'revision':rev(self.case)})

    def rule(self,**changes):
        value={'format':'psl.client-uat-rules/v1','human_only':True,'qualification_mode':'reviewed_human_attestation_v1',
            'reviewer_ids':[self.actor.pk],'reviewer_role':'PM','independent_review':False,'agent_review_required':False,
            'exact_mentions_required':True,'proof_formats':['txt','pdf','docx','xlsx'],
            'workaround_mode':'explicit_client_approved_scope_v1','assurance':'human_witnessed_not_external_authentication','financial_controls':'independent'}
        value.update(changes)
        return artifact(self.actor,self.case,COMPONENT,SCHEMA_REF,value,self.e['policy_decision'])

    def target(self,previous=None):
        gate=self.candidate.gates.filter(kind='uat_client').order_by('-pk').first()
        return domain.record_target(self.actor,self.case.pk,self.d.pk,self.contact.pk,timezone.now()-timedelta(hours=2),
            previous.pk if previous else None,gate.pk if gate else None,bool(gate),uuid4(),rev(self.case))

    def proof(self,text=None):
        return upload_file(self.actor,self.case,SimpleUploadedFile('SAMPLE-client-proof.txt',
            (text or 'SAMPLE Client Witness approved delivery-build. SAMPLE source proof.').encode()))

    def response(self,target=None,outcome='approved',previous=None,proof=None,workaround=None):
        target=target or self.target();proof=proof or self.proof()
        return domain.record_response(self.actor,self.case.pk,target.pk,timezone.now()-timedelta(hours=1),outcome,True,
            'SAMPLE genuine response record',workaround,None,[proof.pk],previous.pk if previous else None,uuid4(),rev(self.case))

    def check(self,response):return domain.inspect_proof(self.actor,self.case.pk,response.pk,rev(self.case))

    def review(self,response,inspection=None,actor=None,verdict='confirm'):
        inspection=inspection or self.check(response)
        return domain.review_proof(actor or self.actor,self.case.pk,response.pk,inspection.pk,verdict,verdict=='confirm',
            'SAMPLE exact human proof review',uuid4(),rev(self.case))

    def export(self,response,review):return domain.export_gate(self.actor,self.case.pk,response.pk,review.pk,rev(self.case))


class ClientUATTests(ClientUATFixture,TestCase):
    def setUp(self):self.setup_uat()

    def test_connected_client_proof_release_readiness_and_correction(self):
        self.rule();self.plan();self.gates([k for k in delivery.UPSTREAM_GATES if k!='uat_client'])
        response=self.response();inspection=self.check(response)
        self.assertTrue(inspection.result['checks']['version_mentioned']);self.assertTrue(inspection.result['checks']['contact_mentioned'])
        self.assertFalse(inspection.result['external_authenticity_verified'])
        review=self.review(response,inspection);binding=self.export(response,review)
        self.assertEqual(domain.gate_current(self.candidate,binding.verification).pk,binding.pk)
        self.assertEqual(delivery.upstream(self.d)['gates'][-2],[binding.verification.record_id,binding.verification_id])
        request=delivery.record_release_request(self.actor,self.case.pk,self.d.pk,'SAMPLE-GLPI-client-proof',self.e['requirements'].pk,'Actual synthetic deployment request',rev(self.case))
        self.gates(delivery.GLPI_GATES,'SAMPLE-GLPI-client-proof')
        ready=delivery.prepare_readiness(self.actor,self.case.pk,self.d.pk,rev(self.case))
        self.assertFalse(ready.snapshot['deployment_authorized'])
        corrected=self.response(domain.exact(self.case,response.payload['target_id'],contract.TARGET),'changes_requested',response)
        self.assertEqual(corrected.payload['predecessor_id'],response.pk)
        with self.assertRaises(ValidationError):domain.gate_current(self.candidate,binding.verification)
        self.assertEqual(DeliverySource.objects.filter(pk=response.pk).count(),1)
        with self.assertRaises(ValidationError):delivery.readiness_inputs(self.d)
        correction_review=self.review(corrected)
        with self.assertRaises(ValidationError):self.export(corrected,correction_review)
        fresh=self.response(domain.exact(self.case,response.payload['target_id'],contract.TARGET),'approved',corrected)
        fresh_review=self.review(fresh)
        with self.assertRaises(ValidationError):self.export(fresh,fresh_review)
        successor=domain.export_gate(self.actor,self.case.pk,fresh.pk,fresh_review.pk,rev(self.case),
            previous_binding_id=binding.pk,correction_reason='SAMPLE reviewed corrected source replaces the earlier client gate')
        domain.gate_current(self.candidate,successor.verification)
        self.assertNotEqual(successor.verification.record_id,binding.verification.record_id)
        with self.assertRaises(ValidationError):delivery.readiness_inputs(self.d)
        delivery.record_release_request(self.actor,self.case.pk,self.d.pk,'SAMPLE-GLPI-corrected-client-proof',self.e['requirements'].pk,
            'SAMPLE new request reviewed against corrected client source',rev(self.case))
        self.gates(delivery.GLPI_GATES,'SAMPLE-GLPI-corrected-client-proof')
        refreshed=delivery.prepare_readiness(self.actor,self.case.pk,self.d.pk,rev(self.case))
        self.assertNotEqual(refreshed.pk,ready.pk)

    def test_existing_factory_wait_progresses_through_exact_client_proof_to_verified_readiness(self):
        import json
        from pathlib import Path
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.workflows import factory,factory_delivery
        value=json.loads(Path('fixtures/factory-delivery.json').read_text());value.pop('classification')
        cfg=draft_operator_policy(self.actor,self.case.pk,'OPS.factory_delivery_execution',value,self.e['policy_decision'].pk,timezone.now())
        transition(self.actor,cfg.pk,'validated');transition(self.actor,cfg.pk,'active')
        self.rule();self.plan();self.gates([kind for kind in delivery.UPSTREAM_GATES if kind!='uat_client'])
        work=factory_delivery.start(self.actor,self.case.pk,'SAMPLE-UAT-delivery-work',self.d.pk,'SAMPLE client testing release',rev(self.case))
        factory.run_until_wait(work.pk);work.refresh_from_db();self.assertEqual(work.status,'waiting')
        response=self.response();binding=self.export(response,self.review(response))
        delivery.record_release_request(self.actor,self.case.pk,self.d.pk,'SAMPLE-GLPI-UAT-factory',self.e['requirements'].pk,'SAMPLE actual release request',rev(self.case))
        self.gates(delivery.GLPI_GATES,'SAMPLE-GLPI-UAT-factory')
        factory.run_until_wait(work.pk);work.refresh_from_db();self.assertEqual(work.status,'verified',work.finding)
        self.assertFalse(factory_delivery.verify(work)['deployment_authorized'])
        self.client.force_login(self.actor)
        page=self.client.get(reverse('factory_detail',args=[work.pk]));self.assertContains(page,'Open client testing response')
        url=reverse('client_uat',args=[self.case.pk,self.d.pk])+'?work='+str(work.pk)
        self.assertContains(self.client.get(url),'Back to the work item')
        self.assertNotContains(self.client.get(url+'9'*30),'Back to the work item')

    def test_missing_rule_holds_only_confirmation_and_rejection_is_not_approval(self):
        response=self.response(outcome='rejected');inspection=self.check(response)
        with self.assertRaises(ValidationError):self.review(response,inspection)
        self.rule(qualification_mode=None,independent_review=None,agent_review_required=None,exact_mentions_required=None,proof_formats=[],workaround_mode=None)
        with self.assertRaises(ValidationError):self.review(response,inspection)
        self.rule();review=self.review(response,inspection)
        self.assertEqual(review.result['decision'],'rejected')
        self.client.force_login(self.actor)
        page=self.client.get(reverse('client_uat',args=[self.case.pk,self.d.pk]))
        self.assertContains(page,'The client has not approved this version')
        self.assertNotContains(page,'Use reviewed response in delivery checks')
        with self.assertRaises(ValidationError):self.export(response,review)
        self.assertFalse(ClientUATGateBinding.objects.exists())

    def test_independent_human_review_and_original_owner_revocation_before_storage(self):
        response=self.response();inspection=self.check(response)
        person=get_user_model().objects.create_user(username='independent-client-proof-reviewer')
        for action in ['case.read','delivery.read','engagement.read','client_uat.proof.read','client_uat.review','client_uat.inspect']:
            Grant.objects.create(case=self.case,user=person,action=action)
        role='uat-reviewer:'+str(uuid4())
        from apps.policy.services import register_reference,active_component
        current=active_component('D05.role_principal_assignments',self.case)
        ref=register_reference(self.actor,self.case.pk,role,'schema:psl/role-assignment/v1',{'role':'QA','user_id':person.pk},self.e['policy_decision'].pk)
        # Explicit SAMPLE source role; the witness does not become the Client.
        activate(self.actor,self.case,'D05.role_principal_assignments',[*current.envelope['value'],ref.ref],self.e['policy_decision'])
        # Renew the recorded authority by actual immutable source successors.
        target=self.target(domain.exact(self.case,response.payload['target_id'],contract.TARGET));response=self.response(target);inspection=self.check(response)
        self.rule(reviewer_ids=[person.pk],reviewer_role='QA',independent_review=True)
        with self.assertRaises(PermissionDenied):self.review(response,inspection)
        review=self.review(response,inspection,person);binding=self.export(response,review)
        Grant.objects.filter(case=self.case,user=self.actor,action='engagement.capture').update(active=False)
        with patch('adapters.case_uploads.bucket') as storage:
            with self.assertRaises((PermissionDenied,ValidationError)):domain.inspect_proof(person,self.case.pk,response.pk,rev(self.case))
            storage.assert_not_called()
        with self.assertRaises((PermissionDenied,ValidationError)):domain.gate_current(self.candidate,binding.verification)

    def test_real_agent_worker_is_source_linked_and_cannot_confirm_proof(self):
        self.rule(agent_review_required=True)
        with patch.dict('os.environ',{'OPENROUTER_MODEL':'synthetic/model','OPENROUTER_API_KEY':'synthetic-test-key'}):
            response=self.response();inspection=self.check(response)
            with self.assertRaises(ValidationError):self.review(response,inspection)
            with patch('adapters.openrouter.review',return_value={'summary':'SAMPLE document identifies the client and version.','quotes':['1'],'gaps':[]}) as provider:
                self.assertTrue(upload_jobs.run_once());provider.assert_called_once()
            with self.assertRaises(ValidationError):self.review(response,inspection)
            inspection=self.check(response);self.assertEqual(inspection.result['checks']['agent_jobs'][0]['status'],'draft')
            self.assertFalse(ClientUATGateBinding.objects.exists())
            self.assertEqual(domain.agent_drafts(self.actor,response)[0]['summary'],'SAMPLE document identifies the client and version.')
            binding=self.export(response,self.review(response,inspection))
            Grant.objects.filter(case=self.case,user=self.actor,action='agent.extract').update(active=False)
            self.assertEqual(domain.agent_drafts(self.actor,response),[])
            with self.assertRaises(ValidationError):domain.gate_current(self.candidate,binding.verification)

    def test_standard_upload_and_native_inspection_of_word_excel_and_pdf(self):
        from tests.test_upload_text import document
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
        text='SAMPLE Client Witness approved delivery-build.'
        writer=PdfWriter();page=writer.add_blank_page(width=600,height=800)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        stream=DecodedStreamObject();stream.set_data(('BT /F1 12 Tf 40 700 Td ('+text+') Tj ET').encode())
        page[NameObject('/Contents')]=writer._add_object(stream);pdf=BytesIO();writer.write(pdf)
        files=[('SAMPLE-client-proof.docx',document('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>'+text+'</w:t></w:r></w:p></w:document>')),
               ('SAMPLE-client-proof.xlsx',document('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><row><c r="A1" t="inlineStr"><is><t>'+text+'</t></is></c></row></worksheet>')),
               ('SAMPLE-client-proof.pdf',pdf.getvalue())]
        self.rule();target=self.target();previous=None
        for name,data in files:
            upload=upload_file(self.actor,self.case,SimpleUploadedFile(name,data))
            previous=self.response(target,previous=previous,proof=upload)
            inspection=self.check(previous)
            self.assertEqual(inspection.result['checks']['codes'],[])
            self.review(previous,inspection)

    def test_large_agent_result_is_measured_before_transfer_and_holds_only_qualification(self):
        from apps.agents.models import AgentJob
        from django.test.utils import CaptureQueriesContext
        self.rule(agent_review_required=True);response=self.response()
        upload=self.case.caseupload_set.get()
        AgentJob.objects.create(upload=upload,actor=self.actor,role='A07',status='draft',
            result={'summary':'PRIVATE-OVERSIZED-'*20000,'quotes':['not-a-source-quote'],'gaps':[],'source_sha256':upload.sha256})
        with CaptureQueriesContext(connection) as queries:inspection=self.check(response)
        self.assertEqual(inspection.result['checks']['agent_jobs'][0]['status'],'unavailable')
        self.assertTrue(any('OCTET_LENGTH' in q['sql'] and 'CASE WHEN' in q['sql'] for q in queries))
        self.assertEqual(domain.agent_drafts(self.actor,response),[])
        with self.assertRaises(ValidationError):self.review(response,inspection)
        self.assertEqual(DeliverySource.objects.filter(pk=response.pk).count(),1)

    def test_human_form_records_actual_response_and_rejects_missing_genuineness(self):
        self.rule();target=self.target();proof=self.proof();self.client.force_login(self.actor)
        url=reverse('client_uat',args=[self.case.pk,self.d.pk]);instant=timezone.now()-timedelta(minutes=30)
        data={'action':'response','revision':rev(self.case),'operation_key':str(uuid4()),'target':target.pk,'previous':0,
              'day':instant.date().isoformat(),'clock':instant.time().isoformat(),'zone':'UTC','outcome':'approved','proofs':[proof.pk]}
        self.assertContains(self.client.post(url,data),'This field is required')
        self.assertFalse(DeliverySource.objects.filter(dossier=self.d,kind=contract.RESPONSE).exists())
        data['genuine']='on';result=self.client.post(url,data)
        self.assertEqual(result.status_code,302)
        response=DeliverySource.objects.get(dossier=self.d,kind=contract.RESPONSE)
        self.assertEqual(response.payload['outcome'],'approved')
        self.assertFalse(ClientUATGateBinding.objects.exists())
        data.update(previous=response.pk,revision=rev(self.case),operation_key=str(uuid4()),day=(timezone.now()+timedelta(days=1)).date().isoformat())
        refused=self.client.post(url,data)
        self.assertContains(refused,'Response time must follow the actual test request')
        self.assertNotContains(refused,"[&#x27;Response time")
        self.assertContains(refused,'SAMPLE Client Witness')
        self.assertContains(refused,'Correct the testing request')

    def test_wrong_contact_version_workaround_and_retraction_preserve_history(self):
        self.rule(workaround_mode=None)
        response=self.response(outcome='approved_with_workaround',workaround='SAMPLE exact offline reconciliation for the stated version')
        inspection=self.check(response)
        with self.assertRaises(ValidationError):self.review(response,inspection)
        self.rule();review=self.review(response,inspection);binding=self.export(response,review)
        withdrawal=domain.withdraw_recording(self.actor,self.case.pk,response.pk,'SAMPLE recording selected wrong email',uuid4(),rev(self.case))
        self.assertEqual(withdrawal.result['decision'],'unknown')
        with self.assertRaises(ValidationError):domain.gate_current(self.candidate,binding.verification)
        bad=self.response(domain.exact(self.case,response.payload['target_id'],contract.TARGET),previous=response,proof=self.proof('SAMPLE Another Person approved a different build.'))
        with self.assertRaises(ValidationError):self.review(bad)
        self.assertTrue(DeliverySource.objects.filter(pk=response.pk).exists())
        self.assertFalse(contract.mentions('Joanna approved build-1234','Ann'))
        self.assertFalse(contract.mentions('build-1234','build-123'))
        self.assertFalse(contract.mentions('delivery/build','delivery-build',identifier=True))
        self.assertFalse(contract.mentions('delivery-build-v2','delivery-build',identifier=True))
        self.assertFalse(contract.mentions('DELIVERY-BUILD','delivery-build',identifier=True))
        self.assertTrue(contract.mentions('Approved delivery-build.','delivery-build',identifier=True))

    def test_nonmatching_build_slug_and_blank_workaround_cannot_qualify(self):
        self.rule();target=self.target()
        with self.assertRaises(ValidationError):self.response(target,outcome='approved_with_workaround',workaround='   ')
        response=self.response(target,proof=self.proof('SAMPLE Client Witness approved delivery-build-v2.'))
        inspection=self.check(response)
        self.assertFalse(inspection.result['checks']['version_mentioned'])
        with self.assertRaises(ValidationError):self.review(response,inspection)

    def test_old_file_check_protocol_stays_history_until_fresh_exact_check_and_human_review(self):
        self.rule();response=self.response()
        # Execute the actual native check with its prior persisted protocol
        # identity to model a retained v1 receipt; no internal service is mocked.
        with patch.object(contract,'INSPECTION',contract.LEGACY_INSPECTION):legacy=self.check(response)
        with self.assertRaises(ValidationError):self.review(response,legacy)
        current=self.check(response);self.assertNotEqual(current.pk,legacy.pk)
        self.assertEqual(current.adapter,'client-uat-evidence-check/v2')
        review=self.review(response,current);self.export(response,review)
        self.assertTrue(response.verifications.filter(pk=legacy.pk,adapter=contract.LEGACY_INSPECTION).exists())

    def test_nomination_needs_actual_private_proof_access_and_revocation_holds_before_file_read(self):
        grant=Grant.objects.get(case=self.case,user=self.actor,action='client_uat.proof.read');grant.active=False;grant.save()
        with self.assertRaises((PermissionDenied,ValidationError)),transaction.atomic():self.rule()
        response=self.response()
        with patch('adapters.case_uploads.bucket') as storage:
            with self.assertRaises(PermissionDenied):self.check(response)
            storage.assert_not_called()
        grant.active=True;grant.save();self.rule();review=self.review(response);binding=self.export(response,review)
        grant.active=False;grant.save()
        with self.assertRaises(PermissionDenied):domain.gate_current(self.candidate,binding.verification)

    def test_validation_private_downloads_ui_drafts_and_postgres_history_guards(self):
        self.rule();response=self.response();review=self.review(response);binding=self.export(response,review)
        self.client.force_login(self.actor)
        url=reverse('client_uat',args=[self.case.pk,self.d.pk])
        page=self.client.get(url);self.assertEqual(page.status_code,200);self.assertContains(page,'Client proof confirmed')
        delivery_page=self.client.get(reverse('delivery',args=[self.case.pk]))
        self.assertNotIn(contract.TARGET,delivery_page.context['kinds']);self.assertNotIn(contract.RESPONSE,delivery_page.context['kinds'])
        private=reverse('client_uat_proof',args=[self.case.pk,response.pk,response.payload['proofs'][0]['id']])
        download=self.client.get(private);self.assertEqual(download.status_code,200);self.assertEqual(download['Cache-Control'],'no-store')
        outsider=get_user_model().objects.create_user(username='ordinary-delivery-reader')
        for action in ['case.read','delivery.read','engagement.read']:Grant.objects.create(user=outsider,case=self.case,action=action)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(private).status_code,403)
        self.assertNotContains(self.client.get(url),'Download SAMPLE-client-proof.txt')
        self.client.force_login(self.actor)
        self.assertEqual(self.client.get(reverse('client_uat_rules',args=[self.case.pk])).status_code,200)
        for query in [lambda:ClientUATGateBinding.objects.filter(pk=binding.pk).update(snapshot={}),
                      lambda:DeliverySource.objects.filter(pk=response.pk).update(payload={})]:
            with self.assertRaises(DatabaseError),transaction.atomic():query()
        with self.assertRaises(ValidationError):domain.record_response(self.actor,self.case.pk,response.payload['target_id'],timezone.now(),'approved',False,'',None,None,[response.payload['proofs'][0]['id']],response.pk,uuid4(),rev(self.case))
        with self.assertRaises(ValidationError):delivery.verify_source(self.actor,self.case.pk,response.pk,rev(self.case))
        from apps.pmo.gates import verify_gate
        with self.assertRaises(ValidationError):verify_gate(self.actor,self.case.pk,binding.verification.record_id,rev(self.case))

    def test_owner_rule_form_saves_nullable_draft_then_uses_native_validation(self):
        self.client.force_login(self.actor)
        url=reverse('client_uat_rules',args=[self.case.pk])
        page=self.client.get(url);self.assertContains(page,'Not decided')
        result=self.client.post(url,{'revision':rev(self.case),'operation_key':str(uuid4()),'head':0,
            'qualification_mode':'','reviewer_role':'','independent_review':'','agent_review_required':'',
            'exact_mentions_required':'','workaround_mode':'','evidence':self.e['policy_decision'].pk})
        self.assertEqual(result.status_code,302)
        from apps.policy.models import Configuration
        from apps.policy.services import reference_values
        draft=Configuration.objects.get(case=self.case,component=COMPONENT)
        value=reference_values(draft)[0]
        self.assertIsNone(value['independent_review']);self.assertEqual(value['reviewer_ids'],[])
        transition(self.actor,draft.pk,'validated');transition(self.actor,draft.pk,'active')
        response=self.response();self.assertEqual(response.kind,contract.RESPONSE)
        with self.assertRaises((ValidationError,PermissionDenied)):self.review(response)
        self.assertEqual(self.client.get(url).status_code,200)

    def test_incomplete_owner_draft_keeps_configuration_repair_available(self):
        from apps.policy.approval_drafts import draft_approval_policy
        cfg=draft_approval_policy(self.actor,self.case.pk,COMPONENT,{},self.e['policy_decision'].pk,timezone.now())
        self.client.force_login(self.actor)
        response=self.client.get(reverse('client_uat_rules',args=[self.case.pk]))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'The earlier draft needs repair')
        self.assertContains(response,'Save proof rule draft')
        with self.assertRaises(ValidationError):transition(self.actor,cfg.pk,'validated')

    def test_rebind_requires_reason_after_exporter_loses_access_and_new_review_stales_it(self):
        self.rule();response=self.response();review=self.review(response);old=self.export(response,review)
        replacement=get_user_model().objects.create_user(username='sample-replacement-gate-recorder')
        for action in ['case.read','delivery.read','engagement.read','client_uat.export','pmo.gate_record','pmo.gate_verify']:
            Grant.objects.create(case=self.case,user=replacement,action=action)
        Grant.objects.filter(case=self.case,user=self.actor,action='client_uat.export').update(active=False)
        self.client.force_login(replacement)
        refused=self.client.post(reverse('client_uat',args=[self.case.pk,self.d.pk]),{'action':'export',
            'revision':rev(self.case),'operation_key':str(uuid4()),'response':response.pk,'review':review.pk,'previous_binding':old.pk})
        self.assertContains(refused,'Review the earlier delivery handoff and give a reason for replacing it')
        self.assertNotContains(refused,'__all__')
        self.assertContains(refused,'The earlier delivery handoff needs a reviewed replacement')
        with self.assertRaises(ValidationError):domain.export_gate(replacement,self.case.pk,response.pk,review.pk,rev(self.case))
        newer=domain.export_gate(replacement,self.case.pk,response.pk,review.pk,rev(self.case),previous_binding_id=old.pk,correction_reason='SAMPLE new current recorder reviewed the same source')
        self.assertNotEqual(newer.pk,old.pk);domain.gate_current(self.candidate,newer.verification)
        self.review(response)
        with self.assertRaises(ValidationError):domain.gate_current(self.candidate,newer.verification)
        self.assertEqual(ClientUATGateBinding.objects.count(),2)

    def test_existing_department_owned_client_reference_cannot_be_replaced_by_witness(self):
        from apps.policy.services import register_reference,active_component
        from apps.policy.approval_validators import ROUTES,CONTRACTS
        from apps.policy.approval_drafts import draft_approval_policy
        from apps.pmo import approvals
        from tests.approval_helpers import evidence,capture,observe
        person=get_user_model().objects.create_user(username='sample-external-client-source-owner')
        Grant.objects.bulk_create([Grant(case=self.case,user=person,action=x) for x in ACTIONS])
        for user in [self.actor,person]:Grant.objects.create(case=self.case,user=user,action='approval.source.read:sample-client-source')
        existing=active_component('D05.role_principal_assignments',self.case)
        ref=register_reference(self.actor,self.case.pk,'sample-client-role','schema:psl/role-assignment/v1',{'role':'Client','user_id':person.pk},self.e['policy_decision'].pk)
        activate(self.actor,self.case,'D05.role_principal_assignments',[*existing.envelope['value'],ref.ref],self.e['policy_decision'])
        values={ROUTES:{'lease_seconds':30,'max_attempts':2,'routes':[{'kind':'uat_client','gate_kind':'uat_client','source_owner':'Client',
            'owner_id':person.pk,'owner_role':'Client','source_actor_ref':'sample-client-owner','system':'sample-client-source','route_mode':'internal_inbox_v1'}]},
            CONTRACTS:{'contracts':[{'kind':'uat_client','contract_evidence_id':self.e['policy_decision'].pk,'mode':'owner_supplied_reference_v1',
                'signature_assurance':'reference_only','ordering':'decided_at_monotonic_v1','max_age_seconds':3600,
                'required_subject_fields':['build_ref'],'reminders_enabled':False,'minimum_reminder_interval_seconds':60,'maximum_reminders':0}]}}
        for component,value in values.items():
            cfg=draft_approval_policy(self.actor,self.case.pk,component,value,self.e['policy_decision'].pk,timezone.now()-timedelta(seconds=1))
            transition(self.actor,cfg.pk,'validated');transition(self.actor,cfg.pk,'active')
        review_source=self.evidence('approval_contract_review','SAMPLE source owner reviews the exact client evidence contract')
        approvals.review_contract(person,self.case.pk,'uat_client',review_source.pk)
        request_source=self.evidence('approval_request','SAMPLE request for exact client version decision')
        request=approvals.create_request(self.actor,self.case.pk,'SAMPLE-owned-client-decision',self.candidate.pk,'uat_client',self.candidate.reference,None,request_source.pk)
        f={'actor':self.actor,'owner':person,'case':self.case,'request':request}
        source=capture(f,{'kind':'uat_client','system':'sample-client-source','source_owner':'Client','source_actor_ref':'sample-client-owner','critical_defects':None})
        observation=observe(f,source);owned=approvals.export_gate(person,self.case.pk,observation.pk)
        self.rule();target=self.target();proof=self.proof()
        response=domain.record_response(self.actor,self.case.pk,target.pk,source.payload['decided_at'],'approved',True,'SAMPLE same exact source',None,
            source.external_ref,[proof.pk],None,uuid4(),rev(self.case))
        review=self.review(response);bound=self.export(response,review)
        self.assertEqual(bound.verification_id,owned.verification_id)
        approvals.gate_current(self.candidate,'uat_client',bound.verification)
        Grant.objects.filter(case=self.case,user=person,action='approval.source.read:sample-client-source').update(active=False)
        with self.assertRaises((ValidationError,PermissionDenied)):approvals.gate_current(self.candidate,'uat_client',bound.verification)
        with self.assertRaises((ValidationError,PermissionDenied)):self.export(response,review)


class ClientUATConcurrencyTests(ClientUATFixture,TransactionTestCase):
    def setUp(self):self.setup_uat()

    def test_two_connections_record_one_current_response_and_keep_the_loser_reviewable(self):
        target=self.target();proof=self.proof();expected=rev(self.case)
        def submit():
            close_old_connections()
            try:
                return domain.record_response(self.actor,self.case.pk,target.pk,timezone.now()-timedelta(hours=1),'approved',True,
                    'SAMPLE concurrent client response',None,None,[proof.pk],None,uuid4(),expected).pk
            except ValidationError:return 'stale'
            finally:connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:submit(),range(2)))
        self.assertEqual(results.count('stale'),1)
        self.assertEqual(DeliverySource.objects.filter(dossier=self.d,kind=contract.RESPONSE).count(),1)
