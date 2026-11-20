import json
from contextlib import redirect_stdout
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.core.models import Audit, Case
from apps.documents.models import Publication, PublicationJob, PublicationReceipt
from apps.finance.models import Handoff
from apps.identity import staff
from apps.identity.models import Grant, StaffAdmission
from apps.pmo import delivery
from apps.pmo.models import DeliveryDocumentBinding
from apps.workflows import factory_closure, factory_progress
from apps.workflows.models import FactoryProgress, FactoryWork, HumanTask, Outbox
from tests import railway_admitted_schedule_seed as admission_seed, railway_returned_closure_seed as seed
from tests.helpers import rev
from tests.test_staff_profiles import configured


@patch.dict('os.environ', {'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance', 'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT,
                           'PGDATABASE': 'synthetic-preview', seed.GUARD: '1'})
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
@patch.object(factory_progress, 'WAIT_INTERVAL', timedelta(0))
class ReturnedClosureWalkthroughTests(TestCase):
    def test_head_return_then_admitted_correction_quality_review_and_independent_finalisation(self):
        self.assertEqual(connection.vendor, 'postgresql')
        existing = configured()
        origin = existing['scopes'][0]['case']
        invitation, token = staff.invite(existing['actor'], origin.pk, seed.ADMITTED_USERNAME,
            'Sample Quality reviewer', 'sample-return-quality@example.invalid', ['case.read'], rev(origin),
            profile_key='sample-reader')
        quality = staff.accept(token, 'Synthetic!closure-return.sample.816')
        head = get_user_model().objects.create_user('psl-agent-trial')
        origin_revision = rev(origin)
        origin_audits = list(Audit.objects.filter(case=origin).order_by('pk').values_list('pk', flat=True))

        def launch():
            output = StringIO()
            with redirect_stdout(output):
                seed.run()
            prefix, payload = output.getvalue().strip().split('=', 1)
            self.assertEqual(prefix, seed.GUARD)
            return json.loads(payload)

        with patch.multiple(seed, ADMITTED_IDENTITY=(invitation.pk, quality.pk), ADMITTED_STAFF_CASE=origin.pk):
            with patch.dict('os.environ', {seed.GUARD: ''}):
                with self.assertRaisesMessage(RuntimeError, 'returned closure fixture guard'):
                    seed.run()
            self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())
            sample = launch()
            self.assertEqual(launch(), sample | {'preserved': True})

        work = FactoryWork.objects.select_related('case').get(pk=sample['work'])
        dossier = delivery.dossier_for(work.case, sample['dossier'])
        first = factory_closure.document(work)
        self.assertEqual((first.pk, first.audience, first.created_by_id), (sample['report'], 'internal', sample['author']))
        self.assertEqual(first.reviews.get(pk=sample['setup_quality_review']).actor_id, quality.pk)
        self.assertEqual(HumanTask.objects.get(version=first).status, 'completed')
        self.assertFalse(dossier.records.filter(kind__in=('closure_decision', 'closure')).exists())
        self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
        original_head = work.source_head_id
        spent = work.budget_used
        decisions, recovery = sample['decision_path'], sample['recovery_path']

        def outbound_effects():
            return (
                set(PublicationReceipt.objects.filter(publication__version__document__case=work.case)
                    .values_list('pk', 'recipient_id')),
                set(Publication.objects.filter(version__document__case=work.case).values_list('pk', flat=True)),
                set(PublicationJob.objects.filter(publication__version__document__case=work.case)
                    .values_list('pk', 'status')),
                set(Outbox.objects.filter(case=work.case).values_list('pk', 'receipt')),
                set(Handoff.objects.filter(case=work.case).values_list('pk', 'operation_key')),
            )

        original_effects = outbound_effects()
        self.assertEqual({recipient for _, recipient in original_effects[0]}, {sample['author']})

        def post(path, action, **fields):
            work.refresh_from_db()
            return self.client.post(path, {'action': action, 'revision': work.revision,
                                           'case_revision': rev(work.case), **fields})

        def head_decision(report, verdict, note):
            return post(decisions, 'decide', version=report.pk, verdict=verdict,
                        evidence=sample['decision_evidence'], note=note)

        self.client.force_login(head)
        self.assertContains(self.client.get(decisions), 'Return exact closure report')
        self.assertNotContains(self.client.get(recovery), 'Record reviewed source changes')
        self.assertRedirects(head_decision(first, 'return', sample['return_reason']), decisions,
                             fetch_redirect_response=False)
        returned = dossier.records.get(kind='closure_decision')
        self.assertEqual((returned.actor_id, returned.data['version_id'], returned.data['verdict']),
                         (head.pk, first.pk, 'return'))
        self.assertContains(self.client.get(decisions), sample['return_reason'])
        self.assertNotContains(self.client.get(decisions), 'Approve exact closure report')
        self.assertContains(head_decision(first, 'approve', 'Attempted stale approval.'),
                            'Record corrected source and review the new closure report')
        self.assertEqual(dossier.records.get(kind='closure_decision').pk, returned.pk)

        self.client.force_login(quality)
        self.assertContains(self.client.get(recovery), 'Record reviewed source changes')
        revised = sample['inputs'] | {'report_evidence_id': sample['corrected_evidence']}
        self.assertRedirects(post(recovery, 'correct', reason='Carry the written sign-off into the exact report.', **revised),
                             recovery, fetch_redirect_response=False)
        work.refresh_from_db()
        self.assertNotEqual(work.source_head_id, original_head)
        self.assertEqual(work.budget_used, spent)
        self.assertRedirects(post(recovery, 'advance'), recovery, fetch_redirect_response=False)
        background = FactoryProgress.objects.get(work=work, requested_by=quality)
        for _ in range(20):
            self.assertEqual(factory_progress.run_once(), background.pk)
            work.refresh_from_db()
            successor = factory_closure.document(work)
            if successor and HumanTask.objects.filter(version=successor, status='open').exists():
                break
        else:
            self.fail(f'The admitted background request never reached fresh Quality review: {work.finding}')
        self.assertNotEqual(successor.pk, first.pk)
        self.assertEqual((successor.created_by_id, successor.audience), (sample['author'], 'internal'))
        binding = DeliveryDocumentBinding.objects.get(dossier=dossier, version=successor, purpose='closure')
        self.assertEqual(binding.data, {key: revised[key] for key in ('report_evidence_id', 'retrospective_id')})
        self.assertEqual(binding.snapshot['hypercare_id'], sample['stability_record'])
        self.assertIn(f'evidence {sample["signed_summary_evidence"]}', successor.fields['scope']['text'])
        self.assertFalse(successor.reviews.exists())
        self.assertFalse(dossier.records.filter(kind='closure').exists())
        self.assertContains(self.client.get(decisions), 'Approve exact document')
        self.assertNotContains(self.client.get(decisions), 'Approve exact closure report')
        self.assertRedirects(post(decisions, 'review', version=successor.pk, verdict='approve',
                                  note='Checked the preserved sign-off and exact successor report.'),
                             decisions, fetch_redirect_response=False)
        self.assertEqual(successor.reviews.get().actor_id, quality.pk)

        self.client.force_login(head)
        self.assertContains(self.client.get(decisions), 'Approve exact closure report')
        self.assertRedirects(head_decision(successor, 'approve', 'The exact revised report now includes the written sign-off.'),
                             decisions, fetch_redirect_response=False)
        self.assertFalse(dossier.records.filter(kind='closure').exists())
        self.assertFalse(Grant.objects.filter(case=work.case, user=head,
                                              action__in=('factory.execute', 'factory.manage')).exists())
        for _ in range(20):
            self.assertEqual(factory_progress.run_once(), background.pk)
            work.refresh_from_db()
            if work.status == 'verified':
                break
        else:
            self.fail(f'The existing background request did not verify closure: {work.finding}')
        closed = dossier.records.get(kind='closure')
        self.assertEqual((closed.actor_id, closed.data['version_id']), (sample['author'], successor.pk))
        self.assertFalse(closed.snapshot['debt_waived'])
        self.assertFalse(closed.snapshot['deployment_authorized'])
        self.assertEqual(outbound_effects(), original_effects)
        self.assertContains(self.client.get(recovery), sample['return_reason'])
        admission = StaffAdmission.objects.get(invitation=invitation, user=quality)
        self.assertEqual(seed.prepare(quality, head, admission), sample | {'preserved': True})
        self.assertEqual(rev(origin), origin_revision)
        self.assertEqual(list(Audit.objects.filter(case=origin).order_by('pk').values_list('pk', flat=True)), origin_audits)
