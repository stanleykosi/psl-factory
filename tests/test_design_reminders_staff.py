from datetime import timedelta
from email import policy
from email.parser import BytesParser
from hashlib import sha256
from io import BytesIO
import json
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfWriter

from apps.agents.models import CaseUpload
from apps.core.client_contacts import save as save_contact
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.finance import reminders
from apps.finance.models import PaymentReminderDispatch, PaymentReminderMailboxMessage, PaymentReminderReceipt
from apps.identity import intake, staff
from apps.identity.models import Grant, StaffInvitation
from apps.pmo.meetings import create_action
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.reminder_validators import COMPONENT
from apps.policy.role_assignments import draft as draft_roles
from apps.policy.services import transition
from tests import settlement_helpers as settlement
from tests.helpers import rev
from tests.obligation_helpers import issue_identified


def activate(actor, cfg):
    transition(actor, cfg.pk, 'validated')
    transition(actor, cfg.pk, 'active')


class PaymentReminderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor, cls.case, coverage, preparation, proofs = settlement.fixture()
        invoice = settlement.draft(cls.actor, cls.case, preparation)
        cls.issue = issue_identified(cls.actor, cls.case, invoice, proofs)
        cls.policy = add_evidence(cls.actor, cls.case.pk, 'policy_decision', 'Synthetic reminder controls', 'synthetic:test')
        cls.contact = save_contact(cls.actor, cls.case, 'billing', {'revision':rev(cls.case), 'evidence':cls.policy,
            'customer':coverage.customer, 'client_name':'Synthetic client', 'name':'Accounts',
            'email':'billing@example.invalid', 'role':'Billing'})

    def activate_delivery(self, mode, **options):
        values = {'contact_revision_ids':[self.contact.pk], 'sender_ids':[self.actor.pk],
                  'receipt_recorder_ids':[self.actor.pk], 'mode':mode, 'days_after_due':0, 'minimum_days_between':1,
                  **options}
        config = draft_operator_policy(self.actor, self.case.pk, COMPONENT, values, self.policy.pk,
                                      timezone.now() - timedelta(seconds=1))
        activate(self.actor, config)
        return config

    def test_edited_exact_reminder_reaches_synthetic_inbox_once(self):
        self.client.force_login(self.actor)
        url = reverse('design_payment_reminder', args=[self.case.pk, self.issue.pk])
        self.assertContains(self.client.get(url), 'billing@example.invalid')
        post = {'action':'draft', 'subject':'Finance follow-up', 'body':'A human-edited message.', 'revision':rev(self.case)}
        self.assertContains(self.client.post(url, post, follow=True), 'A human-edited message.')
        first = self.issue.reminder_drafts.get()
        send = {'action':'send', 'draft':first.pk, 'revision':rev(self.case)}
        self.assertEqual(self.client.post(url, send).status_code, 200)
        self.assertEqual(PaymentReminderDispatch.objects.count(), 0)
        self.activate_delivery('synthetic_inbox')
        post.update(body='Revised message with source figures.', revision=rev(self.case))
        self.assertEqual(self.client.post(url, post).status_code, 302)
        self.assertEqual(self.client.post(url, {**send, 'revision':rev(self.case)}).status_code, 200)
        current = self.issue.reminder_drafts.order_by('-pk').first()
        send.update(draft=current.pk, revision=rev(self.case))
        self.assertContains(self.client.post(url, send, follow=True), 'Awaiting delivery confirmation')
        operation = PaymentReminderDispatch.objects.get()
        a = reminders.simulate(operation.pk)
        b = reminders.simulate(operation.pk)
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(a.sha256, current.sha256)
        self.assertEqual(PaymentReminderReceipt.objects.count(), 1)
        self.assertContains(self.client.get(url), 'Delivery confirmed')

    def test_manual_evidence_must_match_original_and_blocks_unresolved_resend(self):
        self.activate_delivery('manual_evidence')
        a,c,i = self.actor,self.case,self.issue
        draft = reminders.draft(a,c.pk,i.pk,'Payment follow-up','Reviewed wording.',rev(c))
        dispatch = reminders.dispatch(a,c.pk,i.pk,draft.pk,rev(c))
        next_ = reminders.draft(a,c.pk,i.pk,'Second follow-up','Potential second reminder.',rev(c))
        with self.assertRaises(ValidationError):
            reminders.dispatch(a,c.pk,i.pk,next_.pk,rev(c))
        body = {'operation':str(dispatch.operation_key),'draft_sha256':draft.sha256,
                'recipient':'billing@example.invalid','reference':'synthetic-channel-record','delivered':True}
        wrong = add_evidence(a,c.pk,'payment_reminder_receipt',json.dumps({**body,'recipient':'wrong@example.invalid'}),'synthetic:test')
        with self.assertRaises(ValidationError):
            reminders.confirm(a,c.pk,i.pk,dispatch.pk,body['reference'],True,wrong.pk,rev(c))
        valid = add_evidence(a,c.pk,'payment_reminder_receipt',json.dumps(body),'synthetic:test')
        receipt = reminders.confirm(a,c.pk,i.pk,dispatch.pk,body['reference'],True,valid.pk,rev(c))
        self.assertEqual(receipt.sha256, draft.sha256)

    def test_schedule_preserves_exact_pdf_and_recovers_one_committed_message(self):
        a, c, issue = self.actor, self.case, self.issue
        config = self.activate_delivery('synthetic_mailbox', attachment_required=True, schedule_days_ahead=2)
        writer, file = PdfWriter(), BytesIO()
        writer.add_blank_page(width=240, height=150)
        writer.write(file)
        pdf = file.getvalue()
        upload = CaseUpload.objects.create(case=c,actor=a,key='synthetic-invoice-pdf',name='test-invoice.pdf',
                                           sha256=sha256(pdf).hexdigest(),size=len(pdf))
        url = reverse('design_payment_reminder', args=[c.pk, issue.pk])
        self.client.force_login(a)
        values = {'action':'draft','revision':rev(c),'body':'Synthetic payment reminder.','subject':'Scheduled reminder',
                  'attachment':upload.pk}
        self.assertContains(self.client.post(url,values), 'Check the exact invoice')
        with patch('adapters.case_uploads.read',return_value=pdf):
            self.assertEqual(self.client.post(url,{**values,'attachment_checked':'on'}).status_code,302)
            item = issue.reminder_drafts.get()
            planned = (timezone.now()+timedelta(minutes=5)).replace(microsecond=0)
            result = self.client.post(url, {'action':'schedule','revision':rev(c),'draft':item.pk,
                                            'scheduled_for':planned.isoformat()},follow=True)
            self.assertContains(result,'Scheduled for')
            dispatched = PaymentReminderDispatch.objects.get()
            self.assertEqual(dispatched.scheduled_for,planned)
            self.assertIsNone(reminders.run_mailbox(dispatched.pk))
            with patch('apps.finance.reminders.timezone.now', return_value=planned+timedelta(seconds=5)):
                reminders.deliver_to_mailbox(dispatched.pk)
            self.assertEqual(PaymentReminderReceipt.objects.count(),0)
        # Simulate losing the worker after mailbox commit and before any business receipt.
        transition(a,config.pk,'revoked')
        receipt = reminders.run_mailbox(dispatched.pk)
        self.assertEqual(reminders.run_mailbox(dispatched.pk).pk,receipt.pk)
        self.assertTrue(receipt.delivered)
        [message] = PaymentReminderMailboxMessage.objects.all()
        parsed = BytesParser(policy=policy.default).parsebytes(bytes(message.message))
        self.assertEqual(str(parsed['To']), 'billing@example.invalid')
        self.assertEqual(next(parsed.iter_attachments()).get_payload(decode=True),pdf)
        route = reverse('design_reminder_download',args=[c.pk,issue.pk,item.pk,'email'])
        response = self.client.get(route)
        self.assertEqual(b''.join(response.streaming_content),bytes(message.message))
        self.assertIn('no-store',response['Cache-Control'])
        Grant.objects.filter(case=c,user=a,action='finance.reminder.read').update(active=False)
        self.assertEqual(self.client.get(route).status_code,403)

    def test_cancelled_schedule_and_changed_recipient_leave_mailbox_empty(self):
        a, c, issue = self.actor, self.case, self.issue
        self.activate_delivery('synthetic_mailbox',schedule_days_ahead=2)
        planned = timezone.now()+timedelta(minutes=5)
        first = reminders.draft(a,c.pk,issue.pk,'First reminder','Work with approved figures.',rev(c))
        reservation = reminders.dispatch(a,c.pk,issue.pk,first.pk,rev(c),scheduled_for=planned)
        reminders.cancel_schedule(a,c.pk,issue.pk,reservation.pk,rev(c))
        second = reminders.draft(a,c.pk,issue.pk,'Second reminder','Use the checked billing contact.',rev(c))
        second_reservation = reminders.dispatch(a,c.pk,issue.pk,second.pk,rev(c),scheduled_for=planned)
        save_contact(a,c,'billing',{'revision':rev(c),'evidence':self.policy,'customer':self.contact.customer,
                     'client_name':'Synthetic client','name':'Revised contact','email':'revised@example.invalid','role':'Billing'})
        with patch('apps.finance.reminders.timezone.now',return_value=planned+timedelta(seconds=5)):
            self.assertFalse(reminders.run_mailbox(reservation.pk).delivered)
            self.assertFalse(reminders.run_mailbox(second_reservation.pk).delivered)
        self.assertEqual(PaymentReminderMailboxMessage.objects.count(),0)


class StaffLifecycleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.root = users.objects.create_superuser('staff-technical')
        cls.operator = users.objects.create_user('staff-delegate')
        cls.successor = users.objects.create_user('staff-successor')
        actions = ['case.read','evidence.add','policy.configure','policy.activate','action.manage','action.own']
        cls.scope = {'format':'psl.tenant-access/v1','create_cases':True,'manage_access':True,'kinds':['project'],
                     'allowed_actions':actions,'initial_actions':actions,'classification':'synthetic',
                     'staff_lifecycle':{'invite_minutes':30,'allow_invite':True,'allow_deactivation':True}}
        intake.provision(cls.root,cls.operator,'staff-test',cls.scope,timezone.now()+timedelta(hours=2),True,'Synthetic delegated staff access')
        cls.case = intake.create_case(cls.operator,'staff-test','psl-staff','Staff lifecycle test','project')
        for action in ['case.read','action.own']:
            intake.change_access(cls.operator, cls.case.pk, cls.successor.pk, action, True, 'Exact synthetic successor grant')

    def test_invitation_renewal_acceptance_and_deactivation_reassigns_action(self):
        c,a = self.case,self.operator
        self.client.force_login(a)
        url = reverse('staff_invites', args=[c.pk])
        post = {'name':'Synthetic Staff','username':'synthetic-join','email':'join@example.invalid',
                'actions':['case.read','action.own'],'revision':rev(c)}
        invited = self.client.post(url,post)
        self.assertContains(invited,'Invitation is ready')
        old_token = urlsplit(invited.context['invitation_link']).fragment
        first = StaffInvitation.objects.get(username=post['username'])
        renewed = self.client.post(reverse('staff_renew_invite',args=[c.pk,first.pk]),{**post,'revision':rev(c)})
        token = urlsplit(renewed.context['invitation_link']).fragment
        self.assertNotEqual(old_token,token)
        password = 'Synthetic staff acceptance 8537'
        visitor = Client()
        join = reverse('staff_accept_invite')
        self.assertContains(visitor.post(join,{'token':old_token,'password':password,'confirm':password}), 'invitation is unavailable')
        self.assertEqual(visitor.post(join,{'token':token,'password':password,'confirm':password}).status_code,302)
        user = get_user_model().objects.get(username=post['username'])
        self.assertTrue(visitor.login(username=user.username,password=password))
        self.assertContains(visitor.post(join,{'token':token,'password':password,'confirm':password}), 'invitation is unavailable')
        self.assertNotIn(token,StaffInvitation.objects.get(username=user.username,number=2).token_hash)

        proof = add_evidence(a,c.pk,'policy_decision','Synthetic role examples','synthetic:test')
        activate(a,draft_roles(a,c.pk,[{'role':'PMO Lead','user_id':u.pk} for u in [user,self.successor]],
                               proof.pk,timezone.now()-timedelta(seconds=1)))
        due = timezone.now()+timedelta(days=3)
        item = create_action(a,c.pk,'staff-action','Verify synthetic milestone',user.pk,due,proof.pk,'Synthetic action',rev(c))
        departure = reverse('staff_departure',args=[c.pk,user.pk])
        self.assertContains(self.client.get(departure),'Verify synthetic milestone')
        result = self.client.post(departure,{'revision':rev(c),'reason':'Synthetic handover complete','evidence':proof.pk,
                                            f'reassign_{item.pk}':self.successor.pk}, follow=True)
        self.assertContains(result,'Workspace access removed')
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        item.refresh_from_db()
        self.assertEqual((item.current.owner_id,item.current.due_at),(self.successor.pk,due))
        self.assertEqual(item.states.get(number=1).owner_id,user.pk)
        self.assertEqual(visitor.get(reverse('case',args=[c.pk])).status_code,302)

    def test_secure_invitation_form_keeps_same_origin_csrf_protection(self):
        case = self.case
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.operator)
        path = reverse('staff_invites', args=[case.pk])
        page = browser.get(path, secure=True)
        self.assertEqual(page['Referrer-Policy'], 'same-origin')
        values = {'name':'HTTPS staff','username':'https-staff','email':'https-staff@example.invalid',
                  'actions':['case.read'],'revision':rev(case),'csrfmiddlewaretoken':browser.cookies['csrftoken'].value}
        self.assertEqual(browser.post(path, values, secure=True, headers={'Origin':'https://other.example'}).status_code,403)
        self.assertContains(browser.post(path, values, secure=True, headers={'Referer':'https://testserver'+path}), 'Invitation is ready')
        self.assertEqual(browser.get(reverse('staff_accept_invite'), secure=True)['Referrer-Policy'], 'same-origin')
