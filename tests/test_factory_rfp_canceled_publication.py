"""A canceled unsent RFP reservation yields a fresh reviewed outward version."""
from django.db import connection
from django.test import TestCase
from django.utils import timezone
from apps.core.models import Evidence
from apps.documents.controlled import request_review,review_version
from apps.documents.delivery import operate_publication,run_publication_once
from apps.documents.models import ControlledReview,Publication,PublicationReceipt,Version
from apps.pmo import rfp_documents
from apps.pmo.models import CommercialDecision,RFPDisposition,RFPResponse,RFPReview,RFPSubmission
from apps.workflows import factory,factory_rfp
from tests import factory_rfp_helpers as helpers
from tests.helpers import rev
from tests import test_rfp as native


class FactoryRFPCanceledPublicationTests(TestCase):
    def test_preexisting_reviewed_native_response_is_reused_without_duplicate_decisions_or_document(self):
        data=helpers.configured();actor=data['actor'];case=data['case'];evidence=data['evidence']
        response=native.response(actor,case,evidence)
        native.approve(actor,case,evidence,response)
        document=rfp_documents.draft(actor,case.pk,response.pk,data['template'].pk,data['route']['key'],rev(case))
        request_review(actor,case.pk,document.pk,rev(case))
        review_version(actor,case.pk,document.pk,'approve','Exact native outward version reviewed before factory intake',rev(case))
        before=(RFPResponse.objects.count(),RFPReview.objects.count(),CommercialDecision.objects.count(),Version.objects.count(),ControlledReview.objects.count())
        self.assertEqual(before,(1,2,3,1,1))
        self.assertFalse(Publication.objects.exists())
        work=helpers.start(data)
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(factory_rfp.response_for(work).pk,response.pk)
        self.assertEqual(factory_rfp.document_for(work,data['value']).pk,document.pk)
        self.assertEqual(before,(RFPResponse.objects.count(),RFPReview.objects.count(),CommercialDecision.objects.count(),Version.objects.count(),ControlledReview.objects.count()))
        publication=Publication.objects.get(version=document)
        self.assertEqual(publication.factory_work_id,work.pk)
        self.assertEqual(publication.factory_source_id,work.source_head_id)
        self.assertEqual(publication.job.status,'confirmed')
        self.assertEqual(PublicationReceipt.objects.count(),1)
        submission=RFPSubmission.objects.get(response=response)
        self.assertEqual(submission.version_id,document.pk)
        self.assertEqual(submission.receipt_ids,list(PublicationReceipt.objects.values_list('pk',flat=True)))
        self.assertEqual(work.status,'waiting',work.finding)
        self.assertFalse(RFPDisposition.objects.exists())

    def test_returned_outward_document_waits_for_fresh_instruction_and_new_final_review(self):
        data=helpers.configured();work=helpers.start(data)
        factory.run_until_wait(work.pk);work.refresh_from_db()
        response=helpers.response_review(data,work);helpers.costing_review(data,response)
        factory.run_until_wait(work.pk);work.refresh_from_db()
        original=factory_rfp.document_for(work,data['value'])
        self.assertIsNotNone(original,work.finding)
        review=review_version(data['actor'],data['case'].pk,original.pk,'return',
            'Revise the outward document before another final review',rev(data['case']))
        decisions=(RFPReview.objects.count(),CommercialDecision.objects.count())
        self.assertEqual(decisions,(2,3))
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(Version.objects.count(),1)
        self.assertFalse(Publication.objects.exists())
        head=work.source_head_id;spent=work.budget_used;limit=work.budget_limit
        factory_rfp.correct(data['actor'],work.pk,work.revision,rev(data['case']),data['payload'],
            'Fresh human instruction to prepare an outward successor following returned final review')
        work.refresh_from_db()
        self.assertNotEqual(work.source_head_id,head)
        self.assertEqual((work.budget_used,work.budget_limit),(spent,limit))
        factory.run_until_wait(work.pk);work.refresh_from_db()
        replacement=factory_rfp.document_for(work,data['value'])
        self.assertIsNotNone(replacement,work.finding)
        self.assertNotEqual(replacement.pk,original.pk)
        self.assertEqual(factory_rfp.response_for(work).pk,response.pk)
        self.assertEqual(decisions,(RFPReview.objects.count(),CommercialDecision.objects.count()))
        self.assertTrue(ControlledReview.objects.filter(pk=review.pk,version=original,verdict='return').exists())
        self.assertEqual(ControlledReview.objects.filter(version=replacement).count(),0)
        self.assertEqual(work.status,'waiting',work.finding)
        self.assertFalse(Publication.objects.exists());self.assertFalse(PublicationReceipt.objects.exists())
        self.assertTrue(Evidence.objects.filter(pk=head).exists())

    def test_canceled_unsent_response_requires_fresh_outward_review_before_new_delivery(self):
        self.assertEqual(connection.vendor,'postgresql')
        data=helpers.configured();work=helpers.start(data)
        response,original_document=helpers.reviewed_document(data,work)
        publication=None
        for _ in range(10):
            publication=Publication.objects.filter(version=original_document).first()
            if publication:break
            progressed=factory.run_once(work.pk);work.refresh_from_db()
            # A tick that loses its real elapsed lease reports no progress. The
            # supervisor reclaims it; a genuine wait or failure must still fail
            # this reservation-specific setup with its actual recorded state.
            expired=bool(work.lease_until and work.lease_until<=timezone.now())
            self.assertTrue(progressed or expired and not work.cancel_requested and work.status not in factory.TERMINAL,
                {'status':work.status,'finding':work.finding,'lease_until':str(work.lease_until),
                 'fence':work.fence,'spent':work.budget_used,'activities':list(work.activities.values_list('kind','status'))})
        self.assertIsNotNone(publication,work.finding)
        self.assertEqual(publication.job.status,'pending')
        self.assertFalse(PublicationReceipt.objects.exists())
        original_attempts=publication.job.attempts
        original_reviews=ControlledReview.objects.count()
        work.refresh_from_db();head=work.source_head_id;starter=work.actor_id;spent=work.budget_used;limit=work.budget_limit
        operate_publication(data['actor'],data['case'].pk,publication.job.pk,'cancel',
            'Stop this unsent reservation and prepare a newly reviewed client version',rev(data['case']))
        publication.job.refresh_from_db();self.assertEqual(publication.job.status,'cancelled')
        factory_rfp.correct(data['actor'],work.pk,work.revision,rev(data['case']),data['payload'],
            'Fresh source instruction after explicit cancellation of an unsent outward reservation')
        work.refresh_from_db()
        self.assertNotEqual(work.source_head_id,head)
        self.assertTrue(Evidence.objects.filter(pk=head).exists())
        self.assertEqual((work.actor_id,work.budget_used,work.budget_limit),(starter,spent,limit))
        factory.run_until_wait(work.pk);work.refresh_from_db()
        replacement=factory_rfp.document_for(work,data['value'])
        self.assertIsNotNone(replacement,work.finding)
        self.assertNotEqual(replacement.pk,original_document.pk)
        self.assertEqual(factory_rfp.response_for(work).pk,response.pk)
        self.assertEqual(work.status,'waiting',work.finding)
        self.assertEqual(ControlledReview.objects.filter(version=replacement).count(),0)
        self.assertEqual(ControlledReview.objects.count(),original_reviews)
        self.assertEqual(Publication.objects.count(),1)
        self.assertFalse(PublicationReceipt.objects.exists())
        self.assertFalse(RFPSubmission.objects.exists())
        self.assertGreater(work.budget_used,spent);self.assertEqual(work.budget_limit,limit)
        review_version(data['actor'],data['case'].pk,replacement.pk,'approve',
            'Human reviewed this exact replacement outward response',rev(data['case']))
        factory.run_until_wait(work.pk);work.refresh_from_db()
        successor=Publication.objects.get(version=replacement)
        self.assertEqual(successor.factory_work_id,work.pk)
        self.assertEqual(successor.factory_source_id,work.source_head_id)
        self.assertEqual(successor.job.status,'confirmed')
        self.assertEqual(Publication.objects.count(),2)
        self.assertEqual(PublicationReceipt.objects.count(),1)
        self.assertEqual(PublicationReceipt.objects.get().publication_id,successor.pk)
        submission=RFPSubmission.objects.get(response=response)
        self.assertEqual(submission.version_id,replacement.pk)
        self.assertEqual(submission.receipt_ids,list(PublicationReceipt.objects.values_list('pk',flat=True)))
        self.assertEqual(work.status,'waiting',work.finding)
        self.assertFalse(RFPDisposition.objects.exists())
        publication.job.refresh_from_db()
        self.assertEqual(publication.job.status,'cancelled')
        self.assertEqual(publication.job.attempts,original_attempts)
        self.assertFalse(PublicationReceipt.objects.filter(publication=publication).exists())
        self.assertFalse(run_publication_once(case_id=data['case'].pk,job_id=publication.job.pk))
        self.assertEqual(work.actor_id,starter);self.assertTrue(Evidence.objects.filter(pk=head).exists())
