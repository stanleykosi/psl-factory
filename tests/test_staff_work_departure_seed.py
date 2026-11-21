from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse

from apps.core.models import Audit, Case
from apps.documents.models import ControlledReview, Publication
from apps.finance.models import InvoiceJob
from apps.identity.models import Grant, StaffAccountChange
from apps.workflows import factory_execution
from apps.workflows.models import FactoryAttempt, FactoryWork
from tests import railway_staff_work_departure_seed as seed


class StaffWorkDepartureFixtureTests(TestCase):
    def test_started_work_recovery_then_departure_preserves_original_review_and_exact_worker(self):
        self.assertEqual(connection.vendor, 'postgresql')
        trial = get_user_model().objects.create_user(seed.TRIAL)
        data = seed.prepare()
        self.assertEqual(seed.prepare(), {**data, 'preserved': True})
        case = Case.objects.get(pk=data['case'])
        target = get_user_model().objects.get(pk=data['person'])
        active_session = Client()
        active_session.force_login(target)
        self.assertEqual(active_session.get(data['work_path']).status_code, 200)
        work = FactoryWork.objects.get(pk=data['work'])
        original_attempt = FactoryAttempt.objects.get(pk=data['original_attempt'])
        original_review = ControlledReview.objects.values().get(pk=data['older_review'])
        self.assertEqual(original_review['actor_id'], target.pk)
        self.assertGreater(data['spent'], 0)
        self.client.force_login(trial)
        held = self.client.get(data['departure'])
        self.assertContains(held, 'Complete the native handoff')
        self.assertContains(held, data['worker_review'])
        self.assertContains(held, seed.WORK_REFERENCE)
        self.assertNotContains(held, '<button>Deactivate account</button>', html=True)
        stale = {key: str(held.context['form'].initial[key]) for key in ('operation', 'fingerprint')}
        stale.update(confirmed='on', reason='SAMPLE author reviewed whole account departure.')
        self.assertFalse(StaffAccountChange.objects.filter(user=target).exists())

        proposed = self.client.get(data['worker_review'])
        self.assertContains(proposed, 'Review worker replacement')
        self.assertContains(proposed, 'SAMPLE Original Worker')
        self.assertContains(proposed, 'SAMPLE Continuing Worker')
        self.assertRedirects(self.client.post(data['worker_review'], {
            'revision': work.revision, 'evidence': data['proof'], 'reason': 'SAMPLE named Finance successor reviewed.',
        }), data['work_path'])
        work.refresh_from_db()
        binding = work.execution_binding
        self.assertEqual(binding.principal_id, data['successor'])
        self.assertEqual(binding.reviewer_id, trial.pk)
        self.assertEqual((work.actor_id, work.budget_used), (target.pk, data['spent']))
        self.assertEqual(factory_execution.available_actor(work).pk, data['successor'])
        self.assertContains(self.client.post(data['departure'], stale), 'Staff access or open work changed.')
        target.refresh_from_db()
        self.assertTrue(target.is_active)
        self.assertFalse(StaffAccountChange.objects.filter(user=target).exists())

        ready = self.client.get(data['departure'])
        self.assertContains(ready, '<button>Deactivate account</button>', html=True)
        values = {key: str(ready.context['form'].initial[key]) for key in ('operation', 'fingerprint')}
        self.assertNotEqual(values['fingerprint'], stale['fingerprint'])
        self.assertRedirects(self.client.post(data['departure'], {**values, 'confirmed': 'on', 'reason': stale['reason']}),
                             reverse('staff_roster'))
        target.refresh_from_db()
        self.assertFalse(target.is_active)
        self.assertFalse(Grant.objects.filter(user=target, active=True).exists())
        self.assertEqual(active_session.get(data['work_path']).status_code, 302)
        self.assertTrue(Audit.objects.filter(case=case, actor=trial, action='factory.execution_authority_recovered',
                                            data__binding=binding.pk).exists())
        older = self.client.get(data['earlier_review'])
        self.assertContains(older, 'SAMPLE prior decision retained under the original worker.')
        self.assertEqual(ControlledReview.objects.values().get(pk=data['older_review']), original_review)

        continued = seed.follow_up()
        self.assertEqual(continued['worker'], data['successor'])
        self.assertEqual(continued['binding'], binding.pk)
        work.refresh_from_db()
        self.assertEqual((work.actor_id, work.preparation.handoff_id), (target.pk, data['handoff']))
        self.assertEqual((work.invoice_id, work.invoice.actor_id), (continued['draft'], data['successor']))
        self.assertEqual(work.invoice.payload['amount'], '42.00')
        self.assertGreater(work.budget_used, data['spent'])
        self.assertEqual(FactoryAttempt.objects.get(pk=original_attempt.pk).result, original_attempt.result)
        self.assertFalse(InvoiceJob.objects.filter(invoice__case=case).exists())
        self.assertFalse(Publication.objects.filter(version__document__case=case).exists())
