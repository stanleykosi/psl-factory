from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfWriter

from apps.agents.models import CaseUpload
from apps.core.evidence_access import public_evidence, public_timeline
from apps.core.models import Audit
from apps.finance import cash
from apps.finance.bank_receipt_capture import PROOF, SOURCE_POLICY
from apps.finance.models import CashAllocation, CashReceipt, CashVerification, InvoiceShortPaymentDecision
from apps.identity.models import Grant
from apps.policy.services import active_component, reference_values
from tests.billing_helpers import policy
from tests.helpers import rev
from tests.obligation_helpers import issue_identified
from tests.settlement_helpers import draft, fixture


def pdf_file(name, width=100):
    writer=PdfWriter()
    writer.add_blank_page(width=width,height=100)
    buffer=BytesIO()
    writer.write(buffer)
    return SimpleUploadedFile(name,buffer.getvalue(),content_type='application/pdf')


class BankReceiptCaptureTests(TestCase):
    def setUp(self):
        self.actor,self.case,self.coverage,prep,proof=fixture()
        self.proofs=proof
        self.issue=issue_identified(self.actor,self.case,draft(self.actor,self.case,prep,'SAMPLE-BANK-INVOICE'),proof)
        self.url=reverse('finance_record_payment',args=[self.case.pk,self.issue.pk])
        self.client.force_login(self.actor)
        self.at=(timezone.now()-timedelta(minutes=1)).isoformat()
        self.objects={}

    def report(self, amount='20', file=None):
        return self.client.post(self.url,{'action':'report','revision':rev(self.case),
            'customer':self.coverage.customer,'amount':amount,'currency':'NGN','amount_basis':'gross_including_tax',
            'received_at':self.at,'source':'synthetic-bank','transaction_ref':'TEST-BANK-TRANSFER-20',
            'locator':'test-reported-statement','file':file or pdf_file('reported-bank.pdf')})

    def verify(self, receipt_url, *, locator='', file=None):
        fields={'action':'verify','revision':rev(self.case),'role':'Finance','confirmed':'on','locator':locator}
        if file:fields['file']=file
        return self.client.post(receipt_url,fields)

    def test_report_verify_and_apply_retains_shortfall_and_private_statement(self):
        initial=cash.open_amount(self.issue)
        self.assertGreater(initial,20)
        self.assertContains(self.client.get(self.url),'Record reported payment')
        with (patch('adapters.case_uploads.put',side_effect=self.objects.__setitem__),
              patch('adapters.case_uploads.read',side_effect=lambda p:self.objects[p.key]) as private_read):
            posted=self.report()
            self.assertEqual(posted.status_code,302)
            receipt=CashReceipt.objects.get(case=self.case)
            receipt_url=reverse('finance_bank_receipt',args=[self.case.pk,self.issue.pk,receipt.pk])
            self.assertRedirects(posted,receipt_url)
            self.assertEqual(self.report().status_code,302)
            self.assertEqual(CashReceipt.objects.filter(case=self.case).count(),1)
            self.assertEqual(Audit.objects.filter(case=self.case,action=PROOF).count(),1)
            self.assertFalse(CashVerification.objects.filter(receipt=receipt).exists())
            self.assertEqual(cash.open_amount(self.issue),initial)
            self.assertNotContains(self.client.get(receipt_url),'Apply verified payment')
            self.assertRedirects(self.verify(receipt_url),receipt_url)
            lot=CashVerification.objects.get(receipt=receipt)
            self.assertEqual(lot.amount,20)
            self.assertFalse(CashAllocation.objects.filter(lot=lot).exists())
            self.assertContains(self.client.get(receipt_url),'Apply verified payment')
            self.assertEqual(cash.open_amount(self.issue),initial)
            fields={'action':'allocate','revision':rev(self.case),'role':'Finance','key':'sample-bank-apply',
                    'amount':'20','reason':'Confirmed synthetic payment applied to this exact invoice.'}
            self.assertRedirects(self.client.post(receipt_url,fields),receipt_url)
            allocation=CashAllocation.objects.get(lot=lot,issue=self.issue)
            self.assertEqual(allocation.amount,20)
            self.assertEqual(cash.open_amount(self.issue),initial-20)
            self.assertFalse(InvoiceShortPaymentDecision.objects.filter(issue=self.issue).exists())
            self.assertContains(self.client.get(receipt_url),'Review the remaining balance')
            self.assertEqual(CashReceipt.objects.get(pk=receipt.pk).payload,receipt.payload)
            self.assertFalse(CaseUpload.objects.filter(case=self.case).exists())
            self.assertFalse(public_evidence(self.case.evidence.all()).filter(pk__in=[receipt.evidence_id,lot.evidence_id]).exists())
            self.assertFalse(public_timeline(self.case).filter(action=PROOF).exists())
            proof_url=reverse('finance_bank_proof',args=[self.case.pk,self.issue.pk,receipt.pk,'report'])
            downloaded=self.client.get(proof_url)
            self.assertEqual(downloaded.status_code,200)
            self.assertTrue(b''.join(downloaded.streaming_content).startswith(b'%PDF-'))
            cash.reverse(self.actor,self.case.pk,'allocation',allocation.pk,'Finance',
                         self.proofs['cash_correction'].pk,'Correct only the synthetic allocation.',rev(self.case))
            self.assertEqual(cash.open_amount(self.issue),initial)
            self.assertEqual(cash.cash_remaining(lot),20)
            self.assertEqual(CashReceipt.objects.get(pk=receipt.pk).payload,receipt.payload)
            reader=get_user_model().objects.create_user(username='ordinary-finance-reader')
            for action in ('case.read','finance.read'):
                Grant.objects.create(case=self.case,user=reader,action=action)
            self.client.force_login(reader)
            self.assertNotContains(self.client.get(receipt_url),'reported-bank.pdf')
            before=private_read.call_count
            self.assertEqual(self.client.get(proof_url).status_code,403)
            self.assertEqual(private_read.call_count,before)

    def test_unknown_amount_and_storage_failure_do_not_create_verified_cash(self):
        initial=cash.open_amount(self.issue)
        with (patch('adapters.case_uploads.put',side_effect=OSError('simulated storage error')) as put,
              patch('adapters.case_uploads.discard_unbound') as discard):
            response=self.report()
            self.assertContains(response,'Private bank proof storage is unavailable')
            discard.assert_called_once_with(put.call_args.args[0])
        self.assertFalse(CashReceipt.objects.filter(case=self.case).exists())
        with patch('adapters.case_uploads.put',side_effect=self.objects.__setitem__):
            response=self.report(amount='')
        self.assertEqual(response.status_code,302)
        receipt=CashReceipt.objects.get(case=self.case)
        self.assertIsNone(receipt.payload['amount'])
        self.assertContains(self.client.get(response.url),'The reported amount is unknown')
        self.assertEqual(self.verify(response.url).status_code,403)
        self.assertFalse(CashVerification.objects.filter(receipt=receipt).exists())
        self.assertEqual(cash.open_amount(self.issue),initial)

    def test_configured_independence_requires_actual_distinct_bytes_and_locator(self):
        current=active_component(SOURCE_POLICY,self.case)
        scope=reference_values(current)[0]
        policy(self.actor,self.case,SOURCE_POLICY,{**scope,'require_independent_evidence':True})
        with patch('adapters.case_uploads.put',side_effect=self.objects.__setitem__):
            posted=self.report()
            self.assertEqual(posted.status_code,302)
            same=self.verify(posted.url,locator='separate-verification',file=pdf_file('renamed-same-file.pdf'))
            self.assertContains(same,'different statement reference and independent file')
            self.assertFalse(CashVerification.objects.filter(receipt__case=self.case).exists())
            self.assertRedirects(self.verify(posted.url,locator='separate-verification',file=pdf_file('bank-check.pdf',101)),
                                 posted.url)
        self.assertEqual(CashVerification.objects.filter(receipt__case=self.case).count(),1)
