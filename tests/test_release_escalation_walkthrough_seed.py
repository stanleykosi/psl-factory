import json
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.core.models import Case
from apps.documents.models import Publication, PublicationReceipt
from apps.identity import staff
from apps.identity.models import StaffAdmission
from apps.pmo.delivery import valid_release
from apps.pmo.models import DeliveryDossier
from apps.workflows.factory_escalation import document
from apps.workflows.models import FactoryWork, HumanTask
from tests import railway_admitted_schedule_seed as admission_seed
from tests import railway_release_escalation_walkthrough_seed as seed
from tests.helpers import rev
from tests.test_staff_profiles import configured


class ReleaseEscalationWalkthroughSeedTests(TestCase):
    def test_native_release_and_distinct_human_escalation_submit_then_review(self):
        self.assertEqual(connection.vendor, 'postgresql')
        initial = configured()
        origin = initial['scopes'][0]['case']
        operator = get_user_model().objects.create_user('psl-agent-trial')
        invitation, token = staff.invite(initial['actor'], origin.pk, 'sample-escalation-admitted-reviewer',
            'Sample escalation reviewer', 'sample-escalation-reviewer@example.invalid', ['case.read'], rev(origin),
            profile_key='sample-reader')
        reviewer = staff.accept(token, 'Synthetic!escalation.review.278')
        admission = StaffAdmission.objects.get(invitation=invitation, user=reviewer)
        origin_revision = rev(origin)
        environment = {'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                       'PGDATABASE': 'synthetic-preview', seed.GUARD: '1'}

        def read_samples():
            output = StringIO()
            with patch.dict('os.environ', environment), redirect_stdout(output), \
                    patch.object(admission_seed, 'ADMISSION_TENANT', origin.tenant), \
                    patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader'), \
                    patch.multiple(seed, ADMITTED_IDENTITY=(invitation.pk, reviewer.pk),
                                   ADMITTED_STAFF_CASE=origin.pk, ADMITTED_USERNAME=reviewer.username):
                seed.run()
            label, value = output.getvalue().strip().split('=', 1)
            self.assertEqual(label, seed.GUARD)
            return json.loads(value)

        with patch.dict('os.environ', dict(environment, **{seed.GUARD: '0'})):
            with self.assertRaisesMessage(RuntimeError, 'release/escalation sample guard'):
                seed.run()
        self.assertFalse(Case.objects.filter(pk__in=seed.CASE_IDS.values()).exists())
        data = read_samples()
        release, escalation = data['release'], data['escalation']
        self.assertEqual((escalation['reviewer'], escalation['admission'], escalation['invitation']),
                         (reviewer.pk, admission.pk, invitation.pk))
        self.assertNotEqual(release['case'], escalation['case'])
        self.assertNotEqual(escalation['head'], reviewer.pk)

        def post(sample, action, **fields):
            work = FactoryWork.objects.select_related('case').get(pk=sample['work'])
            return self.client.post(sample['path'], {'action': action, 'revision': work.revision,
                'case_revision': rev(work.case), **fields})

        self.client.force_login(operator)
        dossier = DeliveryDossier.objects.get(pk=release['dossier'], case_id=release['case'], candidate_id=release['candidate'])
        self.assertFalse(dossier.records.filter(kind='release_outcome').exists())
        self.assertContains(self.client.get(release['path']), 'Release environment (if known)')
        self.assertRedirects(post(release, 'hypercare_observation', kind='release', readiness=release['readiness'],
            released_at=release['released_at'], deployment_environment=release['environment'], reference=release['reference'],
            evidence=release['evidence'], note=release['note']), release['path'], fetch_redirect_response=False)
        outcome = valid_release(dossier)
        self.assertEqual((outcome.actor_id, outcome.data['deployment_environment'], outcome.evidence_id),
                         (operator.pk, release['environment'], release['evidence']))
        self.assertFalse(outcome.snapshot['deployment_dispatched'])
        self.assertContains(self.client.get(release['path']), release['environment'])

        work = FactoryWork.objects.get(pk=escalation['work'], case_id=escalation['case'])
        version = document(work)
        self.assertEqual((version.pk, version.created_by_id), (escalation['version'], operator.pk))
        self.assertFalse(HumanTask.objects.filter(version=version).exists())
        self.assertContains(self.client.get(escalation['path']), 'Message drafted')
        self.assertRedirects(post(escalation, 'request_review', version=version.pk), escalation['path'], fetch_redirect_response=False)
        task = HumanTask.objects.get(version=version)
        self.assertEqual((task.status, task.created_by_id), ('open', operator.pk))
        self.assertNotContains(self.client.get(escalation['path']), 'Approve exact communication')
        self.assertEqual(post(escalation, 'review', version=version.pk, verdict='approve', note='Synthetic review').status_code, 403)

        self.client.force_login(reviewer)
        self.assertContains(self.client.get(escalation['path']), 'Approve exact communication')
        self.assertRedirects(post(escalation, 'review', version=version.pk, verdict='approve', note='Reviewed exact sample draft.'),
                             escalation['path'], fetch_redirect_response=False)
        self.assertEqual(version.reviews.get().actor_id, reviewer.pk)
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())
        self.assertFalse(PublicationReceipt.objects.filter(publication__version=version).exists())

        self.assertEqual(read_samples(), {name: sample | {'preserved': True} for name, sample in data.items()})
        self.assertEqual(rev(origin), origin_revision)
        self.assertEqual(HumanTask.objects.get(version=version).pk, task.pk)
        self.assertEqual(valid_release(dossier).pk, outcome.pk)
