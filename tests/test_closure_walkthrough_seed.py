"""Three scoped principals complete the connected native closure sample."""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.identity.models import Grant
from apps.pmo.models import DeliveryDossier
from apps.workflows import factory, factory_closure
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import railway_closure_walkthrough_seed as seed
from tests.helpers import rev


class ClosureWalkthroughSeedTests(TestCase):
    def test_exact_document_returns_to_source_and_reaches_distinct_review_and_closure(self):
        self.assertEqual(connection.vendor, 'postgresql')
        users = get_user_model().objects
        reviewer = users.create_user('sample-closure-quality-walkthrough')
        head = users.create_user('sample-closure-head-walkthrough')
        sample = seed.prepare(reviewer, head)
        self.assertEqual(seed.prepare(reviewer, head), sample | {'preserved': True})
        work = FactoryWork.objects.get(pk=sample['work'])
        dossier = DeliveryDossier.objects.get(pk=sample['dossier'])
        first = factory_closure.document(work)
        self.assertEqual(first.pk, sample['report'])
        self.assertEqual(first.created_by_id, sample['author'])
        self.assertEqual(len({first.created_by_id, reviewer.pk, head.pk}), 3)
        self.assertFalse(first.reviews.exists())
        self.assertFalse(dossier.records.filter(kind__in=('closure_decision', 'closure')).exists())
        decisions = sample['decision_path']
        recovery = sample['recovery_path']

        def post(path, action, **fields):
            work.refresh_from_db()
            return self.client.post(path, {'action': action, 'revision': work.revision,
                                           'case_revision': rev(work.case), **fields})

        def quality(version):
            return post(decisions, 'review', version=version.pk, verdict='approve',
                        note='Quality reviewer checked the exact fictional closure report.')

        def head_decision(version, verdict, note):
            return post(decisions, 'decide', version=version.pk, verdict=verdict, note=note,
                        evidence=sample['decision_evidence'])

        self.client.force_login(head)
        self.assertNotContains(self.client.get(decisions), 'Approve exact closure report')
        self.assertContains(head_decision(first, 'approve', 'Head must wait for document quality review.'),
                            'approval of this exact outward projection is required')
        self.assertFalse(dossier.records.filter(kind='closure_decision').exists())

        self.client.force_login(reviewer)
        self.assertContains(self.client.get(decisions), 'Approve exact document')
        self.assertRedirects(quality(first), decisions, fetch_redirect_response=False)
        self.assertEqual(first.reviews.get().actor_id, reviewer.pk)
        self.assertEqual(head_decision(first, 'approve', 'Quality reviewer lacks this decision grant.').status_code, 403)

        self.client.force_login(head)
        return_note = 'Return the exact fictional report for the revised handover lesson.'
        self.assertContains(self.client.get(decisions), 'Return exact closure report')
        self.assertRedirects(head_decision(first, 'return', return_note), decisions, fetch_redirect_response=False)
        returned = dossier.records.get(kind='closure_decision')
        self.assertEqual((returned.actor_id, returned.data['version_id']), (head.pk, first.pk))
        returned_page = self.client.get(decisions)
        self.assertContains(returned_page, 'Closure returned')
        self.assertContains(returned_page, f'Recorded by {head.username}')
        self.assertNotContains(returned_page, 'Approve exact closure report')
        self.assertFalse(dossier.records.filter(kind='closure').exists())

        self.client.force_login(reviewer)
        self.assertContains(self.client.get(recovery), 'Record reviewed source changes')
        corrected = sample['inputs'] | {'report_evidence_id': sample['corrected_evidence']}
        self.assertRedirects(post(recovery, 'correct', reason='Select the exact corrected synthetic report evidence.',
                                  **corrected), recovery, fetch_redirect_response=False)
        self.assertRedirects(post(recovery, 'advance'), recovery, fetch_redirect_response=False)
        self.assertEqual(FactoryProgress.objects.get(work=work).requested_by_id, reviewer.pk)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        successor = factory_closure.document(work)
        self.assertNotEqual(successor.pk, first.pk)
        self.assertEqual(successor.created_by_id, sample['author'])
        self.assertFalse(successor.reviews.exists())
        self.assertEqual(dossier.records.get(kind='closure_decision').pk, returned.pk)
        self.assertRedirects(quality(successor), decisions, fetch_redirect_response=False)

        self.client.force_login(head)
        self.assertContains(self.client.get(decisions), 'Approve exact closure report')
        self.assertRedirects(head_decision(successor, 'approve', 'Approve the corrected exact fictional report.'),
                             decisions, fetch_redirect_response=False)
        self.assertFalse(dossier.records.filter(kind='closure').exists())
        self.assertFalse(Grant.objects.filter(user=head, case=work.case, action__in=('factory.manage', 'factory.execute')).exists())
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertEqual(work.status, 'verified', work.finding)
        closed = dossier.records.get(kind='closure')
        self.assertEqual((closed.actor_id, closed.data['version_id']), (sample['author'], successor.pk))
        self.assertFalse(closed.snapshot['debt_waived'])
        self.assertFalse(closed.snapshot['deployment_authorized'])
        self.assertContains(self.client.get(recovery), return_note)
        self.assertEqual(seed.prepare(reviewer, head), sample | {'preserved': True})
