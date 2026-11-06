from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase
from apps.core.services import add_evidence
from apps.core.models import Case
from apps.identity.models import Grant
from apps.pmo.gates import register_candidate, record_gate, verify_gate, draft_gate_packet, gate_summary
from apps.pmo.models import GateRecord, GateVerification
from apps.documents.controlled import request_review, review_version, reserve_publication, preflight
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationJob, PublicationReceipt
from apps.agents.documents import check_candidate
from adapters.pmo_gates import SyntheticGateAdapter
from .helpers import rev
from .document_helpers import publication_fixture

class PMOGateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor,cls.case,cls.owner,cls.source,cls.template,cls.recipient,_,_=publication_fixture()
        cls.requirements=add_evidence(cls.actor,cls.case.pk,'requirements','Candidate requirements version 1','synthetic:requirements')
        cls.candidate=register_candidate(cls.actor,cls.case.pk,'build-123',cls.requirements.pk,rev(cls.case))

    def gate(self,kind='qa_exit'):
        return record_gate(self.actor,self.case.pk,self.candidate.pk,kind,'source:'+kind,self.source.pk,rev(self.case))

    def test_reported_evidence_is_not_source_verified_or_release_authority(self):
        gate=self.gate()
        self.assertTrue(any('qa_exit: unverified' in line for line in gate_summary(self.candidate)))
        run=check_candidate(self.actor,self.case.pk,self.candidate.pk)
        self.assertFalse(run.result['release_authorized'])
        self.assertEqual(run.result['gate_manifest'][0]['record'],gate.pk)
        self.assertEqual(GateVerification.objects.count(),0)

    def test_candidate_packet_connects_gate_adapter_human_review_and_publication(self):
        gate=self.gate();verification=verify_gate(self.actor,self.case.pk,gate.pk,rev(self.case))
        self.assertEqual(verification.result['decision'],'accepted')
        packet=draft_gate_packet(self.actor,self.case.pk,self.candidate.pk,self.template.pk,'client',rev(self.case))
        self.assertEqual(preflight(packet),[])
        request_review(self.actor,self.case.pk,packet.pk,rev(self.case))
        review_version(self.actor,self.case.pk,packet.pk,'approve','Verified outward gate status summary',rev(self.case))
        reserve_publication(self.actor,self.case.pk,packet.pk,rev(self.case));run_publication_once()
        self.assertEqual(PublicationJob.objects.get().status,'confirmed')
        text=str(PublicationReceipt.objects.get().payload)
        self.assertIn('qa_exit: accepted',text);self.assertIn('not release authorization',text)
        self.assertNotIn('source:qa_exit',text)

    def test_unknown_critical_defects_never_become_zero_or_qa_exit_approval(self):
        gate=self.gate()
        class Unknown(SyntheticGateAdapter):
            def read(self,record):return dict(super().read(record),critical_defects=None)
        result=verify_gate(self.actor,self.case.pk,gate.pk,rev(self.case),Unknown())
        self.assertIsNone(result.result['critical_defects']);self.assertEqual(result.result['decision'],'unknown')
        class Defects(SyntheticGateAdapter):
            def read(self,record):return dict(super().read(record),critical_defects=1)
        result=verify_gate(self.actor,self.case.pk,gate.pk,rev(self.case),Defects())
        self.assertEqual(result.result['decision'],'rejected')

    def test_wrong_candidate_or_owner_from_adapter_is_rejected(self):
        gate=self.gate()
        class Wrong(SyntheticGateAdapter):
            def read(self,record):return dict(super().read(record),source_owner='PMO')
        with self.assertRaises(ValidationError):verify_gate(self.actor,self.case.pk,gate.pk,rev(self.case),Wrong())
        self.assertFalse(GateVerification.objects.exists())

    def test_new_gate_or_verification_invalidates_existing_packet(self):
        gate=self.gate();verify_gate(self.actor,self.case.pk,gate.pk,rev(self.case))
        packet=draft_gate_packet(self.actor,self.case.pk,self.candidate.pk,self.template.pk,'client',rev(self.case))
        request_review(self.actor,self.case.pk,packet.pk,rev(self.case))
        review_version(self.actor,self.case.pk,packet.pk,'approve','Reviewed',rev(self.case))
        reserve_publication(self.actor,self.case.pk,packet.pk,rev(self.case))
        self.gate('uat_client');run_publication_once()
        self.assertEqual(PublicationJob.objects.get().status,'held')
        self.assertFalse(PublicationReceipt.objects.exists())

    def test_duplicate_source_and_cross_case_capture_are_rejected(self):
        self.gate()
        with self.assertRaises(ValidationError):self.gate()
        other=Case.objects.create(title='Other',tenant='other',kind='project')
        with self.assertRaises(PermissionDenied):record_gate(self.actor,other.pk,self.candidate.pk,'qa_exit','x',self.source.pk,1)
        self.assertEqual(GateRecord.objects.count(),1)

    def test_operational_source_capture_does_not_use_synthetic_verification(self):
        gate=self.gate();Case.objects.filter(pk=self.case.pk).update(synthetic=False)
        with self.assertRaises(ValidationError):verify_gate(self.actor,self.case.pk,gate.pk,rev(self.case))
        self.assertEqual(GateRecord.objects.count(),1);self.assertFalse(GateVerification.objects.exists())

    def test_staff_gate_form_and_candidate_preflight(self):
        self.client.force_login(self.actor);url=f'/cases/{self.case.pk}/documents/'
        result=self.client.post(url,{'action':'gate','candidate':self.candidate.pk,'kind':'engineering_go',
            'external_ref':'engineering:go-123','evidence':self.source.pk,'revision':rev(self.case)})
        self.assertEqual(result.status_code,302)
        self.assertEqual(self.client.post(url,{'action':'gate_check','candidate':self.candidate.pk,'revision':rev(self.case)}).status_code,302)
        self.assertContains(self.client.get(url),'engineering:go-123')
