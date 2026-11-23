"""Role access to the real Start work subjects mapped to the original 45 IDs.

The HTTP assertions cover the native work record and its permitted controls.
Several downstream processes share one work identity. Processing and final
receipts have their own domain acceptance suites.
"""
from importlib import import_module

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.identity.models import Grant
from apps.identity.team_models import StaffMembership
from apps.workflows import factory
from apps.workflows.factory_processes import process_for, PROCESS_IDS
from apps.workflows.models import FactoryAttempt
from .process_role_helpers import role_accounts


def original_fixture(component, cls=None, method=None, *, class_data=False, **kwargs):
    """Reuse the original native test intake, including its exact source records."""
    module = import_module('tests.test_factory_' + component)
    if cls is None:
        fixture = module.setup(**kwargs)
        if not isinstance(fixture, dict):
            return fixture.work
        return fixture['work'] if 'work' in fixture else fixture['w']
    fixture = getattr(module, cls)()
    if class_data:
        fixture.setUpTestData()
    fixture.setUp()
    return getattr(fixture, method)(**kwargs) if method else fixture.work


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class OriginalProcessRoleAccessTests(TestCase):
    def test_active_legacy_grant_and_project_scope_are_checked_together(self):
        from django.contrib.auth import get_user_model
        from django.core.exceptions import PermissionDenied
        from apps.core.models import Case
        from apps.identity.services import require, subject_actions, visible_cases

        case = Case.objects.create(tenant='role-query', title='Role check', kind='project', synthetic=True)
        other = Case.objects.create(tenant='other', title='Second project', kind='project', synthetic=True)
        support = Case.objects.create(tenant='role-query', title='Support', kind='support', synthetic=True)
        user = get_user_model().objects.create_user('legacy-native-source')
        for selected in (case, support):
            Grant.objects.create(user=user, case=selected, action='case.read')
            with self.assertNumQueries(1):
                require(user, selected, 'case.read')
        Grant.objects.create(user=user, case=other, action='case.read', active=False)
        Grant.objects.create(user=user, case=other, action='evidence.add')
        with self.assertRaises(PermissionDenied):
            require(user, other, 'case.read')
        self.assertEqual(set(visible_cases(user)), {case, support})
        get_user_model().objects.filter(pk=user.pk).update(is_active=False)
        self.assertTrue(user.is_active)  # Keep the object from before the change.
        with self.assertRaises(PermissionDenied):
            require(user, case, 'case.read')
        with subject_actions(user, case, ['case.read']), self.assertRaises(PermissionDenied):
            require(user, case, 'case.read')
        self.assertFalse(visible_cases(user).exists())

    def test_source_triggered_work_uses_its_department_detail_and_own_commands(self):
        from . import planning_helpers
        from .native_station_helpers import start_station

        f = planning_helpers.fixture()
        work = start_station(self, 'P17', f['packet'])
        roles = role_accounts(work.case)
        base = f'/api/v1/work/{work.pk}'
        progress = work.background_progress
        initial = (progress.status, work.revision)
        for actor, allowed in ((work.actor, True), (roles['pmo_member'], True), (roles['cto'], False)):
            self.client.force_login(actor)
            detail = self.client.get(base)
            self.assertEqual(detail.status_code, 200 if allowed else 404, detail.content[:400])
            if allowed:
                card = detail.json()
                destination = card['department_handoff_url']
                self.assertEqual(destination, base + '/department-handoff')
                native = self.client.get(destination).json()
                self.assertEqual((native['title'], native['process']), (card['title'], 'P17'))
                self.assertEqual(card['actions'], [])
                self.assertIsNone(card['revision'])
            history = self.client.get(base + '/history')
            self.assertEqual(history.status_code, 200 if allowed else 404)
            if allowed:
                self.assertEqual(history.json()['items'], [])
            for suffix, data in [('background', {'enabled': False}), ('actions', {'action': 'reconcile'})]:
                attempted = self.client.post(base + '/' + suffix, {**data, 'expected_revision': work.revision},
                                             content_type='application/json')
                self.assertEqual(attempted.status_code, 404, attempted.content[:400])
            generic = self.client.get('/api/v1/work', {'queue': 'active', 'line': work.definition})
            self.assertEqual(generic.json()['items'], [])
        work.refresh_from_db()
        progress.refresh_from_db()
        self.assertEqual((progress.status, work.revision), initial)

    def check_work(self, work, *processes, restricted=False, dispatched=False, investigation=None, roles=None):
        self.assertTrue(work.case.synthetic)
        self.assertTrue(set(processes) <= set(PROCESS_IDS[work.definition]))
        ui = reverse('factory_detail', args=[work.pk])
        api = f'/api/v1/work/{work.pk}'
        roles = roles or role_accounts(work.case)
        owner = Client()
        owner.force_login(work.actor)
        self.assertEqual(owner.get(ui).status_code, 200, work.definition)
        owner_api = owner.get(api)
        self.assertEqual(owner_api.status_code, 200, owner_api.content[:400])
        self.assertEqual(owner_api.json()['line'], work.definition)
        department = 'finance' if work.definition.startswith(('finance-', 'pmo-finance/')) else 'pmo'
        outcomes = {}
        for role, user in roles.items():
            self.client.force_login(user)
            page = self.client.get(ui)
            detail = self.client.get(api)
            if role in (department + '_head', department + '_member') and not restricted:
                self.assertEqual(page.status_code, 200, (role, work.definition))
                self.assertEqual(detail.status_code, 200, (role, detail.content[:400]))
                result = detail.json()
                self.assertEqual((result['id'], result['line'], result['django_url']), (work.pk, work.definition, ui))
                self.assertEqual(result['actions'], [])
                self.assertFalse(any(task['can_decide'] or task['can_claim'] for task in result['tasks']))
                outcomes[role] = 'read'
            else:
                self.assertIn(page.status_code, (403, 404), (role, work.definition))
                self.assertEqual(detail.status_code, 404, (role, work.definition))
                self.assertNotIn('line', detail.json())
                outcomes[role] = 'restricted'
        if restricted:
            self.client.force_login(roles['finance_member'])
            reference = work.request['reference']
            self.assertNotContains(self.client.get(reverse('home'), {'queue': 'active', 'line': work.definition}), reference)
            self.assertEqual(self.client.get('/api/v1/work', {'queue':'active','line':work.definition}).json()['items'], [])
            register = self.client.get(reverse('department_records', args=['chidi', work.case_id]),
                                       {'group': 'work', 'id': work.pk})
            self.assertEqual(register.status_code, 200)
            self.assertEqual(register.context['entries'], [])
        attempts = FactoryAttempt.objects.filter(activity__work=work, phase='observed')
        stages = set(attempts.filter(result__specialist__has_key='process')
                     .values_list('result__specialist__process', flat=True))
        receipt_lines = []
        for process in processes:
            if process == 'P28':
                self.assertTrue(attempts.filter(result__progress_investigation_id=investigation.pk).exists())
                level = 'native_investigation'
            elif dispatched:
                self.assertIn(process, stages, (work.definition, stages, work.finding))
                level = 'dispatched_work_record'
            else:
                self.assertEqual(process_for(work, 'ACT04', {}, {}), process)
                level = 'native_intake'
            receipt_lines.append(f'ROLE_ACCESS {process} ' + ' '.join(f'{key}={value}' for key, value in outcomes.items())
                                 + f' level={level} line={work.definition}')
        for line in receipt_lines:
            print(line, flush=True)
        return roles

    def test_engagement(self):
        from .test_factory_engagement import setup, complete

        f = setup()
        complete(f)
        self.check_work(f['w'], 'P16', 'P03', dispatched=True)

    def test_issue(self):
        self.check_work(original_fixture('issues', 'FactoryIssueTests'), 'P50')

    def test_minutes(self):
        self.check_work(original_fixture('minutes', 'FactoryMinutesTests', 'start'), 'P43')

    def test_escalation(self):
        self.check_work(original_fixture('escalation', 'FactoryEscalationTests', 'start'), 'P44')

    def test_weekly_reporting(self):
        from .test_factory_reporting import FactoryReportingTests

        f = FactoryReportingTests()
        f.setUp()
        f.configure()
        self.check_work(f.start_work(), 'P41')

    def test_monthly_leadership(self):
        self.check_work(original_fixture('leadership', 'FactoryLeadershipTests', 'start_work'), 'P42')

    def test_tuesday_leadership(self):
        from .test_factory_leadership import FactoryLeadershipTests

        f = FactoryLeadershipTests()
        f.setUp()
        f.tuesday()
        self.check_work(f.start_work(), 'P40')

    def test_emergency(self):
        from .test_factory_emergency import FactoryEmergencyTests

        f = FactoryEmergencyTests()
        f.setUp()
        f.start_work()
        f.advance()
        auth = f.authorized('coexist')
        actual = f.outcome(auth)
        f.select(auth, actual)
        f.advance()
        self.check_work(f.work, 'P61', 'P62', dispatched=True)

    def test_change(self):
        from apps.workflows import factory_change as change
        from .helpers import rev
        from .test_factory_change import FactoryChangeTests

        f = FactoryChangeTests()
        f.setUp()
        f.start()
        f.advance()
        auth = f.authorized()
        f.work.refresh_from_db()
        change.correct(f.actor, f.work.pk, f.work.revision, rev(f.case), f.cv.pk,
                       dict(f.inputs, authorization_id=auth.pk), 'Selected reviewed change authority.')
        f.advance()
        f.review('notice')
        f.advance()
        f.ready(auth)
        f.advance()
        f.review('go_live')
        f.advance()
        self.check_work(f.work, 'P57', 'P59', 'P60', dispatched=True)

    def test_bid(self):
        from django.utils import timezone
        from apps.pmo import rfp
        from apps.pmo.models import RFPSubmission
        from .factory_rfp_helpers import configured, start, reviewed_document
        from .helpers import rev

        f = configured()
        work = start(f)
        response, _ = reviewed_document(f, work)
        factory.run_until_wait(work.pk)
        submission = RFPSubmission.objects.get(response=response)
        rfp.outcome(f['actor'], f['case'].pk, submission.pk, 'won', timezone.now(), 'Client',
                    f['evidence']['rfp_outcome'].pk, 'Synthetic client award.', rev(f['case']))
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.check_work(work, 'P46', 'P47', 'P48', 'P49', dispatched=True)

    def test_costing_and_commercial(self):
        from .test_factory_commercial import setup, FactoryCommercialTests

        f = setup()
        FactoryCommercialTests().prepared_review(f)
        factory.run_until_wait(f['work'].pk)
        f['work'].refresh_from_db()
        self.check_work(f['work'], 'P14', 'P06', 'P07', dispatched=True)

    def test_planning(self):
        self.check_work(original_fixture('planning'), 'P26')

    def test_release_and_progress_investigation(self):
        from django.utils import timezone
        from apps.agents.models import AgentRun
        from apps.pmo import progress
        from apps.workflows import factory
        from .test_factory_delivery import setup
        from .helpers import rev

        f = setup()
        source = progress.configure(f.actor, f.case.pk, f.d.pk, 'Engineering', 'Synthetic board',
                                    'milestone', f.actor.pk, 'synthetic_mock', f.e['requirements'].pk, rev(f.case))
        progress.observe(f.actor, f.case.pk, source.pk, None, 'v1', timezone.now(), 'available', {
            'activity_ref': 'milestone', 'dependency_ref': 'card', 'summary': 'A dependency needs review.',
            'timeline_impact': True, 'scope_change': False,
        }, rev(f.case))
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        investigation = AgentRun.objects.filter(case=f.case, actor=f.work.execution_actor, process_id='P28',
                                                provider='deterministic-delivery-progress-v1').latest('pk')
        self.check_work(f.work, 'P32', 'P28', dispatched=True, investigation=investigation)

    def test_hypercare(self):
        self.check_work(original_fixture('hypercare'), 'P35')

    def test_archive(self):
        self.check_work(original_fixture('archive'), 'P36')

    def test_handover(self):
        self.check_work(original_fixture('handover'), 'P37')

    def test_closure(self):
        self.check_work(original_fixture('closure'), 'P39')

    def test_go_live(self):
        self.check_work(original_fixture('go_live'), 'P33')

    def test_incumbent_reference(self):
        self.check_work(original_fixture('ledger', 'FactoryLedgerTests', 'start'), 'F01')

    def test_income_schedule(self):
        self.check_work(original_fixture('schedules', 'FactorySchedulesTests', 'start'), 'F12')

    def test_inventory_schedule(self):
        self.check_work(original_fixture('schedules', 'FactorySchedulesTests', 'start', inventory=True), 'F13')

    def test_asset_records(self):
        self.check_work(original_fixture('ppe', 'FactoryPPETests', 'start'), 'F07')

    def test_forecast(self):
        self.check_work(original_fixture('forecast', 'ForecastFactoryTests', 'start'), 'F39')

    def test_payroll(self):
        from .test_factory_payroll import FactoryPayrollTests

        f = FactoryPayrollTests()
        f.setUpTestData()
        f.pipeline()
        self.client.force_login(f.f['manager'])
        received = self.client.get(reverse('factory_detail', args=[f.work.pk]))
        self.assertContains(received, 'Received aggregate report')
        self.assertNotContains(received, f.work.request['reference'])
        self.check_work(f.work, 'F16', 'F17', 'F18', restricted=True, dispatched=True)

    def test_staff_cost_exception(self):
        self.check_work(original_fixture('bu', 'FactoryBUTests', 'start', class_data=True), 'F21', restricted=True)

    def test_transaction_attribution(self):
        self.check_work(original_fixture('bu', 'FactoryBUTests', 'start', class_data=True, mode='event'),
                        'F44', restricted=True)

    def test_accounts(self):
        from apps.workflows import factory_accounting
        from apps.workflows.models import HumanTask
        from .factory_accounting_helpers import configured
        from .finance_analysis_helpers import fixture, METRICS

        actor, case, evidence, _, _, source, template, _ = fixture()
        work = configured(actor, case, evidence, source, template, METRICS)['work']
        factory.run_until_wait(work.pk)
        task = HumanTask.objects.get(case=case, kind='factory_accounting_review', status='open')
        task = factory_accounting.claim(actor, task.pk, task.revision)
        factory_accounting.decide(actor, task.pk, task.revision, 'approve', evidence['finance_review'].pk,
                                  'Reviewed synthetic accounts and output lineage.')
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.check_work(work, 'F03', 'F22', 'F09', 'F23', dispatched=True)

    def test_invoice(self):
        from tempfile import TemporaryDirectory
        from adapters.factory_invoices import MockFactoryInvoiceAdapter
        from apps.workflows.models import HumanTask
        from .factory_helpers import fixture
        from .obligation_helpers import factory_identified

        f = fixture()
        work = f['work']
        roles = role_accounts(work.case)
        milestone = f['handoff'].milestone
        for role in ('pmo_head', 'pmo_member'):
            self.client.force_login(roles[role])
            project = self.client.get(f'/api/v1/projects/{work.case_id}/milestones')
            self.assertEqual(project.status_code, 200, project.content[:400])
            completions = [row for section in project.json()['sections'] for row in section['items']]
            completion = next(row for row in completions if row['title'] == milestone.name)
            self.assertEqual(completion['django_url'],
                             reverse('department_records', args=['tola', work.case_id]) + f'?group=milestone&id={milestone.pk}')
            self.assertContains(self.client.get(completion['django_url']), milestone.name)
        with TemporaryDirectory() as directory:
            adapter = MockFactoryInvoiceAdapter(directory)
            factory.run_until_wait(work.pk, adapter=adapter)
            factory_identified(f)
            task = HumanTask.objects.get(case=work.case, kind='factory_review', status='open')
            task_url = f'/api/v1/tasks/{task.pk}'
            self.client.force_login(roles['finance_member'])
            refused = self.client.post(task_url + '/claim', {'expected_revision': task.revision},
                                       content_type='application/json')
            self.assertIn(refused.status_code, (403, 404, 422), refused.content[:400])
            task.refresh_from_db()
            self.assertIsNone(task.claimed_by_id)
            self.client.force_login(work.actor)
            claimed = self.client.post(task_url + '/claim', {'expected_revision': task.revision},
                                       content_type='application/json')
            self.assertEqual(claimed.status_code, 200, claimed.content[:400])
            reviewed = self.client.post(task_url + '/decision', {
                'expected_revision': claimed.json()['revision'], 'verdict': 'approve', 'evidence_id': f['proof'].pk,
                'note': 'Reviewed the original synthetic Finance packet and its assigned authority.',
            }, content_type='application/json')
            self.assertEqual(reviewed.status_code, 200, reviewed.content[:400])
            factory.run_until_wait(work.pk, adapter=adapter)
        work.refresh_from_db()
        self.check_work(work, 'P34', 'F29', 'F30', dispatched=True, roles=roles)

    def test_unassigned_project_grants_cannot_escape_a_current_or_ended_appointment(self):
        from apps.identity.services import visible_cases
        from apps.identity.teams import revoke
        from .test_factory_engagement import setup

        f = setup()
        roles = role_accounts(f['c'])
        other = setup(name='other-engagement-author')
        other_work = other['w']
        for key in ('cto', 'ceo', 'admin'):
            actor = roles[key]
            for action in ('case.read', 'engagement.read', 'factory.read'):
                Grant.objects.create(user=actor, case=other['c'], action=action)
            self.client.force_login(actor)
            ui = reverse('factory_detail', args=[other_work.pk])
            api = f'/api/v1/work/{other_work.pk}'
            self.assertEqual(self.client.get(ui).status_code, 404)
            self.assertEqual(self.client.get(api).status_code, 404)
            self.assertFalse(visible_cases(actor).filter(pk=other['c'].pk).exists())
            membership = StaffMembership.objects.get(user=actor, case=f['c'])
            revoke(membership.invitation.actor, f['c'].pk, membership.pk, 'Appointment ended in synthetic test.')
            self.assertFalse(visible_cases(actor).filter(pk=other['c'].pk).exists())
            self.assertEqual(self.client.get(ui).status_code, 404)
            self.assertEqual(self.client.get(api).status_code, 404)
