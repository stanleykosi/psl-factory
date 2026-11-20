"""Exercise the isolated fixture through the existing case and work commands."""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.identity.models import Grant
from apps.pmo.models import DeliveryDossier, DeliverySource
from apps.policy.services import resolve
from apps.workflows import factory_hypercare
from apps.workflows.models import FactoryWork
from tests import railway_hypercare_walkthrough_seed as seed
from tests.helpers import rev


class HypercareWalkthroughSeedTests(TestCase):
    def test_setup_hold_and_exact_failed_then_qualifying_observations(self):
        self.assertEqual(connection.vendor, 'postgresql')
        users = get_user_model().objects
        operator = users.create_user('hypercare-walkthrough-operator')
        sample = seed.prepare(operator)
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
            self.assertRedirects(self.client.post(path, {'action': 'advance', 'revision': work.revision}), path,
                                 fetch_redirect_response=False)
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
