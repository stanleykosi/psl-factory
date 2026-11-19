"""Check that grouped browser staging leaves operator decisions for the walkthrough."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.pmo.models import ArchiveCopyPlan, ChangeAuthorization, EmergencyAuthorization, EscalationDecision
from apps.workflows.models import FactoryProgress, FactoryWork
from tests.railway_batch_walkthrough_seed import PREPARATION, prepare_project


class DesignBatchWalkthroughTests(TestCase):
    def test_native_preparations_open_and_preserve_existing_journeys(self):
        actor = get_user_model().objects.create_user('synthetic-batch-browser-reviewer')
        self.client.force_login(actor)
        for key, (definition, _) in PREPARATION.items():
            with self.subTest(journey=key):
                prepared = prepare_project(actor, key)
                replay = prepare_project(actor, key)
                self.assertFalse(prepared['existing_work_preserved'])
                self.assertTrue(replay['existing_work_preserved'])
                self.assertEqual(prepared['work'], replay['work'])
                work = FactoryWork.objects.get(pk=prepared['work'], definition=definition,
                                               case__synthetic=True, actor=actor)
                self.assertFalse(FactoryProgress.objects.filter(work=work, status='running').exists())
                self.assertEqual(self.client.get(prepared['path']).status_code, 200)
        self.assertFalse(ArchiveCopyPlan.objects.exists())
        self.assertFalse(ChangeAuthorization.objects.exists())
        self.assertFalse(EmergencyAuthorization.objects.exists())
        self.assertFalse(EscalationDecision.objects.exists())
