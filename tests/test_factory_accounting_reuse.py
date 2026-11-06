"""Reuse native report receipts without confusing historical delivery with current output."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError,transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.documents.controlled import create_version, reserve_publication
from apps.documents.delivery import run_publication_once
from apps.documents.models import Publication, PublicationReceipt
from apps.finance import analysis
from apps.finance.documents import draft_report
from apps.finance.models import FinanceDocumentBinding, FinanceRun
from apps.identity.models import Grant
from apps.policy.factory_recovery_validators import COMPONENT, METHOD
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory, factory_accounting as accounting, factory_execution
from tests.finance_analysis_helpers import fixture, pipeline, METRICS
from tests.factory_accounting_helpers import configured
from tests.helpers import rev


class AccountingReceiptReuseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        a, c, e, _, _, source, template, recipient = fixture(username='reuse-source-owner')
        _, _, output = pipeline(a, c, source)
        analysis.review(a, c.pk, 'output', output.pk, 'Finance', 'approve', e['finance_review'].pk,
                        'Synthetic native accounting output reviewed before factory intake', rev(c))
        version = draft_report(a, c.pk, output.pk, template.pk, 'internal', rev(c))
        publication = reserve_publication(a, c.pk, version.pk, rev(c))
        run_publication_once(case_id=c.pk, job_id=publication.job.pk)
        worker = get_user_model().objects.create_user(username='reuse-reviewed-worker')
        for action in ['case.read', 'factory.read', 'factory.execute', 'finance.read', 'finance.calculate',
                       'agent.finance', 'finance.publish', 'document.draft', 'document.publish', 'evidence.add']:
            Grant.objects.create(case=c, user=worker, action=action)
        f = configured(a, c, e, source, template, METRICS, executor_id=worker.pk)
        work = f['work']; now = timezone.now()
        rule = dict(definition=accounting.DEFINITION, method=METHOD, principal_id=worker.pk, reviewer_id=a.pk,
                    review_role='Finance', independent_of_worker=True, valid_from=now.isoformat(),
                    valid_until=(now + timedelta(hours=1)).isoformat())
        policy = draft_operator_policy(a, c.pk, COMPONENT, {'rules': [rule]}, e['policy_decision'].pk, now)
        transition(a, policy.pk, 'validated'); transition(a, policy.pk, 'active')
        factory_execution.bind(a, work.pk, work.revision, e['policy_decision'].pk, 'Reviewed worker; reuse original native output only')
        Grant.objects.filter(case=c, user=a, action='factory.execute').update(active=False)
        cls.actor, cls.case, cls.version, cls.publication, cls.work, cls.value = a, c, version, publication, work, f['value']

    def test_bound_worker_reuses_original_native_report_and_receipt_without_another_effect(self):
        before = (FinanceRun.objects.count(), FinanceDocumentBinding.objects.count(), Publication.objects.count(), PublicationReceipt.objects.count())
        receipt = PublicationReceipt.objects.get(publication=self.publication)
        factory.run_until_wait(self.work.pk); self.work.refresh_from_db()
        self.assertEqual(self.work.status, 'verified', self.work.finding)
        self.assertIsNone(Publication.objects.get(pk=self.publication.pk).factory_work_id)
        self.assertEqual(accounting.verified(self.work, self.value)['receipt_ids'], [receipt.pk])
        self.assertEqual(before, (FinanceRun.objects.count(), FinanceDocumentBinding.objects.count(), Publication.objects.count(), PublicationReceipt.objects.count()))
        self.client.force_login(self.actor)
        page = self.client.get(reverse('factory_detail', args=[self.work.pk]))
        self.assertEqual(page.context['row']['state'], 'Verified')
        self.assertContains(page, 'Confirmed for')

    def test_superseded_document_cannot_reuse_historical_receipts_as_current_output(self):
        factory.run_until_wait(self.work.pk); self.work.refresh_from_db()
        self.assertEqual(self.work.status,'verified',self.work.finding)
        state = accounting.snapshot(self.work, self.value, reader=self.actor)[0]
        receipt = PublicationReceipt.objects.get(publication=self.publication)
        create_version(self.actor, self.case.pk, self.version.template_id, self.version.document.title,
                       self.version.audience, self.version.fields, rev(self.case), document_id=self.version.document_id)
        self.assertIsNone(accounting.snapshot(self.work, self.value, reader=self.actor)[0]['document'])
        with self.assertRaises(ValidationError): accounting.verified(self.work, self.value, state)
        with self.assertRaises(DatabaseError),transaction.atomic():
            type(self.work).objects.filter(pk=self.work.pk).update(status='verified')
        self.client.force_login(self.actor)
        page=self.client.get(reverse('factory_detail',args=[self.work.pk]))
        self.assertEqual(page.context['row']['state'],'Published report needs review')
        self.assertTrue(page.context['row']['readiness_changed'])
        self.assertEqual(PublicationReceipt.objects.get(pk=receipt.pk).payload_sha256, receipt.payload_sha256)
        self.assertEqual(PublicationReceipt.objects.count(), 1)
