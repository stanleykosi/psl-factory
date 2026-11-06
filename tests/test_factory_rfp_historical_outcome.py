"""Factory/SQL regression for a real submitted offer after unsent rework and staff turnover."""
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection
from django.test import TestCase
from django.utils import timezone
from apps.core.services import add_evidence
from apps.documents.models import PublicationReceipt
from apps.identity.models import Grant
from apps.pmo import rfp
from apps.pmo.models import RFPResponse,RFPSubmission,RFPDisposition,RFPCase,Baseline
from apps.workflows import factory,factory_rfp
from apps.workflows.models import FactoryAttempt
from tests import factory_rfp_helpers as helpers
from tests.helpers import rev


class FactoryRFPHistoricalOutcomeTests(TestCase):
    def test_actual_submitted_offer_verifies_after_unsent_draft_and_old_grant_withdrawal(self):
        self.assertEqual(connection.vendor,'postgresql')
        f=helpers.configured();actor,case,evidence=f['actor'],f['case'],f['evidence']
        work=helpers.start(f);submitted_response,document=helpers.reviewed_document(f,work)
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(work.status,'waiting',work.finding)
        submitted=RFPSubmission.objects.get(response=submitted_response,version=document)
        receipt_ids=list(PublicationReceipt.objects.order_by('pk').values_list('pk',flat=True))
        self.assertEqual(submitted.receipt_ids,receipt_ids);self.assertEqual(len(receipt_ids),1)
        original=(work.actor_id,work.source_head_id,work.policy_id,work.budget_limit);spent=work.budget_used
        wording=add_evidence(actor,case.pk,'rfp_response','Newer unsent RFP wording remains a draft','synthetic:unsent-factory-follow-up')
        unsent=rfp.prepare_response(actor,case.pk,wording.pk,submitted_response.matrix,
            {kind:evidence[kind].pk for kind in ['requirements','plan','costing']},rev(case),
            public_terms_id=evidence['rfp_commercial_terms'].pk)
        self.assertFalse(unsent.submissions.exists());self.assertEqual(RFPSubmission.objects.count(),1)
        withdrawn=['rfp.prepare','rfp.review','commercial.decide','document.review_controlled',
            *['rfp.contribute:'+team for team in rfp.TEAMS]]
        Grant.objects.filter(case=case,user=actor,action__in=withdrawn).update(active=False)
        for action in ['case.read','rfp.read','factory.start','evidence.add','factory.read','factory.execute','rfp.outcome','rfp.dispose']:
            self.assertTrue(Grant.objects.filter(case=case,user=actor,action=action,active=True).exists(),action)
        with self.assertRaises((ValidationError,PermissionDenied)):rfp.source_snapshot(RFPCase.objects.get(case=case))
        outcome=rfp.outcome(actor,case.pk,submitted.pk,'won',timezone.now(),'Client',evidence['rfp_outcome'].pk,
            'Current owner confirmed the exact previously delivered response, not the unsent draft',rev(case))
        self.assertEqual(factory_rfp.submission_for(work).pk,submitted.pk)
        self.assertEqual(factory_rfp.response_for(work).pk,submitted_response.pk)
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(work.status,'verified',work.finding)
        verified=factory_rfp.verify(work)
        self.assertTrue(verified['verified']);self.assertEqual(verified['submission'],submitted.pk)
        self.assertEqual(verified['response'],submitted_response.pk)
        self.assertEqual(verified['receipt_ids'],receipt_ids)
        disposition=RFPDisposition.objects.get(rfp=submitted_response.rfp)
        self.assertEqual(disposition.outcome_id,outcome.pk);self.assertEqual(disposition.kind,'route_a')
        self.assertEqual(disposition.snapshot['response'],submitted_response.pk)
        self.assertEqual(disposition.snapshot['commercial_sources'],submitted_response.commercial.sources)
        self.assertFalse(disposition.snapshot['baseline_imported']);self.assertFalse(Baseline.objects.exists())
        self.assertEqual(RFPCase.objects.get(case=case).current_response_id,unsent.pk)
        self.assertEqual(RFPResponse.objects.count(),2);self.assertFalse(unsent.submissions.exists())
        self.assertEqual(list(PublicationReceipt.objects.order_by('pk').values_list('pk',flat=True)),receipt_ids)
        self.assertEqual((work.actor_id,work.source_head_id,work.policy_id,work.budget_limit),original)
        self.assertGreater(work.budget_used,spent)
        self.assertFalse(Grant.objects.filter(case=case,user=actor,action__in=withdrawn,active=True).exists())
        observed=FactoryAttempt.objects.filter(activity__work=work,activity__kind='ACT13',phase='observed').latest('pk')
        self.assertEqual(observed.result['submission'],submitted.pk);self.assertEqual(observed.result['response'],submitted_response.pk)
