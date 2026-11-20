"""The fresh bid walkthrough seed prepares permission and leaves intake to the browser."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from adapters.upload_text import extract
from apps.agents.models import CaseUpload
from apps.core.models import Case
from apps.identity import intake
from apps.identity.intake_models import CaseIntake, TenantAuthority
from apps.identity.models import Grant
from apps.pmo.models import RFPCase
from tests import railway_rfp_fresh_intake_seed as seed


class FreshBidStartFixtureTests(TestCase):
    def test_prepares_only_the_exact_start_permission_and_preserves_existing_staff_scope(self):
        self.assertEqual(connection.vendor, 'postgresql')
        users = get_user_model().objects
        recorder = users.create_user(seed.RECORDER)
        administrator = users.create_superuser('sample-existing-scope-bootstrap')
        existing = intake.provision(administrator, recorder, 'sample-existing-workspace',
            {**seed.scope(), 'allowed_actions': ['case.read'], 'initial_actions': ['case.read']},
            timezone.now() + timedelta(hours=1), True, 'Synthetic pre-existing workspace-only action set.')
        workspace = intake.create_case(recorder, existing.tenant, 'sample-original', 'Original sample workspace', 'project')
        original_grants = list(Grant.objects.filter(user=recorder).values_list('case_id', 'action', 'active'))

        sample = seed.prepare(recorder)
        existing.refresh_from_db()
        self.assertEqual(existing.value['initial_actions'], ['case.read'])
        self.assertEqual(Grant.objects.filter(case=workspace, user=recorder).count(), 1)
        self.assertEqual(list(Grant.objects.filter(user=recorder).values_list('case_id', 'action', 'active')), original_grants)
        self.assertFalse(CaseIntake.objects.filter(tenant=seed.TENANT).exists())
        self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())
        self.assertFalse(RFPCase.objects.exists())
        self.assertFalse(CaseUpload.objects.exists())
        self.assertIsNone(sample['existing_receipt'])

        repeated = seed.prepare(recorder)
        self.assertTrue(repeated['preserved'])
        self.assertEqual(repeated['authority'], sample['authority'])
        self.assertEqual(TenantAuthority.objects.filter(tenant=seed.TENANT, user=recorder).count(), 1)
        bootstrap = users.get(username=seed.BOOTSTRAP)
        self.assertFalse(bootstrap.is_active or bootstrap.is_superuser or bootstrap.is_staff or bootstrap.has_usable_password())
        recorder.refresh_from_db()
        self.assertTrue(recorder.is_active)
        self.assertFalse(recorder.is_staff or recorder.is_superuser or recorder.has_usable_password())

        self.client.force_login(recorder)
        self.assertContains(self.client.get(reverse('factory_intake')), 'Log a received bid')
        form = self.client.get(sample['entry'])
        self.assertContains(form, seed.TENANT)
        self.assertNotContains(form, existing.tenant)
        self.assertContains(form, 'Attach the bid document')
        attachment = seed.sample_document()
        self.assertEqual(attachment, seed.sample_document())
        source = extract(sample['file_name'], attachment)
        for value in (sample['reference'], sample['prospect'], sample['deadline'], sample['submission_target']):
            self.assertIn(value, source)
