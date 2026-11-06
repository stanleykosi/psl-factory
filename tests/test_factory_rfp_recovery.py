"""RFP recovery preserves committed effects and independent human decisions."""
from time import sleep
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase,TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from adapters.publications import InternalPublicationAdapter
from apps.documents.delivery import claim_publication,deliver_internal,run_publication_once
from apps.documents.models import Publication,PublicationReceipt
from apps.identity.models import Grant
from apps.pmo.models import RFPReview,RFPSubmission
from apps.policy.services import transition
from apps.workflows import factory,factory_rfp
from tests import factory_rfp_helpers as helpers
from tests.helpers import rev


def reserved_response(test,data):
    work=helpers.start(data)
    response,document=helpers.reviewed_document(data,work)
    publication=None
    for _ in range(10):
        publication=Publication.objects.filter(version=document).first()
        if publication:break
        test.assertTrue(factory.run_once(work.pk))
        work.refresh_from_db()
    test.assertIsNotNone(publication,work.finding)
    test.assertEqual(publication.factory_work_id,work.pk)
    test.assertEqual(publication.job.status,'pending')
    work.refresh_from_db()
    return work,response,publication


class FactoryRFPCrashRecoveryTests(TransactionTestCase):
    def test_expired_native_lease_recovers_committed_receipt_after_source_author_withdrawal(self):
        self.assertEqual(connection.vendor,'postgresql')
        self.assertFalse(connection.in_atomic_block,'Crash evidence requires real committed native transactions')
        data=helpers.configured()
        work,response,publication=reserved_response(self,data)
        head=work.source_head_id;starter=work.actor_id;spent=work.budget_used;limit=work.budget_limit
        lease=claim_publication(case_id=data['case'].pk,job_id=publication.job.pk)
        self.assertIsNotNone(lease)
        job_id,fence=lease
        deliver_internal(job_id,fence)
        # The native local effect committed; the worker crashes before recording finish.
        publication.job.refresh_from_db()
        self.assertEqual(publication.job.status,'leased')
        receipts=list(PublicationReceipt.objects.filter(publication=publication).order_by('pk').values_list('pk',flat=True))
        self.assertEqual(len(receipts),1)
        with self.assertRaises(ValidationError):
            factory.reconcile(data['actor'],work.pk,work.revision)
        self.assertEqual(PublicationReceipt.objects.filter(publication=publication).count(),1)
        Grant.objects.filter(case=data['case'],user=data['actor'],action='factory.start').update(active=False)
        # Wait out the actual30-second native lease; do not rewrite timestamps or authority.
        remaining=max(0,(publication.job.lease_until-timezone.now()).total_seconds())
        if remaining:sleep(remaining+0.05)
        self.assertLessEqual(publication.job.lease_until,timezone.now())
        with patch.object(InternalPublicationAdapter,'deliver',side_effect=AssertionError('A committed receipt must be looked up without another send')) as send:
            factory.reconcile(data['actor'],work.pk,work.revision)
        send.assert_not_called()
        work.refresh_from_db();publication.job.refresh_from_db()
        self.assertEqual(publication.job.status,'confirmed')
        self.assertEqual((work.source_head_id,work.actor_id,work.budget_used,work.budget_limit),(head,starter,spent,limit))
        self.assertEqual(list(PublicationReceipt.objects.filter(publication=publication).order_by('pk').values_list('pk',flat=True)),receipts)
        self.assertTrue(factory.run_once(work.pk))
        submission=RFPSubmission.objects.get(response=response)
        self.assertEqual(submission.receipt_ids,receipts)
        self.assertFalse(Grant.objects.get(case=data['case'],user=data['actor'],action='factory.start').active)


class FactoryRFPAuthorityBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.data=helpers.configured()

    def test_withdrawn_source_author_holds_new_publication_without_creating_receipts(self):
        data=self.data;work,response,publication=reserved_response(self,data)
        head=work.source_head_id;spent=work.budget_used
        Grant.objects.filter(case=data['case'],user=data['actor'],action='factory.start').update(active=False)
        self.assertTrue(run_publication_once(case_id=data['case'].pk,job_id=publication.job.pk))
        publication.job.refresh_from_db();work.refresh_from_db()
        self.assertEqual(publication.job.status,'held')
        self.assertFalse(PublicationReceipt.objects.filter(publication=publication).exists())
        self.assertFalse(RFPSubmission.objects.filter(response=response).exists())
        self.assertEqual((work.source_head_id,work.budget_used),(head,spent))

    def test_withdrawn_execution_profile_preserves_current_native_human_response_review(self):
        data=self.data;work=helpers.start(data)
        factory.run_until_wait(work.pk);work.refresh_from_db()
        response=factory_rfp.response_for(work)
        self.assertIsNotNone(response,work.finding)
        spent=work.budget_used
        transition(data['actor'],data['profile'].pk,'revoked')
        self.client.force_login(data['actor'])
        url=reverse('factory_detail',args=[work.pk])+'?queue=decisions&q=Synthetic'
        page=self.client.get(url)
        self.assertContains(page,'PMO Lead response review')
        self.assertNotContains(page,'Continue response work')
        payload={'action':'response','revision':work.revision,'case_revision':rev(data['case']),'target':response.pk,
            'role':'PMO Lead','verdict':'approve','evidence':data['evidence']['policy_decision'].pk,
            'note':'Current native human review remains available while agent execution is unconfigured'}
        self.assertRedirects(self.client.post(url,payload),url)
        review=RFPReview.objects.get(response=response,role='PMO Lead')
        self.assertEqual(review.actor_id,data['actor'].pk)
        work.refresh_from_db();self.assertEqual(work.budget_used,spent)
        Grant.objects.filter(case=data['case'],user=data['actor'],action='rfp.review').update(active=False)
        payload.update(revision=work.revision,case_revision=rev(data['case']),role='Engineering Lead')
        self.assertEqual(self.client.post(url,payload).status_code,403)
        self.assertEqual(RFPReview.objects.filter(response=response).count(),1)
