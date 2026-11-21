from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TestCase
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.identity.models import Grant
from apps.pmo import planning, planning_inputs
from apps.pmo.models import DeliverySource, PlanningDepartmentInput
from apps.workflows.models import FactoryAttempt, FactoryProgress, FactoryWork
from tests import railway_planning_readiness_walkthrough_seed as seed
from tests.helpers import rev


ENVIRONMENT = {'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
               'PGDATABASE': 'synthetic-preview', seed.GUARD: '1'}


@patch.dict('os.environ', ENVIRONMENT)
class PlanningReadinessWalkthroughSeedTests(TestCase):
    def test_live_matching_claim_keeps_exact_five_inputs_and_current_private_costing_scope(self):
        self.assertEqual(connection.vendor, 'postgresql')
        reader = get_user_model().objects.create_user('psl-agent-trial')
        with patch.dict('os.environ', {seed.GUARD: '0'}):
            with self.assertRaisesMessage(RuntimeError, 'Planning readiness fixture guard'):
                seed.prepare()
        self.assertFalse(Case.objects.filter(pk=seed.CASE_ID).exists())
        sample = seed.prepare()
        self.assertEqual(seed.prepare(), sample | {'preserved': True})
        work = FactoryWork.objects.select_related('actor', 'case').get(pk=sample['work'])
        self.assertNotEqual(work.actor_id, reader.pk)
        self.client.force_login(reader)
        label = 'Preparing readiness from 5 of 5 recorded department inputs.'
        self.assertNotContains(self.client.get(sample['path']), label)

        def inspect_live_claim(seconds):
            self.assertEqual(seconds, seed.WINDOW_SECONDS)
            work.refresh_from_db()
            claim = FactoryAttempt.objects.get(activity__work=work, activity__kind='ACT03',
                                                phase='started', fence=work.fence)
            collection = claim.observation['report']['readiness_inputs']['department_inputs']
            self.assertEqual({row['department']: row['id'] for row in collection['inputs']}, sample['inputs'])
            self.assertEqual(collection['review_id'], sample['review'])
            self.assertIsNone(planning.latest(work.case, 'ready'))
            page = self.client.get(sample['path'])
            self.assertContains(page, label)
            self.assertContains(page, 'data-work-watch')
            self.assertContains(page, 'Keep the reviewed costing. Proposal version 2. Earlier proposal version 1.')
            entries = {item['department']: item['record'] for item in page.context['row']['planning']['department_inputs']['rows']}
            self.assertEqual((entries['QA']['effort_state'], entries['QA']['person_days']), ('unknown', None))
            self.assertEqual((entries['Security']['effort_state'], entries['Security']['person_days']), ('known', '0.000'))
            self.assertEqual(entries['Product']['effort_state'], 'not_applicable')

            with transaction.atomic():
                Grant.objects.filter(user=reader, case=work.case, action='costing.source.read').update(active=False)
                restricted = self.client.get(sample['path'])
                self.assertContains(restricted, label)
                self.assertNotContains(restricted, 'Earlier proposal version')
                transaction.set_rollback(True)
            with transaction.atomic():
                Grant.objects.filter(user=reader, case=work.case, action='approval.source.read:synthetic-planning-scope').update(active=False)
                self.assertNotContains(self.client.get(sample['path']), label)
                transaction.set_rollback(True)
            with transaction.atomic():
                original = PlanningDepartmentInput.objects.get(pk=sample['inputs']['Engineering'])
                planning_inputs.record(work.actor, work.case_id, sample['packet'], 'Engineering', original.pk,
                    original.source_id, 'Sample Engineering', timezone.now(), 'Later sample engineering statement.',
                    'known', Decimal('4.000'), rev(work.case))
                self.assertNotContains(self.client.get(sample['path']), label)
                transaction.set_rollback(True)

        with patch.object(seed, 'sleep', side_effect=inspect_live_claim) as live:
            result = seed.observe(work.pk)
        live.assert_called_once_with(seed.WINDOW_SECONDS)
        self.assertEqual(result['packet'], sample['packet'])
        self.assertNotContains(self.client.get(sample['path']), label)
        self.assertEqual(planning.latest(work.case, 'ready').pk, result['readiness'])
        self.assertFalse(DeliverySource.objects.filter(dossier__case=work.case, kind='scope_baseline').exists())
        self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
        self.assertEqual(Audit.objects.filter(case=work.case, action=seed.OBSERVATION).count(), 1)
        with self.assertRaisesMessage(RuntimeError, 'fresh exact readiness claim'):
            seed.observe(work.pk)
