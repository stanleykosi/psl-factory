"""Exercise the separate maker and reviewer on the guarded weekly specimen."""
import json
from contextlib import redirect_stdout
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.core.models import Audit, Case
from apps.documents.models import Publication, PublicationReceipt, Version
from apps.identity import staff
from apps.identity.models import StaffAdmission
from apps.workflows import factory_progress, factory_reporting as weekly
from apps.workflows.models import FactoryProgress, FactoryWork, HumanTask
from tests import railway_admitted_schedule_seed as admission_seed
from tests import railway_weekly_return_walkthrough_seed as seed
from tests.helpers import rev
from tests.test_staff_profiles import configured


@patch.dict('os.environ', {'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                           seed.GUARD: '1', 'PGDATABASE': 'synthetic-preview'})
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
@patch.object(factory_progress, 'WAIT_INTERVAL', timedelta(0))
class WeeklyReturnWalkthroughTests(TestCase):
    def test_independent_return_replaces_only_one_exact_citation_then_receives_the_approved_successor(self):
        self.assertEqual(connection.vendor, 'postgresql')
        intake = configured()
        origin = intake['scopes'][0]['case']
        invitation, token = staff.invite(
            intake['actor'], origin.pk, seed.ADMITTED_USERNAME, 'Sample weekly report maker',
            'sample-weekly-maker@example.invalid', ['case.read'], rev(origin), profile_key='sample-reader',
        )
        maker = staff.accept(token, 'Synthetic!weekly.return.982')
        reviewer = get_user_model().objects.create_user('psl-agent-trial')
        admission = StaffAdmission.objects.get(invitation=invitation, user=maker)
        scope_revision = rev(origin)
        scope_audits = list(Audit.objects.filter(case=origin).order_by('pk').values_list('pk', flat=True))
        with patch.multiple(seed, ADMITTED_IDENTITY=(invitation.pk, maker.pk), ADMITTED_STAFF_CASE=origin.pk):
            with patch.dict('os.environ', {seed.GUARD: '0'}):
                with self.assertRaisesMessage(RuntimeError, 'weekly return fixture guard'):
                    seed.run()
            self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())
            output = StringIO()
            with redirect_stdout(output):
                seed.run()
        prefix, result = output.getvalue().strip().split('=', 1)
        self.assertEqual(prefix, seed.GUARD)
        specimen = json.loads(result)
        self.assertEqual(seed.prepare(maker, reviewer, admission), specimen | {'preserved': True})

        work = FactoryWork.objects.select_related('case').get(pk=specimen['work'])
        case = work.case
        original = Version.objects.get(pk=specimen['first_report'])
        first_review = HumanTask.objects.get(pk=specimen['first_task'], version=original, status='open')
        self.assertFalse(original.reviews.exists())
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())
        self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
        self.assertEqual(original.created_by_id, maker.pk)
        self.assertEqual(weekly.document(work).pk, original.pk)
        self.assertEqual(len({ids['evidence_ids'][0] for ids in specimen['original_sections'].values()}), 4)

        def post(path, action, **fields):
            work.refresh_from_db()
            return self.client.post(path, {'action': action, 'revision': work.revision,
                                           'case_revision': rev(case), **fields})

        def decide(version, verdict, note):
            return post(specimen['decision_path'], 'review', version=version.pk, verdict=verdict, note=note)

        self.client.force_login(maker)
        self.assertNotContains(self.client.get(specimen['decision_path']), 'Approve exact report')
        self.assertEqual(decide(original, 'approve', 'A maker cannot review their own report.').status_code, 403)
        self.client.force_login(reviewer)
        self.assertContains(self.client.get(specimen['decision_path']), 'Return exact report')
        self.assertRedirects(decide(original, 'return', specimen['return_reason']), specimen['decision_path'],
                             fetch_redirect_response=False)
        returned = original.reviews.get()
        self.assertEqual((returned.actor_id, returned.verdict, returned.note),
                         (reviewer.pk, 'return', specimen['return_reason']))
        first_review.refresh_from_db()
        self.assertEqual(first_review.status, 'returned')
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())

        self.client.force_login(maker)
        edit = specimen['edit_path'].split('#', 1)[0]
        before = self.client.get(edit)
        self.assertContains(before, 'Returned for changes')
        self.assertContains(before, specimen['return_reason'])
        values = before.context['inputs_form'].initial
        self.assertEqual(values['template_id'], specimen['template'])
        for name, section in specimen['original_sections'].items():
            self.assertEqual(values[name], section['text'])
            self.assertEqual(values[f'{name}_citations'], section['evidence_ids'])
        fields = {'start_at': specimen['start'], 'end_at': specimen['end'], 'template_id': specimen['template'],
                  'reason': specimen['correction_reason']}
        sections = {**specimen['original_sections'], 'risks': specimen['revised_risks']}
        for name, section in sections.items():
            fields[name] = section['text']
            fields[f'{name}_citations'] = section['evidence_ids']
        self.assertRedirects(post(edit, 'correct', **fields), edit, fetch_redirect_response=False)
        self.assertRedirects(post(specimen['path'], 'advance'), specimen['path'], fetch_redirect_response=False)
        progress = FactoryProgress.objects.get(work=work, requested_by=maker)
        for _ in range(20):
            self.assertEqual(factory_progress.run_once(), progress.pk)
            work.refresh_from_db()
            successor = weekly.document(work)
            if successor and HumanTask.objects.filter(version=successor, status='open').exists():
                break
        else:
            self.fail(f'The exact successor did not reach its separate review: {work.finding}')
        self.assertNotEqual(successor.pk, original.pk)
        self.assertFalse(successor.reviews.exists())
        self.assertEqual(successor.created_by_id, maker.pk)
        data = weekly.source(work, maker)
        content = weekly.inventory(maker, case, data['inputs'])
        self.assertEqual(weekly.client_content(case, content, data['inputs']['content_id'])[1], sections)
        self.assertEqual((data['inputs']['start_at'], data['inputs']['end_at']), (specimen['start'], specimen['end']))
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())

        self.client.force_login(reviewer)
        page = self.client.get(specimen['decision_path'])
        self.assertContains(page, specimen['revised_risks']['text'])
        self.assertContains(page, 'Approve exact report')
        self.assertContains(decide(original, 'approve', 'Attempt a stale report approval.'),
                            'STALE_VERSION: select exact current weekly report')
        self.assertRedirects(decide(successor, 'approve', 'The later sample record supports this corrected version.'),
                             specimen['decision_path'], fetch_redirect_response=False)
        self.assertEqual(successor.reviews.get().actor_id, reviewer.pk)
        for _ in range(24):
            self.assertEqual(factory_progress.run_once(), progress.pk)
            work.refresh_from_db()
            if work.status == 'verified':
                break
        else:
            self.fail(f'The separate native inbox receipt was not verified: {work.finding}')
        receipt = PublicationReceipt.objects.get(publication__factory_work=work)
        self.assertEqual((receipt.recipient_id, receipt.publication.actor_id, receipt.publication.version_id),
                         (specimen['inbox'], specimen['publisher'], successor.pk))
        self.assertEqual(weekly.verify(work)['receipt_ids'], [receipt.pk])
        self.assertEqual(original.reviews.get().pk, returned.pk)
        self.assertFalse(Publication.objects.filter(version=original).exists())
        self.assertContains(self.client.get(specimen['recovery_path']), 'Delivery by recipient')
        self.assertContains(self.client.get(specimen['recovery_path']), 'Sample weekly inbox')
        self.assertEqual(rev(origin), scope_revision)
        self.assertEqual(list(Audit.objects.filter(case=origin).order_by('pk').values_list('pk', flat=True)), scope_audits)
        self.assertEqual(seed.prepare(maker, reviewer, admission), specimen | {'preserved': True})
