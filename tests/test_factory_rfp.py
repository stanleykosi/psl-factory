"""Real native RFP factory behavior; only recipient-transport faults are synthetic."""
from copy import deepcopy
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.test import TestCase,TransactionTestCase
from django.utils import timezone
from apps.agents.models import AgentRun
from apps.core.models import Evidence
from apps.core.services import add_evidence
from apps.documents.models import Publication,PublicationJob,PublicationReceipt,ControlledReview
from apps.identity.models import Grant
from apps.pmo import rfp
from apps.pmo.models import RFPResponse,RFPReview,RFPSubmission,RFPDisposition,CommercialDecision,Baseline
from apps.workflows import factory,factory_rfp
from apps.workflows.models import FactoryWork
from adapters.publications import PublicationTimeoutAfterAccept
from tests.helpers import rev,setup_case
from tests import factory_rfp_helpers as helpers


class FactoryRFPTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.data=helpers.configured()

    def test_intake_useful_agent_human_reviews_receipt_and_won_route_a(self):
        self.assertEqual(connection.vendor,'postgresql')
        f=self.data;work=helpers.start(f);starter=work.actor_id
        factory.run_until_wait(work.pk);work.refresh_from_db()
        response=factory_rfp.response_for(work)
        self.assertIsNotNone(response,work.finding);self.assertEqual(work.status,'waiting',work.finding)
        investigation=AgentRun.objects.filter(case=f['case'],provider='deterministic-rfp-investigation-v1').order_by('pk').first()
        self.assertIsNotNone(investigation)
        self.assertTrue(investigation.result['citations'])
        self.assertFalse(investigation.result['approval_granted']);self.assertFalse(investigation.result['submission_dispatched'])
        self.assertNotIn(f['evidence']['costing'].body,str(investigation.result))
        self.assertEqual(RFPReview.objects.count(),0);self.assertEqual(CommercialDecision.objects.count(),0)
        self.assertFalse(Publication.objects.exists());self.assertGreater(work.budget_used,0)
        helpers.response_review(f,work)
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(work.status,'waiting',work.finding);self.assertFalse(Publication.objects.exists())
        helpers.costing_review(f,response)
        factory.run_until_wait(work.pk);work.refresh_from_db()
        document=factory_rfp.document_for(work,f['value'])
        self.assertIsNotNone(document,work.finding);self.assertEqual(work.status,'waiting',work.finding)
        self.assertFalse(ControlledReview.objects.filter(version=document).exists())
        from apps.documents.controlled import review_version
        review_version(f['actor'],f['case'].pk,document.pk,'approve','Actual human exact outward review',rev(f['case']))
        factory.run_until_wait(work.pk);work.refresh_from_db()
        submission=RFPSubmission.objects.get(response=response)
        self.assertEqual(work.status,'waiting',work.finding);self.assertFalse(RFPDisposition.objects.exists())
        publication=Publication.objects.get(version=document)
        self.assertEqual(publication.factory_work_id,work.pk)
        receipts=list(PublicationReceipt.objects.filter(publication=publication).order_by('pk').values_list('pk',flat=True))
        self.assertEqual(submission.receipt_ids,receipts);self.assertEqual(len(receipts),1)
        self.assertFalse(Baseline.objects.exists())
        spent=work.budget_used
        outcome=rfp.outcome(f['actor'],f['case'].pk,submission.pk,'won',timezone.now(),'Client',
            f['evidence']['rfp_outcome'].pk,'Actual synthetic customer decision',rev(f['case']))
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(work.status,'verified',work.finding)
        disposition=RFPDisposition.objects.get(rfp=response.rfp)
        self.assertEqual(disposition.kind,'route_a');self.assertEqual(disposition.outcome_id,outcome.pk)
        self.assertFalse(disposition.snapshot['baseline_imported']);self.assertFalse(Baseline.objects.exists())
        self.assertTrue(factory_rfp.verify(work)['verified'])
        self.assertEqual(work.actor_id,starter);self.assertGreater(work.budget_used,spent)
        self.assertEqual(work.budget_limit,30000)
        counts=(RFPResponse.objects.count(),RFPReview.objects.count(),CommercialDecision.objects.count(),PublicationReceipt.objects.count())
        factory.run_until_wait(work.pk)
        self.assertEqual(counts,(RFPResponse.objects.count(),RFPReview.objects.count(),CommercialDecision.objects.count(),PublicationReceipt.objects.count()))

    def test_lost_outcome_requires_declared_lessons_before_verified_archive(self):
        f=self.data;payload=deepcopy(f['payload']);payload['lessons']=None;work=helpers.start(f,payload=payload)
        response,document=helpers.reviewed_document(f,work)
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertTrue(RFPSubmission.objects.filter(response=response).exists(),work.finding)
        submission=RFPSubmission.objects.get(response=response)
        rfp.outcome(f['actor'],f['case'].pk,submission.pk,'lost',timezone.now(),'Client',f['evidence']['rfp_outcome'].pk,
            'Actual synthetic loss',rev(f['case']))
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertNotEqual(work.status,'verified');self.assertFalse(RFPDisposition.objects.exists())
        spent=work.budget_used;payload['lessons']=f['evidence']['rfp_lessons'].pk
        factory_rfp.correct(f['actor'],work.pk,work.revision,rev(f['case']),payload,'Record the actual loss lessons')
        factory.run_until_wait(work.pk);work.refresh_from_db()
        disposition=RFPDisposition.objects.get(rfp=response.rfp)
        self.assertEqual(disposition.kind,'loss_archive');self.assertEqual(disposition.lessons_id,payload['lessons'])
        self.assertEqual(work.status,'verified',work.finding);self.assertGreaterEqual(work.budget_used,spent)
        self.assertEqual(RFPResponse.objects.count(),1);self.assertEqual(PublicationReceipt.objects.count(),1)

    def test_unknown_inputs_get_useful_investigation_then_source_owned_correction(self):
        f=self.data;payload=deepcopy(f['payload']);payload['response_evidence']=None;work=helpers.start(f,payload=payload)
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertTrue(AgentRun.objects.filter(case=f['case'],provider='deterministic-rfp-investigation-v1').exists())
        self.assertEqual(work.status,'waiting',work.finding);self.assertFalse(RFPResponse.objects.exists())
        head=work.source_head_id;spent=work.budget_used;limit=work.budget_limit;revision=work.revision
        factory_rfp.correct(f['actor'],work.pk,revision,rev(f['case']),f['payload'],'Received response wording')
        work.refresh_from_db();self.assertNotEqual(work.source_head_id,head)
        self.assertTrue(Evidence.objects.filter(pk=head).exists());self.assertEqual(work.budget_used,spent)
        self.assertEqual(work.budget_limit,limit)
        with self.assertRaises(ValidationError):
            factory_rfp.correct(f['actor'],work.pk,revision,rev(f['case']),f['payload'],'Stale correction cannot overwrite')
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertIsNotNone(factory_rfp.response_for(work),work.finding)

    def test_return_requires_explicit_source_successor_and_fresh_native_decisions(self):
        f=self.data;work=helpers.start(f);factory.run_until_wait(work.pk);work.refresh_from_db()
        old=factory_rfp.response_for(work)
        rfp.review(f['actor'],f['case'].pk,old.pk,'Engineering Lead','return',f['evidence']['policy_decision'].pk,
            'Clarify the quoted requirement coverage',rev(f['case']))
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(RFPResponse.objects.count(),1);self.assertNotEqual(work.status,'verified')
        payload=deepcopy(f['payload']);payload['matrix'][0]['response']='Revised cited coverage after actual review'
        factory_rfp.correct(f['actor'],work.pk,work.revision,rev(f['case']),payload,'Address returned wording')
        spent=FactoryWork.objects.get(pk=work.pk).budget_used
        factory.run_until_wait(work.pk);work.refresh_from_db()
        revised=factory_rfp.response_for(work)
        self.assertIsNotNone(revised,work.finding);self.assertNotEqual(revised.pk,old.pk)
        self.assertEqual(revised.reviews.count(),0);self.assertEqual(revised.commercial.decisions.count(),0)
        self.assertTrue(RFPReview.objects.filter(response=old,verdict='return').exists())
        self.assertGreater(work.budget_used,spent)

    def test_uncertain_publication_reconciles_exact_receipts_before_cancellation(self):
        f=self.data;work=helpers.start(f);response,document=helpers.reviewed_document(f,work)
        for _ in range(10):
            publication=Publication.objects.filter(version=document).first()
            if publication:break
            progressed=factory.run_once(work.pk);work.refresh_from_db()
            self.assertTrue(progressed,work.finding)
        self.assertIsNotNone(publication,work.finding)
        self.assertEqual(publication.job.status,'pending')
        self.assertTrue(factory.run_once(work.pk,adapter=PublicationTimeoutAfterAccept()))
        publication.job.refresh_from_db();work.refresh_from_db()
        self.assertEqual(publication.job.status,'unknown')
        receipts=list(PublicationReceipt.objects.filter(publication=publication).values_list('pk',flat=True))
        self.assertEqual(len(receipts),1)
        factory.manage(f['actor'],work.pk,work.revision,'cancel')
        work.refresh_from_db()
        factory.reconcile(f['actor'],work.pk,work.revision)
        work.refresh_from_db();publication.job.refresh_from_db()
        self.assertEqual(publication.job.status,'confirmed')
        self.assertEqual(work.status,'followup_needed',work.finding)
        self.assertFalse(RFPDisposition.objects.exists())
        self.assertEqual(list(PublicationReceipt.objects.filter(publication=publication).values_list('pk',flat=True)),receipts)

    def test_idempotency_scope_exact_types_permission_and_sql_output_guards(self):
        f=self.data;work=helpers.start(f)
        self.assertEqual(helpers.start(f).pk,work.pk)
        self.assertEqual(FactoryWork.objects.count(),1)
        changed=deepcopy(f['payload']);changed['matrix'][0]['response']='Different request under the same key'
        with self.assertRaises(ValidationError):helpers.start(f,payload=changed)
        for field in ['response_evidence','public_terms','lessons']:
            invalid=deepcopy(f['payload']);invalid[field]=True
            with self.subTest(field=field),self.assertRaises(ValidationError):helpers.start(f,key='BAD-'+field,payload=invalid)
        other,case=setup_case(username='other-rfp-source')
        foreign=add_evidence(other,case.pk,'requirements','Other workspace source','synthetic:other')
        invalid=deepcopy(f['payload']);invalid['sources']['requirements']=foreign.pk
        with self.assertRaises((ValidationError,PermissionDenied)):helpers.start(f,key='CROSS-CASE',payload=invalid)
        with transaction.atomic(),self.assertRaises(DatabaseError):
            FactoryWork.objects.filter(pk=work.pk).update(status='verified')
        work.refresh_from_db();self.assertNotEqual(work.status,'verified')
        Grant.objects.filter(case=f['case'],user=f['actor'],action='factory.start').update(active=False)
        with self.assertRaises(PermissionDenied):helpers.start(f,key='NO-AUTHORITY')

    def test_primary_response_decision_uses_native_review_and_rejects_stale_csrf_and_revoked_grants(self):
        from django.test import Client
        from django.urls import reverse
        f=self.data;work=helpers.start(f);factory.run_until_wait(work.pk);work.refresh_from_db()
        response=factory_rfp.response_for(work)
        self.assertIsNotNone(response,work.finding)
        self.client.force_login(f['actor'])
        url=reverse('factory_detail',args=[work.pk])+'?queue=decisions&q=Synthetic'
        self.assertEqual(self.client.get(url).status_code,200)
        payload={'action':'response','revision':work.revision,'case_revision':rev(f['case']),'target':response.pk,
            'role':'PMO Lead','verdict':'approve','evidence':f['evidence']['policy_decision'].pk,'note':'Actual human review through operator console'}
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(f['actor'])
        self.assertEqual(csrf.post(url,payload).status_code,403)
        self.assertFalse(RFPReview.objects.exists())
        self.assertRedirects(self.client.post(url,payload),url)
        review=RFPReview.objects.get(response=response,role='PMO Lead')
        self.assertEqual(review.actor_id,f['actor'].pk);self.assertEqual(review.verdict,'approve')
        self.assertEqual(review.evidence_id,f['evidence']['policy_decision'].pk)
        self.assertContains(self.client.post(url,payload),'STALE_VERSION')
        self.assertEqual(RFPReview.objects.count(),1)
        work.refresh_from_db()
        Grant.objects.filter(case=f['case'],user=f['actor'],action='rfp.review').update(active=False)
        denied=dict(payload,revision=work.revision,case_revision=rev(f['case']),role='Engineering Lead')
        self.assertEqual(self.client.post(url,denied).status_code,403)
        self.assertEqual(RFPReview.objects.count(),1)


class FactoryRFPConcurrencyTests(TransactionTestCase):
    def test_two_workers_share_the_same_reservation_and_do_not_duplicate_response(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from django.db import close_old_connections,connections
        from apps.agents.factory_catalogue import SyntheticFactoryCoordinator
        f=helpers.configured();work=helpers.start(f);entered=Event();release=Event();backend=[]
        class HeldCoordinator(SyntheticFactoryCoordinator):
            def choose(self,context):
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()');backend.append(cursor.fetchone()[0])
                entered.set()
                if not release.wait(20):raise AssertionError('Second worker did not finish while original claim was held')
                return super().choose(context)
        def advance():
            close_old_connections()
            try:return factory.run_once(work.pk,provider=HeldCoordinator())
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=1) as pool:
            first=pool.submit(advance)
            try:
                self.assertTrue(entered.wait(20),'Original worker never reached its persisted planning reservation')
                self.assertFalse(factory.run_once(work.pk))
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()');self.assertNotEqual(cursor.fetchone()[0],backend[0])
            finally:release.set()
            self.assertTrue(first.result(timeout=20))
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(RFPResponse.objects.count(),1)
        self.assertIsNotNone(factory_rfp.response_for(work),work.finding)
        self.assertFalse(PublicationReceipt.objects.exists())
