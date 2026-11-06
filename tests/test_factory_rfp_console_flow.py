"""Primary RFP console drives native decisions and one exact recipient receipt."""
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.agents.models import AgentRun
from apps.documents.models import Publication,PublicationReceipt,ControlledReview
from apps.pmo.models import (RFPResponse,RFPReview,RFPSubmission,RFPOutcome,RFPDisposition,
    CommercialDecision,Baseline)
from apps.workflows import factory_rfp
from apps.workflows.models import FactoryWork
from tests import factory_rfp_helpers as helpers
from tests.helpers import rev


class FactoryRFPConsoleFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.data=helpers.configured()

    def test_structured_intake_primary_decisions_and_customer_outcome_keep_one_native_chain(self):
        self.assertEqual(connection.vendor,'postgresql')
        f=self.data;actor=f['actor'];case=f['case'];e=f['evidence'];declared=f['payload']
        self.client.force_login(actor)
        create_url=reverse('factory_create')+'?definition=rfp-response/v1&case='+str(case.pk)
        intake={'definition':'rfp-response/v1','case':case.pk,'key':'RFP-CONSOLE-1','reference':'Cited customer response',
            'revision':rev(case),'response_evidence':declared['response_evidence'],'public_terms':declared['public_terms'],
            'lessons':declared['lessons'],**declared['sources'],
            'requirements-TOTAL_FORMS':'1','requirements-INITIAL_FORMS':'0','requirements-MIN_NUM_FORMS':'0','requirements-MAX_NUM_FORMS':'100',
            **{'requirements-0-'+key:value for key,value in declared['matrix'][0].items()}}
        started=self.client.post(create_url,intake)
        self.assertEqual(started.status_code,302,getattr(started,'context',None))
        work=FactoryWork.objects.get(case=case,key='RFP-CONSOLE-1')
        self.assertEqual(started.url,reverse('factory_detail',args=[work.pk]))
        self.assertEqual(factory_rfp.inputs(work)['matrix'],declared['matrix'])
        self.assertEqual(FactoryWork.objects.filter(case=case).count(),1)
        starter=work.actor_id;head=work.source_head_id
        url=reverse('factory_detail',args=[work.pk])+'?queue=decisions&q=Cited+customer'

        def post(action,**fields):
            work.refresh_from_db()
            result=self.client.post(url,{'action':action,'revision':work.revision,'case_revision':rev(case),**fields})
            self.assertEqual(result.status_code,302,getattr(result,'context',None))
            self.assertEqual(result.url,url)
            work.refresh_from_db()
            return result

        post('advance')
        response=factory_rfp.response_for(work)
        self.assertIsNotNone(response,work.finding)
        self.assertEqual(work.status,'waiting',work.finding)
        investigation=AgentRun.objects.filter(case=case,provider='deterministic-rfp-investigation-v1').first()
        self.assertIsNotNone(investigation)
        self.assertTrue(investigation.result['citations'])
        self.assertFalse(investigation.result['approval_granted']);self.assertFalse(investigation.result['submission_dispatched'])
        self.assertEqual(RFPReview.objects.filter(response=response).count(),0)
        self.assertEqual(CommercialDecision.objects.filter(revision=response.commercial).count(),0)
        self.assertFalse(Publication.objects.filter(version__document__case=case).exists())
        page=self.client.get(url)
        self.assertContains(page,'PMO Lead response review');self.assertContains(page,'Engineering Lead response review')
        self.assertContains(page,'RFP RESPONSE AND CUSTOMER OUTCOME')
        self.assertEqual(page['Cache-Control'],'no-store')

        for role in ['Engineering Lead','PMO Lead']:
            post('response',target=response.pk,role=role,verdict='approve',evidence=e['policy_decision'].pk,
                note='Actual configured human review of the exact cited response')
        self.assertEqual(RFPReview.objects.filter(response=response).count(),2)
        # A valid human identity cannot bypass the source-defined costing sequence.
        work.refresh_from_db()
        premature=self.client.post(url,{'action':'commercial','revision':work.revision,'case_revision':rev(case),
            'target':response.commercial_id,'role':'CEO','verdict':'approve','note':'Premature decision must not bypass PM and Head of PMO'})
        self.assertEqual(premature.status_code,200)
        self.assertEqual(CommercialDecision.objects.filter(revision=response.commercial).count(),0)
        for role in ['PM','Head of PMO','CEO']:
            post('commercial',target=response.commercial_id,role=role,verdict='approve',
                note='Actual configured costing decision in the required order')
        self.assertEqual(list(CommercialDecision.objects.filter(revision=response.commercial).order_by('pk').values_list('role',flat=True)),
            ['PM','Head of PMO','CEO'])

        post('advance')
        document=factory_rfp.document_for(work,f['value'])
        self.assertIsNotNone(document,work.finding)
        self.assertEqual(work.status,'waiting',work.finding)
        self.assertEqual(ControlledReview.objects.filter(version=document).count(),0)
        self.assertFalse(PublicationReceipt.objects.filter(publication__version=document).exists())
        self.assertContains(self.client.get(url),'Final client response review')
        post('document',target=document.pk,role='PMO Lead',verdict='approve',
            note='Actual human review of this exact outward client projection')
        self.assertEqual(ControlledReview.objects.filter(version=document).count(),1)

        post('advance')
        publication=Publication.objects.get(version=document)
        submission=RFPSubmission.objects.get(response=response)
        receipts=list(PublicationReceipt.objects.filter(publication=publication).order_by('pk').values_list('pk',flat=True))
        self.assertEqual(len(receipts),1);self.assertEqual(submission.receipt_ids,receipts)
        self.assertEqual(publication.factory_work_id,work.pk)
        self.assertEqual(work.status,'waiting',work.finding)
        self.assertFalse(RFPDisposition.objects.filter(rfp=response.rfp).exists())
        self.assertContains(self.client.get(url),'Record actual customer outcome')
        spent=work.budget_used
        post('outcome',target=submission.pk,role='Client',verdict='won',observed_at=timezone.now().isoformat(),
            evidence=e['rfp_outcome'].pk,note='Actual evidenced synthetic customer award')
        post('advance')
        self.assertEqual(work.status,'verified',work.finding)
        disposition=RFPDisposition.objects.get(rfp=response.rfp)
        self.assertEqual(disposition.kind,'route_a');self.assertFalse(disposition.snapshot['baseline_imported'])
        self.assertEqual(disposition.outcome_id,RFPOutcome.objects.get(submission=submission).pk)
        self.assertFalse(Baseline.objects.filter(case=case).exists())
        self.assertTrue(factory_rfp.verify(work)['verified'])
        self.assertEqual((work.actor_id,work.source_head_id),(starter,head))
        self.assertGreater(work.budget_used,spent);self.assertEqual(work.budget_limit,30000)
        self.assertEqual(RFPResponse.objects.filter(rfp__case=case).count(),1)
        self.assertEqual(RFPSubmission.objects.filter(response__rfp__case=case).count(),1)
        self.assertEqual(Publication.objects.filter(version__document__case=case).count(),1)
        self.assertEqual(list(PublicationReceipt.objects.filter(publication=publication).values_list('pk',flat=True)),receipts)
        verified=self.client.get(url)
        self.assertContains(verified,'Verified outcome')
        self.assertContains(verified,'The recorded win starts Route A')
        self.assertNotContains(verified,'name="action" value="advance"',html=False)
        # A delayed original intake retry reads its existing completed work; it
        # cannot reopen the won RFP, reset allowance or create another effect.
        repeated=self.client.post(create_url,intake)
        self.assertEqual(repeated.status_code,302,getattr(repeated,'context',None))
        self.assertEqual(repeated.url,reverse('factory_detail',args=[work.pk]))
        self.assertEqual(FactoryWork.objects.filter(case=case).count(),1)
        self.assertEqual(PublicationReceipt.objects.filter(publication=publication).count(),1)
