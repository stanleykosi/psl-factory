import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.db import close_old_connections, connection
from django.urls import reverse
from django.utils import timezone

from adapters.rfp_followup import SyntheticBidMailbox, expected
from apps.core.client_contacts import save as save_contact
from apps.core.services import add_evidence
from apps.pmo import rfp, rfp_followup, rfp_messages
from apps.pmo.models import RFPFollowupAttempt, RFPFollowupMailbox, RFPFollowupReceipt
from apps.identity.models import Grant
from apps.policy.change_drafts import draft_standard_policy
from apps.policy.services import reference_values, resolve, transition
from apps.workflows import factory
from tests import factory_rfp_helpers as helpers
from tests.helpers import rev


def configured(data,mode='synthetic_mailbox'):
    actor,case=data['actor'],data['case']
    contact=save_contact(actor,case,'project',{'revision':rev(case),'customer':'','client_name':'Sample procurement',
        'name':'Synthetic bid recipient','email':'procurement@example.invalid','role':'Procurement',
        'evidence':data['evidence']['policy_decision']})
    cfg=resolve('D11.adapter_configuration_refs',case).configuration
    value={'kind':'rfp_followup','key':'customer_followup','mode':mode,'contact_id':contact.pk,'sender_roles':['PM']}
    routes=[row for row in reference_values(cfg) if row.get('kind')!='rfp_followup']
    policy=draft_standard_policy(actor,case.pk,'D11.adapter_configuration_refs',routes+[value],
                                data['evidence']['policy_decision'].pk,timezone.now())
    transition(actor,policy.pk,'validated');transition(actor,policy.pk,'active')
    return contact


class BidMessageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data=helpers.configured()
        configured(cls.data)
        f=cls.data
        cls.work=helpers.start(f)
        response,_=helpers.reviewed_document(f,cls.work)
        factory.run_until_wait(cls.work.pk)
        cls.submission=response.submissions.get()
        cls.outcome=rfp.outcome(f['actor'],f['case'].pk,cls.submission.pk,'unknown',timezone.now(),
            'Client',None,'Sample no-reply check',rev(f['case']))

    def release(self):
        f=self.data
        run=rfp_followup.draft(f['actor'],f['case'].pk,self.outcome.pk,rev(f['case']))
        review=rfp_followup.review(f['actor'],f['case'].pk,self.outcome.pk,run.pk,'Sample reviewed customer message',0,rev(f['case']))
        return rfp_messages.reserve(f['actor'],f['case'].pk,self.outcome.pk,review.pk,'customer_followup',rev(f['case']))

    def test_fresh_outcome_offers_a_draft_before_any_review_exists(self):
        self.client.force_login(self.data['actor'])
        page=self.client.get(reverse('factory_work_response',args=[self.work.pk]))
        self.assertContains(page,'Prepare a follow-up draft')

    def test_bounded_worker_scan_wraps_and_omits_verified_originals(self):
        dispatch=self.release()
        self.assertEqual(rfp_messages.next_batch(limit=1),[dispatch.pk])
        self.assertEqual(rfp_messages.next_batch(limit=1),[dispatch.pk])
        rfp_messages.run_once(dispatch.pk)
        self.assertEqual(rfp_messages.next_batch(limit=1),[])
        with self.assertRaises(ValueError):rfp_messages.next_batch(limit=0)

    def test_reviewed_message_delivers_once_and_preserves_its_exact_receipt(self):
        dispatch=self.release()
        self.assertFalse(rfp_messages.run_once(dispatch.pk,lookup_only=True))
        self.assertFalse(RFPFollowupAttempt.objects.exists())
        self.assertTrue(rfp_messages.run_once(dispatch.pk))
        self.assertFalse(rfp_messages.run_once(dispatch.pk))
        dispatch.refresh_from_db()
        self.assertEqual(dispatch.mailbox.payload['body'],'Sample reviewed customer message')
        self.assertTrue(dispatch.receipt.delivered)
        self.assertEqual(RFPFollowupMailbox.objects.count(),1)
        self.client.force_login(self.data['actor'])
        page=self.client.get(reverse('factory_work_response',args=[self.work.pk]))
        self.assertContains(page,'Delivery verified')
        self.assertContains(page,'Read sample inbox message')
        self.assertContains(page,'Released wording')
        self.assertNotContains(page,'Release reviewed follow-up')

    def test_uncertain_lookup_never_delivers_again_and_late_original_receipt_recovers(self):
        dispatch=self.release()

        class BeforeAcceptance(SyntheticBidMailbox):
            def deliver(self,row):
                raise TimeoutError('Sample interrupted response')

        self.assertTrue(rfp_messages.run_once(dispatch.pk,BeforeAcceptance()))
        self.assertTrue(rfp_messages.run_once(dispatch.pk))
        self.assertEqual(RFPFollowupMailbox.objects.count(),0)
        self.assertEqual(RFPFollowupReceipt.objects.count(),0)
        SyntheticBidMailbox().deliver(dispatch)
        self.assertTrue(rfp_messages.run_once(dispatch.pk))
        self.assertEqual(RFPFollowupReceipt.objects.count(),1)

    def test_manual_receipt_checks_exact_message(self):
        f=self.data
        configured(f,'manual_evidence')
        dispatch=self.release()
        source=add_evidence(f['actor'],f['case'].pk,'rfp_followup_receipt',json.dumps(expected(dispatch,'MAIL-1',True)),
                            'synthetic:manual-message-receipt')
        receipt=rfp_messages.confirm(f['actor'],f['case'].pk,dispatch.pk,source.pk,'MAIL-1',True,rev(f['case']))
        self.assertTrue(receipt.delivered)
        with self.assertRaisesMessage(ValidationError,'must match the original'):
            rfp_messages.confirm(f['actor'],f['case'].pk,dispatch.pk,source.pk,'OTHER',True,rev(f['case']))

    def test_changed_contact_and_revoked_sender_hold_before_first_effect(self):
        dispatch=self.release()
        f=self.data
        save_contact(f['actor'],f['case'],'project',{'revision':rev(f['case']),'customer':'',
            'client_name':'Sample procurement','name':'Replacement recipient','email':'replacement@example.invalid',
            'role':'Procurement','evidence':f['evidence']['policy_decision']})
        self.assertFalse(rfp_messages.run_once(dispatch.pk))
        self.assertFalse(RFPFollowupAttempt.objects.exists())
        Grant.objects.filter(case=f['case'],user=f['actor'],action='rfp.submit').update(active=False)
        self.assertFalse(rfp_messages.run_once(dispatch.pk))
        self.assertFalse(RFPFollowupMailbox.objects.exists())


class BidMessageConcurrencyTests(TransactionTestCase):
    def test_competing_workers_preserve_one_original_attempt_and_message(self):
        self.assertEqual(connection.vendor,'postgresql')
        data=helpers.configured()
        configured(data)
        work=helpers.start(data)
        response,_=helpers.reviewed_document(data,work)
        factory.run_until_wait(work.pk)
        result=rfp.outcome(data['actor'],data['case'].pk,response.submissions.get().pk,'unknown',
            timezone.now(),'Client',None,'Sample no-reply check',rev(data['case']))
        run=rfp_followup.draft(data['actor'],data['case'].pk,result.pk,rev(data['case']))
        review=rfp_followup.review(data['actor'],data['case'].pk,result.pk,run.pk,
            'One reviewed message',0,rev(data['case']))
        dispatch=rfp_messages.reserve(data['actor'],data['case'].pk,result.pk,review.pk,
            'customer_followup',rev(data['case']))
        barrier=Barrier(2)
        deliveries=[]

        class CountedMailbox(SyntheticBidMailbox):
            def deliver(self,row):
                deliveries.append(row.pk)
                return super().deliver(row)

        def compete():
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                return rfp_messages.run_once(dispatch.pk,CountedMailbox())
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as workers:
            list(workers.map(lambda _:compete(),range(2)))
        self.assertEqual(deliveries,[dispatch.pk])
        self.assertEqual(RFPFollowupAttempt.objects.filter(dispatch=dispatch).count(),1)
        self.assertEqual(RFPFollowupMailbox.objects.filter(dispatch=dispatch).count(),1)
        self.assertEqual(RFPFollowupReceipt.objects.filter(dispatch=dispatch).count(),1)
