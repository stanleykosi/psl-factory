"""Human source controls remain available without offering unusable agent execution."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from apps.identity.models import Grant
from apps.workflows import factory_archive as archive
from apps.workflows.factory_views import presentation
from tests.test_delivery import DeliveryFixture
from tests.test_factory_archive import configure
from tests.helpers import rev


class MissingWorkerActionTests(TestCase):
    def test_manager_keeps_source_controls_but_cannot_advance_an_unavailable_worker(self):
        f = DeliveryFixture(); f.setup_delivery()
        f.operator = get_user_model().objects.create_user(username='missing-worker-archive-operator')
        for action in ['case.read', 'delivery.read', 'factory.execute', 'delivery.manage']:
            Grant.objects.create(case=f.case, user=f.operator, action=action)
        inventory = {kind: f.evidence(kind).pk for kind in archive.CORE_KINDS}
        configure(f)
        starter = get_user_model().objects.create_user(username='missing-execution-worker')
        for action in ['case.read', 'factory.read', 'factory.start', 'factory.execute', 'delivery.read', 'evidence.add']:
            Grant.objects.create(case=f.case, user=starter, action=action)
        work = archive.start(starter, f.case.pk, 'MISSING-WORKER', f.d.pk, inventory, 'Controlled archive with unavailable worker', rev(f.case))
        Grant.objects.filter(case=f.case, user=starter, action='factory.execute').update(active=False)
        archive.source(work, f.actor)  # Current intake-author provenance is intact.
        row = presentation(f.actor, work)
        self.assertTrue(row['archive']['intake_current']); self.assertTrue(row['archive']['can_correct'])
        self.assertFalse(row['can_advance'])
        self.assertEqual(work.budget_used, 0)
        self.client.force_login(f.actor)
        response=self.client.get('/',{'queue':'exceptions'})
        self.assertIn(work.pk,[item['work'].pk for item in response.context['rows']])
