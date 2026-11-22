import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.db import close_old_connections, connection
from django.urls import reverse
from django.utils import timezone

from adapters.rfp_followup import SyntheticBidMailbox, expected
from apps.core.client_contacts import save as save_contact
from apps.core.services import add_evidence
from apps.pmo import rfp, rfp_followup, rfp_messages
from apps.pmo.models import RFPFollowupAttempt, RFPFollowupDispatch, RFPFollowupMailbox, RFPFollowupReceipt
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
        self.client.force_login(f['actor'])
        url = reverse('factory_work_response', args=[self.work.pk])
        queued = self.client.get(url)
        self.assertContains(queued, 'Delivery queued for the reviewed route.')
        self.assertNotContains(queued, 'Check original message receipt')
        self.assertTrue(queued.context['followup']['released'])
        self.assertFalse(queued.context['followup']['waiting_on_original'])
        self.assertFalse(RFPFollowupAttempt.objects.filter(dispatch=dispatch).exists())
        save_contact(f['actor'],f['case'],'project',{'revision':rev(f['case']),'customer':'',
            'client_name':'Sample procurement','name':'Replacement recipient','email':'replacement@example.invalid',
            'role':'Procurement','evidence':f['evidence']['policy_decision']})
        held = self.client.get(url)
        self.assertContains(held, 'Delivery held before its first attempt. Review the customer outcome, current wording and delivery route.')
        self.assertNotContains(held, 'Review the changed project contact before releasing a message.')
        self.assertNotContains(held, 'Release reviewed follow-up')
        self.assertFalse(rfp_messages.run_once(dispatch.pk))
        self.assertFalse(RFPFollowupAttempt.objects.exists())
        Grant.objects.filter(case=f['case'],user=f['actor'],action='rfp.submit').update(active=False)
        held = self.client.get(url)
        self.assertContains(held, 'Review the current sender’s bid access.')
        self.assertNotContains(held, 'Check original message receipt')
        self.assertNotContains(held, 'This record/action has no active grant')
        self.assertFalse(rfp_messages.run_once(dispatch.pk))
        self.assertFalse(RFPFollowupMailbox.objects.exists())
        self.assertFalse(RFPFollowupReceipt.objects.exists())

    def test_changed_route_is_visible_to_the_original_sender_only(self):
        dispatch = self.release()
        f = self.data
        configured(f, 'manual_evidence')
        url = reverse('factory_work_response', args=[self.work.pk])
        self.client.force_login(f['actor'])
        self.assertContains(self.client.get(url), 'Delivery held before its first attempt.')
        peer = get_user_model().objects.create_user(username='sample-bid-followup-read-only-peer')
        Grant.objects.bulk_create([Grant(user=peer, case=f['case'], action=action)
                                   for action in ('case.read', 'factory.read', 'rfp.read')])
        with patch('apps.pmo.rfp_messages.check_current') as preflight:
            self.assertIsNone(rfp_messages.pre_attempt_hold(peer, f['case'], dispatch.pk))
            self.client.force_login(peer)
            page = self.client.get(url)
            self.assertNotContains(page, 'Delivery held before its first attempt.')
            self.assertNotContains(page, 'Sample reviewed customer message')
            preflight.assert_not_called()
        self.assertFalse(RFPFollowupAttempt.objects.filter(dispatch=dispatch).exists())

    def test_decision_and_recovery_readbacks_skip_private_followup_history(self):
        dispatch = self.release()
        self.client.force_login(self.data['actor'])
        table = RFPFollowupDispatch._meta.db_table
        for route in ('factory_invoice_decision', 'factory_invoice_recovery'):
            with self.subTest(route=route):
                with CaptureQueriesContext(connection) as queries:
                    page = self.client.get(reverse(route, args=[self.work.pk]))
                self.assertNotContains(page, 'Follow-up delivery')
                self.assertFalse(any(table in query['sql'] for query in queries.captured_queries))
        self.assertFalse(RFPFollowupAttempt.objects.filter(dispatch=dispatch).exists())

    def test_newer_wording_cannot_release_while_the_original_reservation_is_held(self):
        dispatch = self.release()
        f = self.data
        newer = rfp_followup.review(f['actor'], f['case'].pk, self.outcome.pk, dispatch.review.data['run'],
            'Sample replacement wording requires a separate release.', dispatch.review_id, rev(f['case']))
        self.client.force_login(f['actor'])
        url = reverse('factory_work_response', args=[self.work.pk])
        page = self.client.get(url)
        self.assertContains(page, 'Delivery held before its first attempt.')
        self.assertContains(page, 'Review the earlier release before releasing new wording.')
        self.assertNotContains(page, 'Release reviewed follow-up')
        self.assertContains(self.client.post(url, {'action': 'followup_send', 'target': self.outcome.pk,
            'reviewed': newer.pk, 'route': 'customer_followup', 'case_revision': rev(f['case'])}),
            'Check the earlier message receipt before releasing another follow-up.')
        preserved = RFPFollowupDispatch.objects.get(outcome=self.outcome)
        self.assertEqual(preserved.review_id, dispatch.review_id)
        self.assertEqual(preserved.payload['body'], 'Sample reviewed customer message')
        self.assertFalse(RFPFollowupAttempt.objects.filter(dispatch=dispatch).exists())

    def test_attempted_original_keeps_lookup_even_when_the_route_changes(self):
        class BeforeAcceptance(SyntheticBidMailbox):
            def deliver(self, dispatch):
                raise TimeoutError('Sample interrupted response')

        dispatch = self.release()
        self.assertTrue(rfp_messages.run_once(dispatch.pk, BeforeAcceptance()))
        configured(self.data, 'manual_evidence')
        self.client.force_login(self.data['actor'])
        url = reverse('factory_work_response', args=[self.work.pk])
        with patch('apps.pmo.rfp_messages.check_current') as preflight:
            page = self.client.get(url)
            self.assertContains(page, 'Awaiting evidence for the original message.')
            self.assertContains(page, 'Check original message receipt')
            self.assertNotContains(page, 'Delivery held before its first attempt.')
            self.assertNotContains(page, 'Release reviewed follow-up')
            preflight.assert_not_called()
        self.assertEqual(RFPFollowupAttempt.objects.filter(dispatch=dispatch).count(), 1)
        self.assertFalse(RFPFollowupMailbox.objects.filter(dispatch=dispatch).exists())
        self.assertFalse(RFPFollowupReceipt.objects.filter(dispatch=dispatch).exists())


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
