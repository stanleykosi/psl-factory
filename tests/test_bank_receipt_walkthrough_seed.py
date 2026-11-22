from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfReader

from apps.core.models import Case
from apps.finance import cash
from apps.finance.models import CashReceipt, CashVerification, InvoiceIssue, InvoiceShortPaymentDecision
from apps.identity.models import Grant
from tests import railway_bank_receipt_walkthrough_seed as sample
from tests.helpers import rev


class BankReceiptWalkthroughFixtureTests(TestCase):
    def test_trial_records_and_independently_proves_new_payment_without_touching_prior_allocation(self):
        trial=get_user_model().objects.create_user(sample.TRIAL)
        with patch.dict('os.environ',{sample.GUARD:'0'}), self.assertRaises(RuntimeError):
            sample.prepare()
        self.assertFalse(Case.objects.filter(pk=sample.CASE_ID).exists())
        with patch.dict('os.environ',{sample.GUARD:'1'}):
            data=sample.prepare()
            self.assertEqual(sample.prepare(),{**data,'preserved':True})
        case=Case.objects.get(pk=data['case'])
        issue=InvoiceIssue.objects.get(pk=data['issue'],invoice__case=case)
        prior=cash.allocations(issue=issue).get(pk=data['prior_allocation'])
        self.assertNotEqual(prior.actor_id,trial.pk)
        self.assertEqual(set(Grant.objects.filter(user=trial,case=case,active=True).values_list('action',flat=True)),
                         sample.TRIAL_ACTIONS)
        self.assertFalse(data['reported'])
        self.assertFalse(data['applied'])
        self.assertEqual(cash.open_amount(issue),sample.FACE-sample.PRIOR)
        facts=data['facts']
        proofs={kind:sample.pdf_bytes(facts,kind) for kind in data['filenames']}
        self.assertNotEqual(proofs['report'],proofs['verification'])
        for kind, content in proofs.items():
            text=PdfReader(BytesIO(content)).pages[0].extract_text()
            self.assertIn('NGN 12.50',text)
            self.assertIn(data['locators'][kind],text)
            self.assertIn(facts['transaction_ref'],text)

        def upload(kind):
            return SimpleUploadedFile(data['filenames'][kind],proofs[kind],content_type='application/pdf')

        self.client.force_login(trial)
        self.assertContains(self.client.get(data['record_path']),'Record reported payment')
        private={}
        with patch('adapters.case_uploads.put',side_effect=private.__setitem__):
            reported=self.client.post(data['record_path'],{**facts,'received_at':data['received_local'],
                'action':'report','revision':rev(case),'locator':data['locators']['report'],'file':upload('report')})
            receipt=CashReceipt.objects.get(case=case,transaction_ref=sample.TRANSFER,actor=trial)
            receipt_url=reverse('finance_bank_receipt',args=[case.pk,issue.pk,receipt.pk])
            self.assertRedirects(reported,receipt_url)
            self.assertEqual(cash.open_amount(issue),sample.FACE-sample.PRIOR)
            form={'action':'verify','revision':rev(case),'role':'Finance','confirmed':'on',
                  'locator':data['locators']['verification']}
            self.assertContains(self.client.post(receipt_url,{**form,'file':upload('report')}),
                                'The rule requires a different statement reference and independent file.')
            self.assertFalse(CashVerification.objects.filter(receipt=receipt).exists())
            self.assertRedirects(self.client.post(receipt_url,{**form,'file':upload('verification')}),receipt_url)
            lot=CashVerification.objects.get(receipt=receipt,actor=trial,amount=sample.PAYMENT)
            self.assertEqual(cash.open_amount(issue),sample.FACE-sample.PRIOR)
            allocation=self.client.get(receipt_url).context['allocation']
            result=self.client.post(receipt_url,{
                'action':'allocate','revision':rev(case),'role':'Finance','key':allocation.initial['key'],
                'amount':data['allocation_amount'],'reason':data['reason'],
            })
            self.assertRedirects(result,receipt_url)
        self.assertEqual(set(private.values()),set(proofs.values()))
        new=cash.allocations(lot=lot,issue=issue).get(actor=trial,amount=sample.PAYMENT)
        self.assertEqual(cash.open_amount(issue),sample.REMAINING)
        self.assertTrue(cash.allocations(issue=issue).filter(pk=prior.pk,amount=sample.PRIOR).exists())
        self.assertFalse(InvoiceShortPaymentDecision.objects.filter(issue=issue).exists())
        payment=self.client.get(receipt_url)
        self.assertContains(payment,'14.75')
        self.assertContains(payment,'Review the remaining balance')
        with patch.dict('os.environ',{sample.GUARD:'1'}):
            preserved=sample.prepare()
        self.assertTrue(preserved['preserved'])
        self.assertEqual((preserved['reported'],preserved['applied']),(receipt.pk,new.pk))
        self.assertEqual(preserved['prior_allocation'],prior.pk)
