"""P37/P39 native document integrity prerequisite; not autonomous handover acceptance."""
from django.core.exceptions import ValidationError
from django.test import TestCase
from apps.documents.controlled import create_version
from apps.documents.models import PublicationReceipt
from apps.pmo.delivery_closure import acknowledge_handover,closure_inputs
from apps.pmo.delivery_documents import draft_delivery_document
from apps.pmo.models import DeliveryRecord,DeliveryDocumentBinding
from apps.agents.delivery import investigate_delivery
from tests.helpers import rev
from tests.test_delivery import DeliveryFixture


class HandoverCurrentDocumentTests(DeliveryFixture,TestCase):
    @classmethod
    def setUpTestData(cls):
        f=DeliveryFixture();f.setup_delivery()
        for key,value in vars(f).items():setattr(cls,key,value)

    def supersede(self,v):
        return create_version(self.actor,self.case.pk,v.template_id,v.document.title,v.audience,v.fields,
            rev(self.case),document_id=v.document_id)

    def test_superseded_handover_cannot_clear_or_record_recipient_gaps_and_new_package_recovers(self):
        self.accepted();self.archive();data={kind:self.evidence(kind).pk for kind in ['support_document','escalation_document']}
        v=draft_delivery_document(self.actor,self.case.pk,self.d.pk,'handover',self.t.pk,data,rev(self.case));receipt=self.publish(v)
        gap=acknowledge_handover(self.actor,self.case.pk,self.d.pk,receipt.pk,'gaps',self.e['requirements'].pk,'Synthetic missing support detail',rev(self.case))
        self.supersede(v)
        for status in ['gaps','received']:
            with self.assertRaisesMessage(ValidationError,'newer document revision'):
                acknowledge_handover(self.actor,self.case.pk,self.d.pk,receipt.pk,status,self.e['requirements'].pk,'Cannot acknowledge obsolete package',rev(self.case))
        self.client.force_login(self.actor)
        response=self.client.post(f'/cases/{self.case.pk}/delivery/',{'action':'handover','revision':rev(self.case),'dossier':self.d.pk,
            'receipt':receipt.pk,'status':'received','evidence':self.e['requirements'].pk,'note':'Obsolete package remains blocked'})
        self.assertContains(response,'newer document revision');self.assertEqual(DeliveryRecord.objects.filter(dossier=self.d,kind='handover').count(),1)
        self.assertTrue(DeliveryRecord.objects.filter(pk=gap.pk,data__status='gaps').exists());self.assertTrue(PublicationReceipt.objects.filter(pk=receipt.pk).exists())
        successor=draft_delivery_document(self.actor,self.case.pk,self.d.pk,'handover',self.t.pk,data,rev(self.case));new_receipt=self.publish(successor)
        received=acknowledge_handover(self.actor,self.case.pk,self.d.pk,new_receipt.pk,'received',self.e['requirements'].pk,'Current exact package received',rev(self.case))
        self.assertNotEqual(new_receipt.pk,receipt.pk);self.assertEqual(received.data['receipt_id'],new_receipt.pk)
        self.assertTrue(DeliveryRecord.objects.filter(pk=gap.pk).exists());self.assertFalse(DeliveryRecord.objects.filter(dossier=self.d,kind='closure').exists())

    def test_closure_and_agent_readback_hold_old_accepted_package_then_current_receipt_recovers(self):
        data=self.closing();before=closure_inputs(self.d,data)
        draft_delivery_document(self.actor,self.case.pk,self.d.pk,'closure',self.t.pk,data,rev(self.case))
        binding=DeliveryDocumentBinding.objects.get(dossier=self.d,purpose='handover');old=binding.version
        self.supersede(old)
        with self.assertRaisesMessage(ValidationError,'newer document revision'):closure_inputs(self.d,data)
        result=investigate_delivery(self.actor,self.case.pk,self.d.pk,rev(self.case)).result
        self.assertIn('newer document revision',result['checks']['closure']['findings'])
        self.assertTrue(DeliveryRecord.objects.filter(pk=before['handover_ids'][0]).exists())
        successor=draft_delivery_document(self.actor,self.case.pk,self.d.pk,'handover',self.t.pk,binding.data,rev(self.case));receipt=self.publish(successor)
        with self.assertRaisesMessage(ValidationError,'gap resolution'):closure_inputs(self.d,data)
        received=acknowledge_handover(self.actor,self.case.pk,self.d.pk,receipt.pk,'received',self.e['requirements'].pk,'Current replacement handover received',rev(self.case))
        after=closure_inputs(self.d,data);self.assertEqual(after['handover_ids'],[received.pk])
        self.assertNotEqual(after['handover_ids'],before['handover_ids']);self.assertEqual(after['finance_confirmation_id'],before['finance_confirmation_id'])
        self.assertFalse(after['debt_waived']);self.assertFalse(after['deployment_authorized'])
