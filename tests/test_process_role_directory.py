from html.parser import HTMLParser

from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from apps.core.services import add_evidence
from apps.core.models import Case
from apps.workflows.models import FactoryWork
from tests.helpers import rev, setup_case
from tests.process_role_helpers import role_accounts


class ProcessList(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = {}

    def handle_starttag(self, tag, attrs):
        row = dict(attrs)
        if tag == 'li' and 'data-process' in row:
            pid = row['data-process']
            if pid in self.rows:
                raise AssertionError(f'Duplicate process {pid}')
            self.rows[pid] = row['data-startable'] == 'true'


class ProcessRoleDirectoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author, cls.case = setup_case(username='process-catalogue-owner')
        cls.actors = role_accounts(cls.case)

    def test_six_roles_see_the_complete_catalogue_and_only_their_available_intakes(self):
        pmo = {'pmo-issues', 'engagement', 'pmo-minutes', 'pmo-escalation', 'pmo-weekly-report',
               'pmo-leadership-report', 'pmo-emergency', 'pmo-change', 'rfp-response', 'planning',
               'delivery-release', 'delivery-hypercare', 'delivery-go-live', 'delivery-archive',
               'delivery-handover', 'delivery-closure'}
        finance = {'finance-ledger','finance-accounts','finance-schedules','finance-ppe','finance-forecast','pmo-finance'}
        expected = {f'P{i:02}' for i in range(1, 64)} | {f'F{i:02}' for i in range(1, 46)}
        for role, actor in self.actors.items():
            with self.subTest(role=role):
                self.client.force_login(actor)
                page = self.client.get(reverse('factory_intake'))
                self.assertEqual(page.status_code, 200)
                html = ProcessList()
                html.feed(page.content.decode())
                response = self.client.get('/api/v1/processes')
                self.assertEqual(response.status_code, 200)
                items = response.json()['items']
                self.assertEqual(len(items), 108)
                flags = {item['process']: item['intake_available'] for item in items}
                self.assertSetEqual(set(flags), expected)
                self.assertEqual(html.rows, flags)
                self.assertEqual(sum(item['project_handoff'] for item in items), 63)
                available = {line+'/v1' for line in {'pmo_head': pmo, 'finance_head': finance}.get(role, set())}
                for item in items:
                    self.assertEqual(item['intake_available'], item['line'] in available, item['process'])
                self.assertEqual({r['key'] for r in self.client.get('/api/v1/lines').json()['items']}, available)
                print(f'ROLE_DIRECTORY {role} {len(flags)} processes; {sum(flags.values())} intake choices', flush=True)
        self.assertEqual(Client().get('/api/v1/processes').status_code, 401)
        self.assertEqual(Client().get(reverse('factory_intake')).status_code, 302)

    def test_role_scoped_engagement_api_creates_source_and_rejects_foreign_case(self):
        actor = self.actors['pmo_head']
        evidence = add_evidence(self.author, self.case.pk, 'engagement_source', 'Sample client request', 'Synthetic brief')
        data = {'line':'engagement/v1', 'case_id': str(self.case.pk), 'case_revision': rev(self.case),
                'idempotency_key':'role-source-intake', 'reference':'TEST-ENGAGEMENT-ROLE',
                'intake': {'route':'B','evidence_id':evidence.pk}}
        self.client.force_login(self.actors['finance_head'])
        self.assertEqual(self.client.post('/api/v1/work',data,content_type='application/json').status_code, 404)
        self.client.force_login(actor)
        foreign = Case.objects.create(tenant='separate-role-catalogue',title='Different organisation',kind='project',synthetic=True)
        self.assertEqual(self.client.post('/api/v1/work',{**data,'case_id':str(foreign.pk)},content_type='application/json').status_code,404)
        accepted = self.client.post('/api/v1/work',data,content_type='application/json')
        self.assertEqual(accepted.status_code,200,accepted.content)
        work = FactoryWork.objects.get(actor=actor,case=self.case,definition='engagement/v1')
        self.assertContains(self.client.get(reverse('factory_detail',args=[work.pk])),data['reference'])
        self.assertEqual(self.client.get(reverse('factory_create'),{'definition':'process-handoff/v1'}).status_code,404)


class VerifiedDepartmentReadingTests(TransactionTestCase):
    def test_verified_bid_reading_and_assistant_outcome_follow_the_receipt_reader(self):
        from django.utils import timezone
        from apps.agents.specialist_memory import outcome_sources, sources_for
        from apps.agents.specialist_models import SpecialistReading
        from apps.pmo import rfp
        from tests.native_station_helpers import assert_waiting, finish_station, start_station
        from tests.test_rfp import fixture

        actor, case, proof, _, _ = fixture(record_intake=False)
        intake = rfp.intake(actor, case.pk, 'ROLE-CHECK', proof['rfp_intake'].pk, timezone.now(),
                           'not_stated', None, None, 'Synthetic invitation to bid', rev(case))
        work = start_station(self, 'P45', intake)
        users = role_accounts(case)
        member = users['pmo_member']
        assert_waiting(self, work)
        report = SpecialistReading.objects.filter(work=work, status='ready').first()
        url = reverse('specialist_report', args=[work.pk, report.pk])
        self.client.force_login(member)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertFalse(sources_for(member, [case.pk], ['planning/v1'], work_id=work.pk))
        assignment = rfp.assign(actor, case.pk, actor, 'CEO', proof['policy_decision'].pk, 'Recorded appointment', rev(case))
        finish_station(self, work, assignment)
        self.assertEqual(self.client.get(url).status_code, 200)
        citations = sources_for(member, [case.pk], ['planning/v1'], work_id=work.pk)
        self.assertIn(url, [citation['url'] for citation in citations])
        self.assertEqual(outcome_sources(member, [case.pk], ['planning/v1'])[0]['record']['field'], 'native_station_receipt')
        outside = users['finance_head']
        self.client.force_login(outside)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertFalse(outcome_sources(outside, [case.pk], ['planning/v1']))
