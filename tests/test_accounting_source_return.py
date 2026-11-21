from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Audit, Case, Evidence
from apps.documents.models import Publication
from apps.finance.models import FinanceReview, FinanceSource
from apps.identity import staff
from apps.identity.models import Grant
from apps.workflows import factory, factory_accounting as accounts, factory_accounting_intake as intake
from apps.workflows.factory_accounting_corrections import LINKED
from apps.workflows.models import FactoryWork, HumanTask
from tests import railway_accounting_source_return_seed as seed, railway_admitted_schedule_seed as admitted
from tests.helpers import rev
from tests.test_staff_profiles import configured


class AccountingSourceReturnTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        identity = configured()
        cls.staff_case = identity['scopes'][0]['case']
        invitation, token = staff.invite(identity['actor'], cls.staff_case.pk, seed.ADMITTED_USERNAME,
            'Sample accounting preparer', 'sample-returning-accounts@example.invalid', ['case.read'], rev(cls.staff_case),
            profile_key='sample-reader')
        cls.maker = staff.accept(token, 'Synthetic!accounting-source.207')
        cls.reviewer = get_user_model().objects.create_user('psl-agent-trial')
        with patch.multiple(admitted, ADMISSION_TENANT='staff-accounts', ADMISSION_PROFILE='sample-reader'):
            cls.sample = seed.prepare(invitation.pk, cls.maker.pk)
        cls.case = Case.objects.get(pk=cls.sample['case'])
        cls.work = FactoryWork.objects.get(pk=cls.sample['work'])
        cls.csv = Path(settings.BASE_DIR, seed.CSV_PATH).read_bytes()

    def decide(self, work, task, verdict, reason):
        path = reverse('factory_invoice_decision', args=[work.pk])
        decision_queue = f'{path}?queue=needs_me&q='
        self.assertRedirects(self.client.post(path, {'action': 'claim', 'task': task.pk, 'task_revision': task.revision}),
                             decision_queue, fetch_redirect_response=False)
        task.refresh_from_db()
        self.assertRedirects(self.client.post(path, {'action': 'decide', 'task': task.pk, 'task_revision': task.revision,
            'verdict': verdict, 'evidence': self.sample['review_proof'], 'reason': reason}),
            decision_queue, fetch_redirect_response=False)

    def returned(self):
        self.client.force_login(self.reviewer)
        task = HumanTask.objects.get(pk=self.sample['source_task'])
        self.decide(self.work, task, 'return', self.sample['return_reason'])
        self.work.refresh_from_db()
        self.assertEqual(self.work.status, 'followup_needed')
        return FinanceReview.objects.get(source_id=self.sample['source'], verdict='return')

    def form(self, decision, data=None):
        page = self.client.get(self.sample['correction'])
        self.assertContains(page, 'Correct a returned trial balance')
        self.assertContains(page, self.sample['return_reason'])
        form = page.context['supplied_form']
        self.assertEqual(form.initial['correction_decision'], decision.pk)
        return {
            'action': 'supplied', 'supplied-key': form.initial['key'], 'supplied-revision': rev(self.case),
            'supplied-correction_head': self.work.source_head_id, 'supplied-correction_decision': decision.pk,
            'supplied-source_evidence': self.sample['extraction_proof'],
            'supplied-extracted_at': self.sample['extracted_at'], 'supplied-completeness': 'complete',
            'supplied-reference': 'Corrected fictional October accounts', 'supplied-inventory_confirmed': 'on',
            'supplied-control_total': self.sample['control_total'],
            'supplied-upload': SimpleUploadedFile('corrected.csv', self.csv if data is None else data),
        }

    def test_source_return_upload_and_units_lead_to_fresh_exact_review_with_history(self):
        self.assertEqual(connection.vendor, 'postgresql')
        with patch.dict('os.environ', {seed.GUARD: '0', 'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT,
                                       'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance', 'PGDATABASE': 'isolated-preview'}):
            with self.assertRaisesMessage(RuntimeError, 'returned accounting source fixture guard'):
                seed.run()
        decision = self.returned()
        original_head, original_revision = self.work.source_head_id, self.work.revision
        self.assertNotContains(self.client.get(self.sample['recovery']), 'Correct and resubmit')
        self.assertEqual(self.client.get(self.sample['correction']).status_code, 404)
        self.client.force_login(self.maker)
        self.assertContains(self.client.get(self.sample['recovery']), 'Correct and resubmit')
        uploaded = self.client.post(self.sample['correction'], self.form(decision))
        self.assertEqual(uploaded.status_code, 302)
        original_receipt = Audit.objects.get(case=self.case, action=intake.RECEIPT)
        held = intake.latest(original_receipt)
        self.assertEqual(held['status'], 'source_units_needed')
        self.assertNotEqual(held['batch'], self.sample['batch'])
        self.assertFalse(Audit.objects.filter(case=self.case, action=LINKED).exists())
        self.assertEqual(FactoryWork.objects.filter(case=self.case).count(), 1)
        page = self.client.get(uploaded.url)
        units = page.context['receipts'][0]['confirm_url']
        self.assertContains(page, 'Confirm file units')
        self.assertContains(self.client.get(units), 'Confirm units and resubmit')
        accepted = self.client.post(units, {'action': 'confirm_units', 'unit': 'major_currency',
            'proof': self.sample['extraction_proof'], 'note': 'The corrected fictional extract is in individual naira.',
            'revision': rev(self.case)})
        link = Audit.objects.get(case=self.case, action=LINKED)
        new = FactoryWork.objects.get(case=self.case, pk=link.data['work'])
        self.assertRedirects(accepted, reverse('factory_detail', args=[new.pk]), fetch_redirect_response=False)
        self.assertEqual((link.data['previous_work'], link.data['previous_head'], link.data['return_decision']),
                         (self.work.pk, original_head, decision.pk))
        self.assertEqual(link.data['new_batch'], held['batch'])
        current = FinanceSource.objects.get(pk=link.data['source'])
        self.assertEqual(next(row['amount'] for row in current.batch.rows if row['account'] == 'direct_cost'), '199')
        self.assertFalse(FinanceReview.objects.filter(source=current).exists())
        self.assertContains(self.client.get(accepted.url), 'Review the original returned work')
        self.assertContains(self.client.get(self.sample['recovery']), 'Open corrected accounting work')
        self.assertNotContains(self.client.get(self.sample['recovery']), 'Record reviewed inputs')
        with self.assertRaisesMessage(ValidationError, 'Open the corrected accounting work'):
            accounts.recheck(self.maker, self.work.pk, original_revision, self.sample['source'], [], 'Attempt to reopen')
        self.work.refresh_from_db()
        self.assertEqual((self.work.source_head_id, self.work.revision, self.work.status),
                         (original_head, original_revision, 'followup_needed'))
        self.assertEqual(HumanTask.objects.get(pk=self.sample['source_task']).status, 'returned')
        self.assertEqual(FinanceReview.objects.get(pk=decision.pk).verdict, 'return')
        factory.run_until_wait(new.pk)
        task = HumanTask.objects.get(case=self.case, kind='factory_accounting_review', status='open',
                                     context__work=new.pk, context__purpose='source')
        self.assertEqual(task.context['packet']['target'], current.pk)
        self.client.force_login(self.reviewer)
        self.decide(new, task, 'approve', 'Checked the corrected same-period extract and its source evidence.')
        self.assertEqual(FinanceReview.objects.get(source=current).actor_id, self.reviewer.pk)
        self.assertFalse(Publication.objects.filter(factory_work__in=(self.work, new)).exists())

    def test_stale_return_and_wrong_period_never_link_corrected_work(self):
        decision = self.returned()
        self.client.force_login(self.maker)
        count = Evidence.objects.filter(case=self.case, kind='financial_input').count()
        wrong_pin = self.form(decision) | {'supplied-correction_decision': decision.pk + 1}
        self.assertContains(self.client.post(self.sample['correction'], wrong_pin), 'original returned source changed')
        self.assertEqual(Evidence.objects.filter(case=self.case, kind='financial_input').count(), count)
        original = FinanceSource.objects.get(pk=self.sample['source']).batch.evidence.body.encode()
        self.assertContains(self.client.post(self.sample['correction'], self.form(decision, original)),
                            'Select a changed trial-balance extract')
        self.assertFalse(Audit.objects.filter(case=self.case, action=intake.RECEIPT).exists())
        reviewer_grant = Grant.objects.filter(case=self.case, user=self.reviewer, action='finance.review')
        reviewer_grant.update(active=False)
        self.assertEqual(self.client.get(self.sample['correction']).status_code, 403)
        reviewer_grant.update(active=True)
        wrong_period = self.form(decision, self.csv.replace(b'2026-10', b'2026-09'))
        self.assertEqual(self.client.post(self.sample['correction'], wrong_period).status_code, 302)
        receipt = Audit.objects.get(case=self.case, action=intake.RECEIPT)
        self.assertEqual(intake.latest(receipt)['status'], 'quarantined')
        self.assertIn('period', str(intake.latest(receipt)['findings']))
        self.assertEqual(FactoryWork.objects.filter(case=self.case).count(), 1)
        self.assertFalse(Audit.objects.filter(case=self.case, action=LINKED).exists())
