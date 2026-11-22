"""A current source action belongs in the lead's exact native queue."""
import json
from contextlib import redirect_stdout
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.identity.models import Grant
from apps.pmo.models import DeliveryDossier
from apps.workflows import factory_hypercare as hypercare, factory_progress
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import railway_hypercare_lead_queue_seed as seed
from tests.helpers import rev


@patch.dict('os.environ', {'RAILWAY_PROJECT_ID': seed.base.PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                           seed.GUARD: '1', 'PGDATABASE': 'synthetic-preview'})
@patch.object(factory_progress, 'WAIT_INTERVAL', timedelta(0))
class HypercareLeadQueueSeedTests(TestCase):
    def test_exact_wait_is_actionable_only_in_source_scope_then_qualifies_from_a_fresh_observation(self):
        self.assertEqual(connection.vendor, 'postgresql')
        operator = get_user_model().objects.create_user('psl-agent-trial', first_name='Sample lead')
        previous = Case.objects.create(pk=seed.base.PRIMARY_CASE_ID, tenant=seed.base.TENANT,
                                       title='Preserved earlier Hypercare workspace', kind='project', synthetic=True)
        previous_grant = Grant.objects.create(case=previous, user=operator, action='case.read')
        initial_revision = rev(previous)
        with patch.dict('os.environ', {seed.GUARD: '0'}):
            with self.assertRaisesMessage(RuntimeError, 'Hypercare lead queue fixture guard'):
                seed.run()
        self.assertFalse(Case.objects.filter(pk=seed.CASE_ID).exists())
        log = StringIO()
        with redirect_stdout(log):
            seed.run()
        prefix, result = log.getvalue().strip().split('=', 1)
        self.assertEqual(prefix, seed.GUARD)
        sample = json.loads(result)
        self.assertEqual(seed.prepare(operator), sample | {'preserved': True})

        work = FactoryWork.objects.select_related('case').get(pk=sample['work'])
        dossier = DeliveryDossier.objects.get(pk=sample['dossier'], case=work.case, candidate_id=sample['candidate'])
        original = dossier.sources.get(pk=sample['original'], kind='hypercare_engineering', actor=operator)
        assessment = dossier.records.get(pk=sample['assessment'], kind='hypercare')
        self.assertEqual(work.status, 'waiting')
        self.assertEqual(original.payload['metrics']['errors'], {'unit': 'count', 'value': 2})
        self.assertIs(assessment.snapshot['qualified'], False)
        self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
        self.assertNotEqual(sample['infrastructure_verifier'], operator.pk)

        def queued(route):
            return self.client.get(sample[route])

        def successor():
            work.refresh_from_db()
            return self.client.post(sample['path'], {
                'action': 'stability_source', 'owner': 'Engineering', 'configuration': sample['criteria'],
                'observed_at': timezone.now().isoformat(), 'confirmed': 'yes', 'reference': sample['successor_reference'],
                'evidence': sample['successor_proof'], 'verify_sample': 'on', 'metric_0': 0,
                'revision': work.revision, 'case_revision': rev(work.case),
            })

        self.client.force_login(operator)
        page = queued('needs_attention')
        self.assertEqual([row['work'].pk for row in page.context['rows']], [work.pk])
        self.assertContains(page, 'Record the current stability observations')
        self.assertContains(page, 'Owner: Sample lead')
        self.assertFalse(queued('waiting_on_others').context['rows'])
        self.assertContains(self.client.get(sample['path']), 'Engineering stability observation')

        reader = get_user_model().objects.get(pk=sample['reader'])
        self.client.force_login(reader)
        self.assertFalse(queued('needs_attention').context['rows'])
        waiting = queued('waiting_on_others')
        self.assertEqual([row['work'].pk for row in waiting.context['rows']], [work.pk])
        self.assertNotContains(waiting, 'Record the current stability observations')
        self.assertNotContains(self.client.get(sample['path']), 'Engineering stability observation')
        self.assertEqual(successor().status_code, 403)
        self.assertEqual(dossier.sources.filter(kind='hypercare_engineering').count(), 1)

        self.client.force_login(operator)
        capture_grant = Grant.objects.get(case=work.case, user=operator, action='delivery.source')
        Grant.objects.filter(pk=capture_grant.pk).update(active=False)
        self.assertFalse(queued('needs_attention').context['rows'])
        self.assertEqual(successor().status_code, 403)
        Grant.objects.filter(pk=capture_grant.pk).update(active=True)
        self.assertRedirects(successor(), sample['path'], fetch_redirect_response=False)
        successor_source = dossier.sources.filter(kind='hypercare_engineering').latest('pk')
        self.assertEqual((successor_source.evidence_id, successor_source.actor_id),
                         (sample['successor_proof'], operator.pk))
        self.assertNotEqual(successor_source.pk, original.pk)
        work.refresh_from_db()
        self.assertRedirects(self.client.post(sample['path'], {'action': 'advance', 'revision': work.revision}),
                             sample['path'], fetch_redirect_response=False)
        progress = FactoryProgress.objects.get(work=work, requested_by=operator)
        for _ in range(16):
            self.assertEqual(factory_progress.run_once(), progress.pk)
            work.refresh_from_db()
            if work.status == 'verified':
                break
        else:
            self.fail(f'The original durable request did not verify the corrected observations: {work.finding}')
        verified = hypercare.verify(work, operator)
        approved = dossier.records.get(pk=verified['hypercare'])
        self.assertEqual(approved.snapshot['sources']['Engineering'][0], successor_source.pk)
        self.assertEqual(approved.snapshot['sources']['Infrastructure'][0], sample['infrastructure'])
        self.assertEqual(approved.snapshot['acceptance_id'], sample['acceptance'])
        self.assertIs(approved.snapshot['qualified'], True)
        self.assertFalse(verified['deployment_dispatched'])
        self.assertFalse(verified['financial_release_granted'])
        self.assertFalse(verified['closure_approved'])
        self.assertEqual([row['work'].pk for row in queued('verified').context['rows']], [work.pk])

        Grant.objects.filter(case=work.case, user_id=sample['infrastructure_verifier'],
                             action='delivery.verify').update(active=False)
        with self.assertRaises(PermissionDenied):
            hypercare.verify(work, operator)
        self.assertFalse(queued('verified').context['rows'])
        self.assertTrue(dossier.records.filter(pk=approved.pk).exists())
        self.assertTrue(dossier.records.filter(pk=assessment.pk).exists())
        self.assertEqual(seed.prepare(operator), sample | {'preserved': True})
        self.assertEqual(rev(previous), initial_revision)
        self.assertEqual(list(Grant.objects.filter(case=previous).values_list('pk', flat=True)), [previous_grant.pk])
        self.assertFalse(Audit.objects.filter(case=previous).exists())
