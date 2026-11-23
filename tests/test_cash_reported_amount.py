from concurrent.futures import ThreadPoolExecutor
import json
from queue import Queue
from threading import Event
from time import monotonic
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.core.services import add_evidence
from apps.finance import cash, cash_reported_amount
from apps.finance.models import CashAllocation, CashReceipt, CashReportedAmount, CashVerification
from apps.identity.models import Grant
from tests.helpers import rev
from tests.obligation_helpers import issue_identified
from tests.settlement_helpers import draft, fixture, receipt
from tests.test_bank_receipt_capture import pdf_file


def supplied_proof(actor, case, original, *, kind='cash_report', **changes):
    return add_evidence(actor,case.pk,kind,json.dumps({**original.payload,'amount':'12.50',**changes}),
                        'synthetic:separate-bank-statement')


class CashReportedAmountTests(TestCase):
    def setUp(self):
        self.actor,self.case,self.coverage,self.preparation,self.proof=fixture()

    def test_distinct_source_and_direct_first_lot_cannot_bypass_current_amount(self):
        actor,case=self.actor,self.case
        original,_=receipt(actor,case,amount=None,ref='sample-unverified-original',verify=False)
        other,_=receipt(actor,case,amount=None,ref='sample-unverified-other',verify=False)
        proof=supplied_proof(actor,case,original)
        verification=supplied_proof(actor,case,original,kind='cash_verification')
        with self.assertRaisesMessage(ValidationError,'exact reported known cash facts'):
            cash.verify(actor,case.pk,original.pk,'Finance',verification.pk,rev(case))
        with self.assertRaisesMessage(ValidationError,'same bank source and original receipt facts'):
            cash_reported_amount.record(actor,case.pk,other.pk,proof.pk,'Same reference only.',rev(case))
        with self.assertRaisesMessage(DatabaseError,'Exact original Unknown receipt'),transaction.atomic():
            CashReportedAmount.objects.create(receipt=other,evidence=proof,payload={**original.payload,'amount':'12.5'},
                                              reason='Wrong bank transfer.',actor=actor)

        supplied=cash_reported_amount.record(actor,case.pk,original.pk,proof.pk,'Bank confirmed original amount.',rev(case))
        self.assertEqual(cash_reported_amount.record(actor,case.pk,original.pk,proof.pk,supplied.reason,rev(case)),supplied)
        _,amount,authority,_=cash.guard_verify(actor,case,original.pk,'Finance',verification.pk)
        with self.assertRaisesMessage(DatabaseError,'First verification requires the exact current reported amount'),transaction.atomic():
            CashVerification.objects.create(receipt=original,amount=amount,evidence=verification,authority=authority,actor=actor)
        with self.assertRaisesMessage(DatabaseError,'First verification requires the exact current reported amount'),transaction.atomic():
            CashVerification.objects.create(receipt=other,amount=amount,evidence=verification,reported_amount=supplied,
                                            authority=authority,actor=actor)

        lot=cash.verify(actor,case.pk,original.pk,'Finance',verification.pk,rev(case))
        self.assertEqual(lot.reported_amount_id,supplied.pk)
        self.assertEqual(lot.authority['reported_amount']['evidence'],proof.pk)
        self.assertEqual(cash.lot_payload(lot)['amount'],'12.5')
        self.assertFalse(CashAllocation.objects.filter(lot=lot).exists())
        original.refresh_from_db()
        self.assertIsNone(original.payload['amount'])
        late=supplied_proof(actor,case,original,amount='13.50')
        with self.assertRaisesMessage(ValidationError,'already has a verified lot'):
            cash_reported_amount.record(actor,case.pk,original.pk,late.pk,'Subsequent bank statement.',rev(case))

    def test_supply_holds_only_verification_when_source_authority_or_config_is_missing(self):
        from apps.policy.services import active_component, transition

        actor,case=self.actor,self.case
        original,_=receipt(actor,case,amount=None,ref='sample-unverified-source-hold',verify=False)
        writer=get_user_model().objects.create_user(username='unrelated-cash-recorder')
        for action in cash_reported_amount.AUTHOR_ACTIONS:
            Grant.objects.create(case=case,user=writer,action=action)
        proof=supplied_proof(actor,case,original)
        with self.assertRaises(PermissionDenied):
            cash_reported_amount.record(writer,case.pk,original.pk,proof.pk,'Different recorder.',rev(case))
        bank=active_component('D14.receipt_verification_source_ref',case)
        transition(actor,bank.pk,'revoked')
        supplied=cash_reported_amount.record(actor,case.pk,original.pk,proof.pk,'Amount read on the bank file.',rev(case))
        verification=supplied_proof(actor,case,original,kind='cash_verification')
        with self.assertRaises(ValidationError):
            cash.verify(actor,case.pk,original.pk,'Finance',verification.pk,rev(case))
        Grant.objects.filter(case=case,user=actor,action='finance.cash.record').update(active=False)
        with self.assertRaises(PermissionDenied):
            cash.verify(actor,case.pk,original.pk,'Finance',verification.pk,rev(case))
        self.assertEqual(CashReportedAmount.objects.get(receipt=original),supplied)
        self.assertFalse(CashVerification.objects.filter(receipt=original).exists())


class CashReportedAmountBrowserTests(TestCase):
    def test_unknown_bank_amount_upload_and_fresh_exact_verification(self):
        actor,case,_,preparation,proof=fixture()
        issue=issue_identified(actor,case,draft(actor,case,preparation,'SAMPLE-UNKNOWN-BANK'),proof)
        self.client.force_login(actor)
        original,_=receipt(actor,case,amount=None,ref='sample-bank-readback',verify=False)
        url=reverse('finance_bank_receipt',args=[case.pk,issue.pk,original.pk])
        balance=cash.open_amount(issue)
        self.assertContains(self.client.get(url),'Record confirmed amount')
        stored={}
        with (patch('adapters.case_uploads.put',side_effect=stored.__setitem__),
              patch('adapters.case_uploads.read',side_effect=lambda proof:stored[proof.key]) as read):
            api = f'/api/v1/projects/{case.pk}/invoices/{issue.pk}/payments/{original.pk}'
            self.assertTrue(self.client.get(api).json()['can_supply_amount'])
            captured = self.client.post(api + '/reported-amount', {
                'revision':rev(case),'amount':'12.50','locator':'confirmed-original-transfer',
                'reason':'Read a confirmed amount on the original bank transaction.',
                'file':pdf_file('sample-confirmed-amount.pdf'),
            })
            self.assertEqual(captured.status_code, 201, captured.content)
            supplied=CashReportedAmount.objects.get(receipt=original)
            self.assertEqual(self.client.get(api).json()['amount_update_id'], supplied.pk)
            page=self.client.get(url)
            self.assertContains(page,'<dt>Reported amount</dt><dd>Unknown</dd>',html=True)
            self.assertContains(page,'Amount supplied from bank proof')
            self.assertContains(page,'sample-confirmed-amount.pdf')
            self.assertNotContains(page,'Apply verified payment')
            verify={'action':'verify','revision':rev(case),'role':'Finance','confirmed':'on'}
            self.assertContains(self.client.post(url,verify),'Review the current reported amount and proof')
            self.assertFalse(CashVerification.objects.filter(receipt=original).exists())
            self.assertEqual(read.call_count,0)
            self.assertRedirects(self.client.post(url,{**verify,'reported_amount_id':supplied.pk}),url)
            self.assertEqual(CashVerification.objects.get(receipt=original).reported_amount_id,supplied.pk)
            self.assertEqual(cash.open_amount(issue),balance)
            self.assertIsNone(CashReceipt.objects.get(pk=original.pk).payload['amount'])

            reader=get_user_model().objects.create_user(username='payment-read-only')
            for action in ('case.read','finance.read'):
                Grant.objects.create(case=case,user=reader,action=action)
            self.client.force_login(reader)
            self.assertNotContains(self.client.get(url),'sample-confirmed-amount.pdf')
            before=read.call_count
            source_url=reverse('finance_bank_proof',args=[case.pk,issue.pk,original.pk,'reported-amount'])
            self.assertEqual(self.client.get(source_url).status_code,403)
            self.assertEqual(read.call_count,before)


class CashReportedAmountConcurrencyTests(TransactionTestCase):
    def test_competing_direct_first_lot_waits_for_supplement_and_cannot_bypass_pin(self):
        actor,case,_,_,_=fixture()
        original,_=receipt(actor,case,amount=None,ref='sample-bank-concurrency',verify=False)
        proof=supplied_proof(actor,case,original)
        evidence=supplied_proof(actor,case,original,kind='cash_verification')
        revision=rev(case)
        written,commit=Event(),Event()
        backend=Queue()

        def write_supplement():
            close_old_connections()
            try:
                with transaction.atomic():
                    supply=cash_reported_amount.record(actor,case.pk,original.pk,proof.pk,
                                                       'The bank confirmed this exact amount.',revision)
                    written.set()
                    if not commit.wait(15):
                        raise RuntimeError('Timed out while holding the exact receipt transaction.')
                return supply.pk
            finally:
                close_old_connections()

        def write_unpinned_lot():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()')
                    backend.put(cursor.fetchone()[0])
                CashVerification.objects.create(receipt=original,evidence=evidence,amount='12.50',authority={},actor=actor)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            supplement=pool.submit(write_supplement)
            try:
                self.assertTrue(written.wait(10))
                racing=pool.submit(write_unpinned_lot)
                pid=backend.get(timeout=5)
                expires=monotonic()+5
                with connection.cursor() as cursor:
                    while monotonic()<expires:
                        cursor.execute('SELECT cardinality(pg_blocking_pids(%s))',[pid])
                        if cursor.fetchone()[0]:
                            break
                        Event().wait(.05)
                    else:
                        self.fail('The competing first verification did not wait for the original receipt lock.')
            finally:
                commit.set()
            supplied_id=supplement.result(timeout=10)
            with self.assertRaisesMessage(DatabaseError,'First verification requires the exact current reported amount'):
                racing.result(timeout=10)

        self.assertFalse(CashVerification.objects.filter(receipt=original).exists())
        lot=cash.verify(actor,case.pk,original.pk,'Finance',evidence.pk,rev(case))
        self.assertEqual(lot.reported_amount_id,supplied_id)
