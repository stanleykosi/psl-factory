"""A real source-owned correction must remain usable after the work starter leaves."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from apps.identity.models import Grant
from apps.workflows import factory_archive as archive
from tests.test_delivery import DeliveryFixture
from tests.test_factory_archive import configure
from tests.helpers import rev


class StarterSuccessorProjectionTests(TestCase):
    def test_current_native_source_successor_does_not_borrow_the_starter_access(self):
        f = DeliveryFixture(); f.setup_delivery()
        f.operator = get_user_model().objects.create_user(username='successor-archive-operator')
        for action in ['case.read', 'delivery.read', 'factory.execute', 'delivery.manage']:
            Grant.objects.create(case=f.case, user=f.operator, action=action)
        f.inventory = {kind: f.evidence(kind).pk for kind in archive.CORE_KINDS}
        configure(f)
        starter = get_user_model().objects.create_user(username='unavailable-successor-starter')
        for action in ['case.read', 'factory.read', 'factory.start', 'factory.execute', 'delivery.read', 'evidence.add']:
            Grant.objects.create(case=f.case, user=starter, action=action)
        work = archive.start(starter, f.case.pk, 'SUCCESSOR-STARTER', f.d.pk, f.inventory, 'Controlled archive intake', rev(f.case))
        previous_head = work.source_head_id
        Grant.objects.filter(case=f.case, user=starter, action='delivery.read').update(active=False)
        # Original intake-author authority is genuinely withdrawn; preserve that hold.
        with self.assertRaises(PermissionDenied): archive.source(work, f.actor)
        self.assertFalse(archive.projection(f.actor, work)['intake_current'])
        self.assertTrue(archive.projection(f.actor, work)['can_correct'])
        current = f.evidence('technical_document', 'Synthetic actual revised technical document')
        inventory = dict(f.inventory, technical_document=current.pk)
        archive.correct(f.actor, work.pk, work.revision, rev(f.case), inventory, 'Source owner reviewed the actual successor document')
        work.refresh_from_db()
        self.assertNotEqual(work.source_head_id, previous_head)
        self.assertEqual(work.actor_id, starter.pk)
        archive.source(work, f.actor)  # Current native provenance and viewer access both pass.
        self.assertTrue(archive.projection(f.actor, work)['intake_current'])


class DeliverySuccessorReaderTests(TestCase):
    def check_successor(self, module, f, field, evidence_kind):
        starter = get_user_model().objects.create_user(username='departed-delivery-starter')
        for action in ['case.read', 'factory.read', 'factory.start', 'factory.execute', 'delivery.read', 'evidence.add']:
            Grant.objects.create(case=f.case, user=starter, action=action)
        work = module.start(starter, f.case.pk, 'CURRENT-SOURCE-READER', f.d.pk, f.inputs, 'Reviewed delivery evidence', rev(f.case))
        old_head = work.source_head_id
        Grant.objects.filter(case=f.case, user=starter, action='delivery.read').update(active=False)
        with self.assertRaises(PermissionDenied): module.source(work, f.actor)
        replacement = f.evidence(evidence_kind, 'Actual revised synthetic delivery source')
        module.correct(f.actor, work.pk, work.revision, rev(f.case), dict(f.inputs, **{field: replacement.pk}), 'Reviewed genuine source successor')
        work.refresh_from_db()
        self.assertNotEqual(work.source_head_id, old_head)
        self.assertEqual(work.actor_id, starter.pk)
        module.source(work, f.actor)
        row = module.projection(f.actor, work)
        if 'intake_current' in row:
            self.assertTrue(row['intake_current'], row)
        else:
            self.assertNotIn('no active grant', row['finding'])
        from django.urls import reverse
        self.client.force_login(f.actor)
        response = self.client.get(reverse('factory_detail', args=[work.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Current worker: Needs current authority')
        self.assertNotContains(response, 'Continue eligible work')
        # Reading the current successor neither repairs the worker nor spends an allowance.
        self.assertEqual(work.budget_used, 0)
        from apps.workflows.models import FactoryActivity
        self.assertFalse(FactoryActivity.objects.filter(work=work).exists())
        # A current viewer cannot repair the successor author's revoked source authority.
        Grant.objects.filter(case=f.case, user=f.actor, action='evidence.add').update(active=False)
        with self.assertRaises(PermissionDenied): module.source(work, f.actor)
        Grant.objects.filter(case=f.case, user=f.actor, action='evidence.add').update(active=True)
        Grant.objects.filter(case=f.case, user=f.actor, action='delivery.read').update(active=False)
        with self.assertRaises(PermissionDenied): module.projection(f.actor, work)

    def test_handover_current_source_reader(self):
        from apps.workflows import factory_handover as module
        f = DeliveryFixture(); f.setup_delivery()
        f.inputs = {'template_id': f.t.pk, 'support_document': f.evidence('support_document').pk,
                    'escalation_document': f.evidence('escalation_document').pk}
        self.check_successor(module, f, 'support_document', 'support_document')

    def test_closure_current_source_reader(self):
        from apps.workflows import factory_closure as module
        from tests.test_factory_closure import setup
        f = setup(capture=False)
        self.check_successor(module, f, 'report_evidence_id', 'closure_report')

    def test_go_live_current_source_reader(self):
        from apps.workflows import factory_go_live as module
        from tests.test_factory_go_live import setup
        f = setup(capture=False)
        self.check_successor(module, f, 'rollback', module.KINDS['rollback'])
