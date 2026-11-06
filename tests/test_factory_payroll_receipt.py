"""Recipient acknowledgement is native receipt truth, not work or message state."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from apps.core.models import Audit
from apps.identity.models import Grant
from apps.finance import payroll as native
from apps.finance.payroll_models import PayrollReportReceipt
from apps.policy.payroll_validators import REPORT
from apps.workflows import factory_payroll as payroll
from apps.workflows.factory_payroll_views import presentation
from tests import test_factory_payroll as baseline
from tests.payroll_helpers import approve,policy
from tests.helpers import rev


class PayrollReceiptConsoleTests(TestCase):
    rowsets=baseline.FactoryPayrollTests.rowsets

    @classmethod
    def setUpTestData(cls):
        baseline.FactoryPayrollTests.setUpTestData.__func__(cls)
        f=cls.f;actor=f['preparer'];case=f['case']
        cls.other=get_user_model().objects.create_user(username='payroll-second-recipient',password='test-only')
        for action in ['case.read','payroll.read','payroll.report.read','payroll.report.receive','factory.read']:
            Grant.objects.create(case=case,user=cls.other,action=action)
        policy(f,REPORT,{**f['config']['report'],'recipient_ids':[f['manager'].pk,cls.other.pk]})
        inputs={'input_ids':[i.pk for i in f['inputs']],'hr_snapshot_id':f['hr'].pk}
        cls.work=payroll.start(actor,case.pk,'RECEIPT-UX',f['request'].pk,inputs,'Synthetic receipt acknowledgement',rev(case))
        for i in f['inputs']:approve(f,i)
        r=native.combine(actor,case.pk,f['request'].pk,inputs['input_ids'],payroll.key(cls.work,'combine'),rev(case));approve(f,r)
        r=native.match(actor,case.pk,r.pk,f['hr'].pk,payroll.key(cls.work,'match'),rev(case));approve(f,r)
        r=native.aggregate(actor,case.pk,r.pk,payroll.key(cls.work,'aggregate'),rev(case));approve(f,r)
        cls.publication=payroll.human_action(actor,cls.work.pk,cls.work.revision,rev(case),'publish',{})

    def setUp(self):
        self.client.force_login(self.f['manager'])
        self.url=reverse('factory_detail',args=[self.work.pk])

    def payload(self,**overrides):
        return {'action':'receive','revision':self.work.revision,'case_revision':rev(self.f['case']),'publication_id':self.publication.pk,**overrides}

    def acknowledge(self):
        response=self.client.post(self.url,self.payload())
        self.assertEqual(response.status_code,302)
        return PayrollReportReceipt.objects.get(publication=self.publication,actor=self.f['manager'])

    def assert_recorded(self,response,receipt):
        self.assertContains(response,'Receipt acknowledged')
        self.assertContains(response,f'Receipt #{receipt.pk} · Aggregate report #{receipt.publication_id}')
        self.assertContains(response,'No further acknowledgement is needed.')
        self.assertNotContains(response,'Acknowledge receipt as myself')
        self.assertNotContains(response,'Inspect restricted payroll input')
        self.assertEqual(response.context['row']['payroll']['receipt'].created_at,receipt.created_at)
        self.assertFalse(response.context['row']['needs_me'])
        for private in ['E001','E002','employee_id','BASIC']:
            self.assertNotContains(response,private)

    def test_first_receipt_and_fresh_post_replay_return_original_identity_without_duplicate(self):
        self.assertEqual(connection.vendor,'postgresql')
        before=self.rowsets();response=self.client.get(self.url)
        self.assertContains(response,'Acknowledge receipt as myself')
        self.assertNotContains(response,'Receipt acknowledged')
        self.assertIsNone(response.context['row']['payroll']['receipt'])
        self.assertTrue(response.context['row']['needs_me'])
        self.assertEqual(self.rowsets(),before)
        receipt=self.acknowledge();before=self.rowsets()
        response=self.client.get(self.url);self.assert_recorded(response,receipt)
        self.assertContains(response,f'Your receipt #{receipt.pk} for aggregate report #{receipt.publication_id} is recorded.')
        self.assertEqual(self.rowsets(),before)
        response=self.client.post(self.url,self.payload(),follow=True);self.assert_recorded(response,receipt)
        self.assertContains(response,f'Your receipt #{receipt.pk} for aggregate report #{receipt.publication_id} is recorded.')
        original=payroll.human_action(self.f['manager'],self.work.pk,self.work.revision,rev(self.f['case']),'receive',{'publication_id':self.publication.pk})
        self.assertEqual((original.pk,original.created_at),(receipt.pk,receipt.created_at))
        self.assertEqual(PayrollReportReceipt.objects.count(),1)
        self.assertEqual(Audit.objects.filter(action='payroll.report_receipt').count(),1)
        self.assertEqual(self.rowsets(),before)
        self.assertNotEqual(self.work.status,'verified')

    def test_stale_duplicate_post_preserves_receipt_and_native_revision_guard(self):
        original_payload=self.payload();receipt=self.acknowledge()
        self.client.get(self.url)  # Consume the original POST notification before replay.
        before=self.rowsets();response=self.client.post(self.url,original_payload)
        self.assert_recorded(response,receipt)
        self.assertContains(response,'Stale revision; refresh before retrying')
        self.assertNotContains(response,f'Your receipt #{receipt.pk} for aggregate report #{receipt.publication_id} is recorded.')
        self.assertEqual(self.rowsets(),before)

    def test_receipt_is_personal_not_another_recipients_acknowledgement(self):
        first=self.acknowledge();self.client.force_login(self.other);before=self.rowsets()
        response=self.client.get(self.url)
        self.assertContains(response,'Acknowledge receipt as myself')
        self.assertNotContains(response,f'Receipt #{first.pk} · Aggregate report')
        self.assertIsNone(response.context['row']['payroll']['receipt'])
        self.assertTrue(response.context['row']['needs_me'])
        self.assertEqual(self.rowsets(),before)
        response=self.client.post(self.url,self.payload(),follow=True)
        second=PayrollReportReceipt.objects.get(publication=self.publication,actor=self.other)
        self.assertNotEqual(first.pk,second.pk);self.assert_recorded(response,second)
        self.assertEqual(PayrollReportReceipt.objects.count(),2)
        self.assertNotContains(response,f'Receipt #{first.pk} · Aggregate report')

    def test_revoked_report_read_hides_existing_receipt_and_blocks_replay(self):
        receipt=self.acknowledge()
        Grant.objects.filter(case=self.f['case'],user=self.f['manager'],action='payroll.report.read').update(active=False)
        before=self.rowsets()
        for response in [self.client.get(self.url),self.client.post(self.url,self.payload())]:
            self.assertEqual(response.status_code,403)
            self.assertNotContains(response,'Receipt acknowledged',status_code=403)
            self.assertNotContains(response,f'Receipt #{receipt.pk} · Aggregate report',status_code=403)
        self.assertEqual(self.rowsets(),before)

    def test_revoked_source_review_hides_receipt_without_erasing_it(self):
        receipt=self.acknowledge();approve(self.f,payroll.run(self.work,'aggregate'),'revoke-receipt-report','revoke')
        before=self.rowsets()
        for response in [self.client.get(self.url),self.client.post(self.url,self.payload())]:
            self.assertEqual(response.status_code,403)
            self.assertNotContains(response,'Receipt acknowledged',status_code=403)
        self.assertEqual(self.rowsets(),before)
        self.assertEqual(PayrollReportReceipt.objects.get(pk=receipt.pk).created_at,receipt.created_at)

    def test_wrong_publication_and_revoked_receive_never_claim_receipt(self):
        before=self.rowsets();response=self.client.post(self.url,self.payload(publication_id=self.publication.pk+99999))
        self.assertContains(response,'Select this work exact aggregate publication')
        self.assertContains(response,'Acknowledge receipt as myself')
        self.assertNotContains(response,'Your receipt is recorded')
        self.assertEqual(self.rowsets(),before)
        Grant.objects.filter(case=self.f['case'],user=self.f['manager'],action='payroll.report.receive').update(active=False)
        before=self.rowsets();response=self.client.post(self.url,self.payload());self.assertEqual(response.status_code,403)
        with self.assertRaises(PermissionDenied):
            payroll.human_action(self.f['manager'],self.work.pk,self.work.revision,rev(self.f['case']),'receive',{'publication_id':self.publication.pk})
        self.assertFalse(PayrollReportReceipt.objects.exists());self.assertEqual(self.rowsets(),before)

    def test_acknowledged_get_head_and_queue_presentation_are_read_only(self):
        receipt=self.acknowledge();before=self.rowsets()
        for _ in range(2):
            self.assert_recorded(self.client.get(self.url),receipt)
            self.assertEqual(self.client.head(self.url).status_code,200)
            row=presentation(self.f['manager'],self.work)
            self.assertEqual(row['state'],'Receipt acknowledged');self.assertFalse(row['needs_me'])
            self.assertEqual(row['payroll']['receipt'].pk,receipt.pk)
        self.assertEqual(self.rowsets(),before)
