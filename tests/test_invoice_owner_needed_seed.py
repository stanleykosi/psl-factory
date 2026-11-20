"""An independent named resolver opens the next native Finance decision without approving it."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.core.models import Case
from apps.finance.models import InvoiceIssue, InvoiceJob, InvoiceReview
from apps.identity import staff
from apps.identity.models import Grant
from apps.policy.models import Configuration
from apps.policy.services import active_component
from apps.workflows import factory
from apps.workflows.models import FactoryWork, HumanTask, TaskEvent
from tests import railway_admitted_schedule_seed as admissions
from tests import railway_invoice_owner_needed_seed as seed
from tests.helpers import rev
from tests.test_staff_profiles import configured


@patch.object(admissions, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admissions, 'ADMISSION_PROFILE', 'sample-reader')
class InvoiceOwnerNeededSeedTests(TestCase):
    def test_governed_nomination_and_recheck_keep_invoice_decision_separate(self):
        self.assertEqual(connection.vendor, 'postgresql')
        existing = configured()
        origin = existing['scopes'][0]['case']
        resolver = get_user_model().objects.create_user(seed.TRIAL)
        invitation, token = staff.invite(existing['actor'], origin.pk, 'sample-invited-owner-needed-reader',
            'Sample project reader', 'sample-owner-needed-reader@example.invalid', ['case.read'],
            rev(origin), profile_key='sample-reader')
        reader = staff.accept(token, 'Synthetic!invoice.owner.629')
        previous = set(Grant.objects.filter(user=reader).values_list('case_id', 'action', 'active'))
        with self.assertRaisesMessage(RuntimeError, 'No exact matching accepted synthetic invitation'):
            seed.prepare(invitation.pk + 1_000, reader.pk)
        self.assertFalse(Case.objects.filter(pk=seed.CASE_ID).exists())
        sample = seed.prepare(invitation.pk, reader.pk)
        self.assertEqual(seed.prepare(invitation.pk, reader.pk), dict(sample, preserved=True))
        case = Case.objects.get(pk=sample['case'])
        work = FactoryWork.objects.get(pk=sample['work'], case=case)
        task = HumanTask.objects.get(pk=sample['task'], case=case)
        self.assertEqual((work.status, work.actor_id, task.claimed_by_id), ('owner_needed', sample['worker'], None))
        self.assertFalse(work.actor.has_usable_password())
        self.assertEqual(set(Grant.objects.filter(user=reader).exclude(case=case)
                             .values_list('case_id', 'action', 'active')), previous)
        decision = sample['decision_path']
        setup = sample['responsibility_path']
        claim = {'action': 'claim', 'task': task.pk, 'task_revision': task.revision}

        self.client.force_login(reader)
        page = self.client.get(decision)
        self.assertContains(page, 'Owner needed')
        self.assertContains(page, 'NGN 42.00')
        self.assertNotContains(page, 'Review invoice responsibilities')
        self.assertNotContains(page, 'Approve exact packet')
        self.assertEqual(self.client.get(setup).status_code, 403)
        self.client.force_login(resolver)
        self.assertNotContains(self.client.get(decision), 'Claim responsibility review')
        self.assertEqual(self.client.post(decision, claim).status_code, 403)
        self.assertContains(self.client.get(setup), 'Responsibility resolver')
        response = self.client.post(setup, {'action': 'draft', 'work': work.pk, **sample['nomination_fields']})
        self.assertEqual(response.status_code, 302)
        current = Configuration.objects.filter(case=case, component=seed.COMPONENT).latest('pk')
        self.assertNotEqual(current.pk, sample['initial_configuration'])
        for state in ('validated', 'active'):
            response = self.client.post(setup, {'action': 'transition', 'work': work.pk,
                                               'configuration': current.pk, 'state': state})
            self.assertEqual(response.status_code, 302)
        self.assertEqual(active_component(seed.COMPONENT, case).pk, current.pk)
        self.assertContains(self.client.get(decision), 'Claim responsibility review')
        self.assertRedirects(self.client.post(decision, claim), decision, fetch_redirect_response=False)
        task.refresh_from_db()
        recheck = {'action': 'responsibility_recheck', 'task': task.pk, 'task_revision': task.revision,
                   'reason': sample['recheck_reason']}
        review_grant = Grant.objects.filter(case=case, user=resolver, action='finance.invoice.review')
        review_grant.update(active=False)
        self.assertContains(self.client.post(decision, recheck), 'native Finance review eligibility')
        task.refresh_from_db()
        self.assertEqual(task.status, 'open')
        review_grant.update(active=True)
        self.assertRedirects(self.client.post(decision, recheck), decision, fetch_redirect_response=False)
        event = TaskEvent.objects.get(task=task, actor=resolver, action='factory.owners_rechecked')
        self.assertFalse(event.data['approval_granted'])
        work.refresh_from_db()
        self.assertEqual((work.status, work.invoice_id, work.invoice.sha256),
                         ('ready', sample['invoice'], sample['invoice_sha256']))
        self.assertEqual(seed.prepare(invitation.pk, reader.pk)['task_status'], 'completed')
        factory.run_until_wait(work.pk)
        fresh = HumanTask.objects.get(case=case, context__work=work.pk, kind='factory_review', status='open')
        self.assertEqual(fresh.context['packet']['invoice'], sample['invoice'])
        self.assertIsNone(fresh.claimed_by_id)
        self.assertFalse(InvoiceReview.objects.filter(invoice__case=case).exists())
        self.assertFalse(InvoiceJob.objects.filter(invoice__case=case).exists())
        self.assertFalse(InvoiceIssue.objects.filter(invoice__case=case).exists())
