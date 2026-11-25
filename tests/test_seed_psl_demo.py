"""The PSL design demo seed: people, clients and four projects, all through real services."""
import os
import stat
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase

from apps.core.models import Case
from apps.identity.team_models import StaffMembership
from apps.pmo.issues import Issue
from apps.pmo.models import Baseline, Milestone, RFPAssignment, RFPCase
from apps.workflows.models import FactoryWork

LAGOON, DELTA, KORA, SABI = ('Lagoon Health · patient app', 'Delta Foods · ordering app',
                              'Kora Logistics · fleet tracker', 'Sabi Market · web store')
SIGN_IN = {'tunde': 'tunde.bello', 'chinedu': 'chinedu.okeke', 'kemi': 'kemi.adebayo', 'ada': 'ada.okafor',
           'folake': 'folake.bello', 'ngozi': 'ngozi.adeyemi', 'amaka': 'amaka.obi'}
PROJECTS_SEEN = {
    'tunde': {LAGOON, KORA, SABI}, 'chinedu': {DELTA, SABI}, 'kemi': {LAGOON, DELTA, KORA, SABI},
    'ada': {LAGOON, DELTA, KORA, SABI}, 'folake': {LAGOON, DELTA, KORA, SABI}, 'ngozi': {LAGOON}, 'amaka': {LAGOON},
}
POSITIONS = {'tunde': [], 'chinedu': [], 'kemi': ['PMO Lead'], 'ada': ['Finance Lead'], 'folake': ['CEO'],
             'ngozi': ['HR'], 'amaka': ['Human resources']}
# Work each person has in flight (the Active work queue): the PMs' own lines and everything the PMO Lead oversees.
ACTIVE_WORK = {'tunde': 3, 'chinedu': 1, 'kemi': 4, 'ada': 0, 'folake': 0, 'ngozi': 0, 'amaka': 0}


class SeedPslDemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.credentials = Path(cls.folder.name) / 'people.txt'
        cls.out = StringIO()
        call_command('seed_psl_demo', credentials_file=str(cls.credentials), stdout=cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()
        super().tearDownClass()

    def client_for(self, key):
        client = Client()
        client.force_login(get_user_model().objects.get(username=SIGN_IN[key] + '@psl-demo.test'))
        return client

    def case(self, title):
        return Case.objects.get(tenant='psl-demo', title=title)

    def test_the_four_projects_exist_as_synthetic_workspaces(self):
        cases = Case.objects.filter(tenant='psl-demo')
        self.assertEqual({case.title for case in cases}, {LAGOON, DELTA, KORA, SABI})
        self.assertTrue(all(case.synthetic and case.kind == 'project' for case in cases))
        self.assertNotIn('password', self.out.getvalue().lower())

    def test_credentials_file_holds_only_sign_in_names_and_passwords(self):
        self.assertEqual(stat.S_IMODE(os.stat(self.credentials).st_mode), 0o600)
        rows = [line.split(' ') for line in self.credentials.read_text().splitlines()]
        self.assertEqual({row[0] for row in rows}, {name + '@psl-demo.test' for name in SIGN_IN.values()})
        self.assertTrue(all(len(row) == 2 and len(row[1]) >= 20 for row in rows))
        self.assertEqual(len({row[1] for row in rows}), len(rows))
        for name, password in rows:
            self.assertTrue(Client().login(username=name, password=password), name)
            self.assertNotIn(password, self.out.getvalue())

    def test_each_person_sees_the_expected_projects_and_work(self):
        for key in SIGN_IN:
            client = self.client_for(key)
            me = client.get('/api/v1/me')
            self.assertEqual(me.status_code, 200, key)
            self.assertEqual([item['name'] for item in me.json()['positions']], POSITIONS[key], key)
            projects = client.get('/api/v1/projects')
            self.assertEqual(projects.status_code, 200, key)
            self.assertEqual({item['title'] for item in projects.json()['items']}, PROJECTS_SEEN[key], key)
            self.assertTrue(all(item['sample'] for item in projects.json()['items']), key)
            work = client.get('/api/v1/work?queue=needs_me')
            self.assertEqual(work.status_code, 200, key)
            active = client.get('/api/v1/work?queue=active')
            self.assertEqual(active.json()['total'], ACTIVE_WORK[key], key)

    def test_pmo_lead_has_the_weekly_report_review_in_my_work(self):
        dashboard = self.client_for('kemi').get('/api/v1/role-dashboard').json()
        self.assertEqual([(row['title'], row['workspace']) for row in dashboard['decisions']],
                         [('Document review', LAGOON)])
        detail = self.client_for('kemi').get(f'/api/v1/role-work/{dashboard["decisions"][0]["id"]}')
        self.assertEqual(detail.json()['review']['verdicts'], ['approve'])
        report = FactoryWork.objects.get(definition='pmo-weekly-report/v1')
        self.assertEqual((report.case.title, report.status), (LAGOON, 'waiting'))
        for key in ('tunde', 'chinedu', 'ada', 'folake', 'ngozi', 'amaka'):
            self.assertEqual(self.client_for(key).get('/api/v1/role-dashboard').json()['decisions'], [], key)

    def test_projects_reach_the_stages_the_backend_can_honestly_reach(self):
        rows = {item['title']: item for item in self.client_for('kemi').get('/api/v1/projects').json()['items']}
        self.assertEqual({title: row['phase'] for title, row in rows.items()},
                         {LAGOON: 'Release', DELTA: 'Release', KORA: 'Pre-sale', SABI: None})
        costing = FactoryWork.objects.get(definition='commercial/v1')
        self.assertEqual(costing.case.title, KORA)
        self.assertIn('Costing awaits source information', costing.finding)

    def test_signed_baselines_milestones_issue_and_unassigned_bid(self):
        for title in (LAGOON, DELTA):
            self.assertTrue(Baseline.objects.get(case=self.case(title)).signed_id, title)
        for title in (KORA, SABI):
            self.assertFalse(Baseline.objects.filter(case=self.case(title), signed__isnull=False).exists(), title)
        self.assertEqual(list(Milestone.objects.filter(case=self.case(LAGOON)).order_by('pk').values_list('name', flat=True)),
                         ['Kick-off', 'UAT sign-off'])
        self.assertFalse(Milestone.objects.filter(case=self.case(DELTA)).exists())
        self.assertEqual(Issue.objects.get(case=self.case(LAGOON)).current.status, 'Open')
        sabi = RFPCase.objects.get(case=self.case(SABI))
        self.assertTrue(sabi.current_intake_id)
        self.assertFalse(RFPAssignment.objects.filter(intake__rfp=sabi).exists())

    def test_money_terms_come_from_the_design_fixture(self):
        client = self.client_for('ada')
        lagoon = self.case(LAGOON)
        rows = client.get(f'/api/v1/projects/{lagoon.pk}/money').json()
        stages = {row['label']: (row['amount'], row['due_date']) for row in rows['items'] if row['contract_stage']}
        self.assertEqual(stages['Signed agreement'], ('3000000.00', '2026-10-30'))
        self.assertEqual(stages['User acceptance testing'], ('4250000.00', '2026-11-10'))

    def test_staff_roles_use_the_real_staff_memberships(self):
        roles = {(item.user.username.split('@')[0], item.role, item.mode)
                 for item in StaffMembership.objects.select_related('user').filter(active=True)}
        self.assertEqual(roles, {('kemi.adebayo', 'pmo-lead', 'lead'), ('ada.okafor', 'finance-lead', 'lead'),
                                 ('folake.bello', 'ceo', 'standalone'), ('ngozi.adeyemi', 'hr', 'lead'),
                                 ('amaka.obi', 'hr', 'member')})

    def test_a_second_run_is_refused_and_nothing_changes(self):
        before = (Case.objects.count(), get_user_model().objects.count())
        with self.assertRaises(CommandError):
            call_command('seed_psl_demo', credentials_file=str(Path(self.folder.name) / 'again.txt'),
                         stdout=StringIO())
        self.assertFalse((Path(self.folder.name) / 'again.txt').exists())
        self.assertEqual((Case.objects.count(), get_user_model().objects.count()), before)
