"""Exercise the distinct accepted-account closure fixture through its native decision routes."""

import json
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.core.models import Audit, Case
from apps.documents.models import Publication
from apps.identity import staff
from apps.identity.models import Grant, StaffAdmission
from apps.pmo.models import DeliveryDossier, DeliveryDocumentBinding
from apps.workflows import factory_closure
from apps.workflows.models import FactoryProgress, FactoryWork, HumanTask
from tests import railway_admitted_schedule_seed as admission_seed, railway_closure_walkthrough_seed as seed
from tests.helpers import rev
from tests.test_staff_profiles import configured


@patch.dict('os.environ', {'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance', 'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT,
                           'PGDATABASE': 'synthetic-preview', seed.ADMITTED_GUARD: '1'})
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class AdmittedClosureWalkthroughTests(TestCase):
    def test_exact_admission_starts_separate_held_closure_and_preserves_legacy_sample(self):
        self.assertEqual(connection.vendor, 'postgresql')
        data = configured()
        origin = data['scopes'][0]['case']
        head = get_user_model().objects.create_user('psl-agent-trial')

        def invite(username):
            invitation, token = staff.invite(data['actor'], origin.pk, username, 'Sample Quality reviewer',
                                             f'{username}@example.invalid', ['case.read'], rev(origin),
                                             profile_key='sample-reader')
            return invitation, staff.accept(token, 'Synthetic!closure.sample.816')

        def launch():
            output = StringIO()
            with redirect_stdout(output):
                seed.run_admitted()
            prefix, payload = output.getvalue().strip().split('=', 1)
            self.assertEqual(prefix, seed.ADMITTED_GUARD)
            return json.loads(payload)

        _, old_quality = invite('synthetic-legacy-closure-reviewer')
        legacy = seed.prepare(old_quality, head)
        old_work = FactoryWork.objects.get(pk=legacy['work'])
        legacy_revision = rev(old_work.case)
        legacy_audits = list(Audit.objects.filter(case=old_work.case).order_by('pk').values_list('pk', flat=True))

        invitation, quality = invite(seed.ADMITTED_USERNAME)
        original_password = quality.password
        original_grants = set(Grant.objects.filter(user=quality).values_list('case_id', 'action', 'active'))
        with patch.multiple(seed, ADMITTED_IDENTITY=(invitation.pk, quality.pk), ADMITTED_STAFF_CASE=origin.pk):
            with patch.dict('os.environ', {seed.ADMITTED_GUARD: '', 'PSL_CLOSURE_WALKTHROUGH_FIXTURE': '1'}):
                with self.assertRaisesMessage(RuntimeError, 'admitted closure fixture guard'):
                    seed.run_admitted()
            current_access = Grant.objects.filter(case=origin, user=quality, action='case.read')
            current_access.update(active=False)
            with self.assertRaisesMessage(RuntimeError, 'retain current access'):
                seed.run_admitted()
            current_access.update(active=True)
            self.assertEqual(Case.objects.filter(tenant=seed.TENANT).count(), 1)
            sample = launch()
            self.assertEqual(launch(), sample | {'preserved': True})

        self.assertNotEqual(sample['case'], legacy['case'])
        self.assertEqual(seed.prepare(old_quality, head), legacy | {'preserved': True})
        self.assertEqual(rev(old_work.case), legacy_revision)
        self.assertEqual(list(Audit.objects.filter(case=old_work.case).order_by('pk').values_list('pk', flat=True)),
                         legacy_audits)
        case = Case.objects.get(pk=sample['case'], synthetic=True)
        self.assertEqual(sample['invitation'], invitation.pk)
        self.assertEqual(sample['admission'], StaffAdmission.objects.get(invitation=invitation, user=quality).pk)
        quality.refresh_from_db()
        self.assertEqual(quality.password, original_password)
        self.assertEqual(set(Grant.objects.filter(user=quality).exclude(case=case).values_list('case_id', 'action', 'active')),
                         original_grants)
        self.assertEqual(set(Grant.objects.filter(user=quality, case=case, active=True).values_list('action', flat=True)),
                         set(seed.QUALITY_ACTIONS))
        self.assertEqual(set(Grant.objects.filter(user=head, case=case, active=True).values_list('action', flat=True)),
                         set(seed.HEAD_ACTIONS))

        work = FactoryWork.objects.get(pk=sample['work'], case=case)
        version = factory_closure.document(work)
        dossier = DeliveryDossier.objects.get(case=case, pk=sample['dossier'])
        self.assertEqual((work.status, version.pk, version.audience), ('waiting', sample['report'], 'internal'))
        self.assertEqual(len({version.created_by_id, quality.pk, head.pk}), 3)
        binding = DeliveryDocumentBinding.objects.get(dossier=dossier, version=version, purpose='closure')
        self.assertEqual(binding.data['report_evidence_id'], sample['inputs']['report_evidence_id'])
        self.assertTrue(version.template.definition['internal_review_required'])
        self.assertTrue(HumanTask.objects.filter(case=case, version=version, status='open', required_role='PMO Lead').exists())
        self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
        self.assertFalse(version.reviews.exists())
        self.assertFalse(dossier.records.filter(kind__in=('closure_decision', 'closure')).exists())
        path = sample['decision_path']

        def post(action, verdict, evidence=None):
            work.refresh_from_db()
            values = {'action': action, 'revision': work.revision, 'case_revision': rev(case), 'version': version.pk,
                      'verdict': verdict, 'note': 'Checked the exact fictional closure report.'}
            if evidence is not None:
                values['evidence'] = evidence
            return self.client.post(path, values)

        self.client.force_login(head)
        self.assertNotContains(self.client.get(path), 'Approve exact closure report')
        self.assertContains(post('decide', 'return', sample['decision_evidence']),
                            'approval of this exact outward projection is required')
        self.client.force_login(quality)
        self.assertContains(self.client.get(path), 'Approve exact document')
        self.assertRedirects(post('review', 'approve'), path, fetch_redirect_response=False)
        self.assertEqual(version.reviews.get().actor_id, quality.pk)
        self.assertEqual(post('decide', 'return', sample['decision_evidence']).status_code, 403)
        self.client.force_login(head)
        self.assertContains(self.client.get(path), 'Return exact closure report')
        self.assertRedirects(post('decide', 'return', sample['decision_evidence']), path, fetch_redirect_response=False)
        returned = dossier.records.get(kind='closure_decision')
        self.assertEqual((returned.actor_id, returned.data['version_id']), (head.pk, version.pk))
        self.assertFalse(dossier.records.filter(kind='closure').exists())
        self.assertFalse(Publication.objects.filter(version=version).exists())
