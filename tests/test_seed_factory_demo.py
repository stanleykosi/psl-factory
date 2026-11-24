"""The factory demo seed reaches a real PMO Lead review wait; a PMO Lead can complete a milestone."""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.pmo.models import Milestone
from apps.pmo.services import complete_milestone
from apps.workflows.models import FactoryWork
from tests.helpers import admit_department, rev, setup_case, signed


class SeedFactoryDemoTests(TestCase):
    def test_seed_reaches_pmo_lead_review_and_refuses_a_second_run(self):
        call_command('seed_demo', stdout=StringIO())
        out = StringIO()
        call_command('seed_factory_demo', stdout=out)
        work = FactoryWork.objects.get(definition='pmo-weekly-report/v1')
        self.assertTrue(work.case.synthetic)
        self.assertEqual(work.status, 'waiting', work.finding)
        actor = get_user_model().objects.get(username='studio-demo')
        self.client.force_login(actor)
        detail = self.client.get(f'/api/v1/work/{work.pk}')
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertEqual(detail.json()['status_label'], 'Awaiting PMO Lead review')
        self.assertIn(f'weekly report work {work.pk}: waiting', out.getvalue())
        with self.assertRaises(CommandError):
            call_command('seed_factory_demo', stdout=StringIO())
        self.assertEqual(FactoryWork.objects.filter(definition='pmo-weekly-report/v1').count(), 1)

    def test_seed_refuses_a_non_synthetic_project(self):
        call_command('seed_demo', stdout=StringIO())
        Case.objects.filter(tenant='synthetic-demo', kind='project').update(synthetic=False)
        with self.assertRaises(Case.DoesNotExist):
            call_command('seed_factory_demo', stdout=StringIO())
        self.assertFalse(FactoryWork.objects.exists())


class PmoLeadMilestoneTests(TestCase):
    def setUp(self):
        self.owner, self.case = setup_case()
        self.evidence = signed(self.owner, self.case)

    def complete(self, user):
        return complete_milestone(user, self.case.pk, 'M1', self.evidence['completion'].pk, rev(self.case))

    def test_pmo_lead_completes_a_milestone(self):
        lead, member = admit_department(self.owner, self.case, 'pmo-lead', member=True)
        milestone = self.complete(lead)
        self.assertEqual(milestone.completed_by_id, lead.pk)
        self.assertTrue(Milestone.objects.filter(case=self.case, name='M1').exists())

    def test_member_and_other_roles_cannot_complete_a_milestone(self):
        lead, member = admit_department(self.owner, self.case, 'pmo-lead', member=True)
        finance_lead, _ = admit_department(self.owner, self.case, 'finance-lead')
        for user in (member, finance_lead):
            with self.assertRaises(PermissionDenied):
                self.complete(user)
        self.assertFalse(Milestone.objects.filter(case=self.case).exists())
