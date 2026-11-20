"""Show the guarded browser sample stops before its upload and Finance decision."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.agents.models import CaseUpload
from apps.core.models import Case
from apps.finance.models import Invoice, InvoiceJob
from apps.identity import staff
from apps.identity.models import Grant
from apps.workflows.models import FactoryProgress, FactoryWork, HumanTask, InvoiceMilestoneProof
from tests import railway_admitted_schedule_seed as admissions
from tests import railway_invoice_milestone_proof_seed as seed
from tests.helpers import rev
from tests.test_staff_profiles import configured


@patch.object(admissions, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admissions, 'ADMISSION_PROFILE', 'sample-reader')
class InvoiceMilestoneProofSeedTests(TestCase):
    def test_stops_at_exact_unsupplied_request_and_preserves_the_two_admitted_roles(self):
        self.assertEqual(connection.vendor, 'postgresql')
        existing = configured()
        origin = existing['scopes'][0]['case']
        reviewer = get_user_model().objects.create_user(seed.TRIAL)
        invitation, token = staff.invite(existing['actor'], origin.pk, 'sample-invited-proof-owner',
            'Sample invoice proof owner', 'sample-proof-owner@example.invalid', ['case.read'],
            rev(origin), profile_key='sample-reader')
        supplier = staff.accept(token, 'Synthetic!invoice.proof.629')
        original_scopes = set(Grant.objects.filter(user=supplier).values_list('case_id', 'action', 'active'))
        with self.assertRaisesMessage(RuntimeError, 'No exact matching accepted synthetic invitation'):
            seed.prepare(invitation.pk + 1_000, supplier.pk)
        with self.assertRaisesMessage(RuntimeError, 'Use the original accepted synthetic evidence supplier'):
            seed.prepare(invitation.pk, supplier.pk, hosted=True)
        self.assertFalse(Case.objects.filter(pk=seed.CASE_ID).exists())

        sample = seed.prepare(invitation.pk, supplier.pk)
        sample_case = Case.objects.get(pk=sample['case'])
        work = FactoryWork.objects.get(pk=sample['work'])
        task = HumanTask.objects.get(pk=sample['task'])
        current = FactoryProgress.objects.get(pk=sample['progress'], work=work)
        self.assertEqual((work.actor_id, task.context['resolver'], sample['reviewer']),
                         (sample['worker'], supplier.pk, reviewer.pk))
        self.assertFalse(work.actor.has_usable_password())
        self.assertEqual((task.status, task.claimed_by_id, current.requested_by_id, current.status),
                         ('open', None, work.actor_id, 'queued'))
        self.assertEqual(set(Grant.objects.filter(user=supplier).exclude(case=sample_case)
                             .values_list('case_id', 'action', 'active')), original_scopes)
        self.assertFalse(CaseUpload.objects.filter(case=sample_case).exists())
        self.assertFalse(InvoiceMilestoneProof.objects.filter(work=work).exists())
        self.assertFalse(Invoice.objects.filter(case=sample_case).exists())
        self.assertFalse(InvoiceJob.objects.filter(invoice__case=sample_case).exists())
        replay = seed.prepare(invitation.pk, supplier.pk)
        self.assertEqual(replay, dict(sample, preserved=True))

        command = {'action': 'claim', 'task': task.pk, 'task_revision': task.revision}
        self.client.force_login(reviewer)
        self.assertEqual(self.client.post(sample['decision_path'], command).status_code, 403)
        self.assertNotContains(self.client.get(sample['decision_path']), 'Upload a private PDF')
        self.client.force_login(supplier)
        self.assertRedirects(self.client.post(sample['decision_path'], command), sample['decision_path'],
                             fetch_redirect_response=False)
        self.assertContains(self.client.get(sample['decision_path']), 'Upload a private PDF')
        self.assertContains(self.client.get(sample['decision_path']), sample['file_path'])
        self.assertNotContains(self.client.get(sample['decision_path']), 'Approve exact packet')
        replay = seed.prepare(invitation.pk, supplier.pk)
        self.assertEqual(replay, dict(sample, preserved=True, claimed_by=supplier.pk))
        self.assertFalse(InvoiceMilestoneProof.objects.filter(work=work).exists())
