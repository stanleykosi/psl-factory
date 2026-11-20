"""Exercise the isolated fixture through the existing case and work commands."""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.identity.models import Grant
from apps.pmo.models import DeliveryDossier, DeliverySource
from apps.policy.services import resolve
from apps.workflows import factory_hypercare, factory_progress
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import railway_hypercare_walkthrough_seed as seed
from tests.helpers import rev


class HypercareWalkthroughSeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operator = get_user_model().objects.create_user('hypercare-walkthrough-operator')
        cls.sample = seed.prepare(cls.operator)

    def test_primary_continue_sample_is_a_separate_unprocessed_workspace(self):
        self.assertEqual(connection.vendor, 'postgresql')
        original = self.sample
        primary = seed.prepare(self.operator, scenario=seed.PRIMARY_CONTINUE)
        self.assertEqual(primary['case'], str(seed.PRIMARY_CASE_ID))
        for identity in ('work', 'case', 'dossier', 'candidate', 'release', 'acceptance', 'receipt', 'criteria_draft',
                         'criteria_proof', 'infrastructure_source', 'infrastructure_recorder'):
            self.assertNotEqual(primary[identity], original[identity], identity)
        self.assertFalse(primary['existing_work_preserved'])
        self.assertEqual(seed.prepare(self.operator), original | {'existing_work_preserved': True})
        self.assertEqual(seed.prepare(self.operator, scenario=seed.PRIMARY_CONTINUE),
                         primary | {'existing_work_preserved': True})
        work = FactoryWork.objects.get(pk=primary['work'], actor=self.operator)
        dossier = DeliveryDossier.objects.get(pk=primary['dossier'], case=work.case)
        self.assertEqual(work.status, 'configuration_needed')
        self.assertNotEqual(resolve(seed.COMPONENT, work.case).status, 'ACTIVE')
        self.assertFalse(dossier.sources.filter(kind='hypercare_engineering').exists())
        self.assertFalse(dossier.records.filter(kind='hypercare').exists())
        self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
        self.client.force_login(self.operator)
        page = self.client.get(primary['path'])
        self.assertContains(page, 'Stability rules need review')
        self.assertNotContains(page, 'Continue eligible work')

    def test_setup_hold_and_exact_failed_then_qualifying_observations(self):
        self.assertEqual(connection.vendor, 'postgresql')
        users = get_user_model().objects
        operator, sample = self.operator, self.sample
        work = FactoryWork.objects.get(pk=sample['work'])
        dossier = DeliveryDossier.objects.get(pk=sample['dossier'])
        path = sample['path']
        self.assertEqual(work.status, 'configuration_needed')
        self.assertNotEqual(resolve(seed.COMPONENT, work.case).status, 'ACTIVE')
        self.assertFalse(dossier.records.filter(kind='hypercare').exists())
        self.assertNotEqual(sample['infrastructure_recorder'], operator.pk)

        self.client.force_login(operator)
        start = self.client.get(path)
        self.assertContains(start, 'Stability rules need review')
        self.assertNotContains(start, 'Engineering stability observation')
        self.assertNotContains(start, 'Continue eligible work')
        for state in ('validated', 'active'):
            self.assertRedirects(self.client.post(sample['case_policy_path'], {
                'action': state, 'configuration': sample['criteria_draft'],
            }), sample['case_policy_path'], fetch_redirect_response=False)
        self.assertContains(self.client.get(path), 'Prerequisites need recheck')
        self.assertRedirects(self.client.post(path, {'action': 'resume', 'revision': work.revision}), path,
                             fetch_redirect_response=False)

        reader = users.create_user('hypercare-walkthrough-reader')
        Grant.objects.bulk_create([Grant(user=reader, case=work.case, action=action)
                                   for action in ('case.read', 'delivery.read', 'factory.read')])

        previous_source = None
        progress_id = None
        for result, count in (('not_met', 2), ('qualified', 0)):
            work.refresh_from_db()
            proof = sample['engineering_proofs'][result]
            values = {'action': 'stability_source', 'owner': 'Engineering',
                      'configuration': sample['criteria_draft'], 'observed_at': timezone.now().isoformat(),
                      'confirmed': 'yes', 'reference': proof['ref'], 'evidence': proof['id'], 'verify_sample': 'on',
                      'metric_0': count, 'revision': work.revision, 'case_revision': rev(work.case)}
            if result == 'not_met':
                self.client.force_login(reader)
                self.assertNotContains(self.client.get(path), 'Engineering stability observation')
                self.assertEqual(self.client.post(path, values).status_code, 403)
                self.assertFalse(dossier.sources.filter(kind='hypercare_engineering').exists())
                self.client.force_login(operator)

            self.assertRedirects(self.client.post(path, values), path, fetch_redirect_response=False)
            source = dossier.sources.filter(kind='hypercare_engineering').latest('pk')
            self.assertEqual((source.actor_id, source.evidence_id), (operator.pk, proof['id']))
            self.assertEqual(source.payload['metrics']['errors'], {'unit': 'count', 'value': count})
            work.refresh_from_db()
            advance = {'action': 'advance', 'revision': work.revision}
            activity_count = work.activities.count()
            assessment_count = dossier.records.filter(kind='hypercare').count()
            if result == 'not_met':
                self.client.force_login(reader)
                self.assertEqual(self.client.post(path, advance).status_code, 403)
                self.client.force_login(operator)
                self.assertContains(self.client.post(path, {**advance, 'revision': work.revision - 1}),
                                    'The work item changed.')
                self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
            else:
                self.assertEqual(FactoryProgress.objects.get(pk=progress_id).status, 'paused')
                self.assertIsNone(factory_progress.run_once())

            for _ in range(2):
                self.assertRedirects(self.client.post(path, advance), path, fetch_redirect_response=False)
            progress = FactoryProgress.objects.get(work=work)
            if progress_id is not None:
                self.assertEqual(progress.pk, progress_id)
            progress_id = progress.pk
            self.assertEqual((progress.requested_by_id, progress.status), (operator.pk, 'queued'))
            self.assertEqual(work.activities.count(), activity_count)
            self.assertEqual(dossier.records.filter(kind='hypercare').count(), assessment_count)

            for _ in range(12):
                self.assertEqual(factory_progress.run_once(), progress_id)
                progress.refresh_from_db()
                if progress.status in {'waiting', 'finished'}:
                    break
            self.assertEqual(progress.status, 'waiting' if result == 'not_met' else 'finished')
            work.refresh_from_db()
            assessment = factory_hypercare.assessed(work)
            self.assertEqual(assessment.snapshot['sources']['Infrastructure'][0], sample['infrastructure_source'])
            self.assertEqual(assessment.snapshot['sources']['Engineering'][0], source.pk)
            self.assertEqual(assessment.snapshot['acceptance_id'], sample['acceptance'])
            self.assertEqual(assessment.snapshot['qualified'], count == 0)
            if result == 'not_met':
                self.assertEqual(work.status, 'waiting')
                self.assertContains(self.client.get(path), 'Current observations do not meet the configured criteria.')
                previous_source, previous_assessment = source, assessment
                pause_path = reverse('factory_background', args=[work.pk])
                self.assertRedirects(self.client.post(pause_path, {'action': 'pause', 'revision': work.revision}),
                                     path, fetch_redirect_response=False)

        self.assertEqual(work.status, 'verified')
        verified = factory_hypercare.verify(work, operator)
        self.assertEqual(verified['hypercare'], assessment.pk)
        self.assertFalse(verified['deployment_authorized'])
        self.assertFalse(verified['financial_release_granted'])
        self.assertFalse(verified['closure_approved'])
        self.assertContains(self.client.get(path), 'Current source observations meet the configured stability criteria.')
        self.assertTrue(DeliverySource.objects.filter(pk=previous_source.pk).exists())
        self.assertTrue(dossier.records.filter(pk=previous_assessment.pk, snapshot__qualified=False).exists())
        self.assertEqual(dossier.records.filter(kind='hypercare').count(), 2)
        self.assertEqual(seed.prepare(operator), sample | {'existing_work_preserved': True})
