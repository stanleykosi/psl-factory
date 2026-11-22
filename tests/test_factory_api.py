import os
from inspect import signature
from unittest.mock import patch
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase
from django.urls import resolve, reverse
from jsonschema import Draft202012Validator, FormatChecker

from apps.agents import assistant
from apps.agents.models import AgentJob, CaseUpload
from apps.agents.upload_jobs import ROLES
from apps.core.factory_api.intake import DERIVED_REFERENCES, INTAKE_GRANTS, STARTS
from apps.core.factory_api.urls import contract
from apps.finance.models import InvoiceIssue, InvoiceJob
from apps.identity.models import Grant
from apps.workflows import factory, factory_minutes
from apps.workflows.factory_definitions import DEFINITIONS
from apps.workflows.models import FactoryProgress, FactoryWork, HumanTask
from tests.factory_helpers import fixture
from tests.helpers import rev, setup_case
from tests.meeting_helpers import meetings_fixture
from tests.obligation_helpers import factory_identified


BASE = '/api/v1'
SPEC = contract()


class ContractTests(SimpleTestCase):
    def test_weekly_update_and_planning_screen_entries_have_their_own_workflows(self):
        import json
        from django.conf import settings

        screens = json.loads((settings.BASE_DIR / 'contracts/factory-api-screen-map.json').read_text())['screens']
        weekly, planning = screens['SCR-25'], screens['SCR-42']
        self.assertIn('weekly client update', weekly['journey'])
        self.assertIn('POST /work/{work_id}/reviews', weekly['json'])
        self.assertNotIn('factory_rfp_answers', weekly['django'])
        self.assertIn('Planning readiness', planning['journey'])
        self.assertIn('planning', planning['django'])
        self.assertNotIn('delivery', planning['django'])

    def test_contract_matches_mounted_routes_and_all_native_start_lines(self):
        from apps.workflows.native_station_contracts import DEFINITION as source_triggered
        self.assertEqual(set(STARTS), set(DEFINITIONS) - {source_triggered})
        self.assertEqual(set(STARTS), set(INTAKE_GRANTS))
        for line, (starter, schema) in STARTS.items():
            common = {'case_id': None, 'key': None, 'expected': None}
            if line not in DERIVED_REFERENCES:
                common['reference'] = None
            for shape in schema.get('oneOf', (schema,)):
                signature(starter).bind(None, **common, **dict.fromkeys(shape['properties']))
        self.assertEqual(self.client.get(f'{BASE}/openapi.json').json(), SPEC)
        ids = set()
        for route, methods in SPEC['paths'].items():
            for operation in methods.values():
                self.assertNotIn(operation['operationId'], ids)
                ids.add(operation['operationId'])
                example = route
                for parameter in operation['parameters']:
                    if parameter['in'] == 'path':
                        value = 'example' if parameter['schema']['type'] == 'string' else '1'
                        if parameter['schema'].get('format') == 'uuid':
                            value = str(uuid4())
                        example = example.replace('{' + parameter['name'] + '}', value)
                self.assertNotEqual(resolve(example).func.__name__, 'unknown')
                for code, response in operation['responses'].items():
                    if code != 'default':
                        Draft202012Validator.check_schema(response['content']['application/json']['schema'])
                if 'requestBody' in operation:
                    for content in operation['requestBody']['content'].values():
                        Draft202012Validator.check_schema(content['schema'])
        self.assertGreaterEqual(len(ids), 38)
        self.assertEqual(self.client.get(f'{BASE}/unknown').json()['code'], 'not_found')


class FactoryApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = fixture(username='api-synthetic-finance')
        cls.actor, cls.case, cls.work = (cls.data[key] for key in ('actor', 'case', 'work'))
        cls.outsider, cls.other_case = setup_case(username='api-other-operator')

    def post(self, url, body, client=None, **headers):
        return (client or self.client).post(BASE + url, body, content_type='application/json', **headers)

    def check(self, response, path, *, method='get', status=200):
        self.assertEqual(response.status_code, status, response.content[:700])
        self.assertIn('no-store', response.headers['Cache-Control'])
        value = response.json()
        schema = SPEC['paths'][BASE + path][method]['responses'][str(status)]['content']['application/json']['schema']
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)
        return value

    def test_session_csrf_read_only_errors_and_html_route(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get(f'{BASE}/me').json()['code'], 'unauthenticated')
        client.force_login(self.actor)
        profile = self.check(client.get(f'{BASE}/me'), '/me')
        self.assertIn('pmo-finance/v1', profile['startable_lines'])
        origin = 'https://frontend.example.test'
        headers = {'HTTP_ORIGIN': origin, 'HTTP_X_CSRFTOKEN': profile['csrf_token']}
        self.assertEqual(self.post('/tasks/1/claim', {}, client, **headers).status_code, 403)
        with self.settings(CSRF_TRUSTED_ORIGINS=[origin]):
            frontend_client = Client(enforce_csrf_checks=True)
            frontend_client.cookies = client.cookies.copy()
            self.assertEqual(self.post('/tasks/1/claim', {}, frontend_client, HTTP_ORIGIN=origin).status_code, 403)
            self.assertEqual(self.post('/tasks/1/claim', {}, frontend_client, **headers).status_code, 422)
        url = f'/work/{self.work.pk}/background'
        payload = {'expected_revision': self.work.revision, 'enabled': True}
        response = self.post(url, payload, client)
        self.assertEqual((response.status_code, response.json()['code']), (403, 'csrf_failed'))
        self.assertFalse(FactoryProgress.objects.exists())
        self.check(self.post(url, payload, client, HTTP_X_CSRFTOKEN=profile['csrf_token']),
                   '/work/{work_id}/background', method='post', status=202)
        self.assertTrue(FactoryProgress.objects.filter(work=self.work, requested_by=self.actor).exists())
        self.assertContains(client.get(reverse('factory_detail', args=[self.work.pk])), self.work.request['reference'])
        self.assertEqual(self.post(url, {**payload, 'expected_revision': 1.0}, client,
                                   HTTP_X_CSRFTOKEN=profile['csrf_token']).status_code, 422)

    def test_current_scope_and_bounded_queue_do_not_expose_private_work(self):
        self.client.force_login(self.actor)
        work_url = f'{BASE}/work/{self.work.pk}'
        detail = self.check(self.client.get(work_url), '/work/{work_id}')
        self.assertEqual(detail['line'], self.work.definition)
        self.assertFalse(detail['tasks'])
        self.check(self.client.get(work_url + '/history'), '/work/{work_id}/history')
        self.check(self.client.get(f'{BASE}/work?queue=mine'), '/work')
        self.check(self.client.get(f'{BASE}/projects'), '/projects')
        self.check(self.client.get(f'{BASE}/projects/{self.case.pk}'), '/projects/{case_id}')
        self.check(self.client.get(f'{BASE}/projects/{self.case.pk}/documents'), '/projects/{case_id}/{tab}')
        self.check(self.client.get(f'{BASE}/projects/{self.case.pk}/money'), '/projects/{case_id}/money')
        self.check(self.client.get(f'{BASE}/projects/{self.case.pk}/month-end'), '/projects/{case_id}/month-end')
        self.check(self.client.get(f'{BASE}/overview'), '/overview')
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(work_url).json(), self.client.get(f'{BASE}/work/9999999').json())
        self.assertFalse(self.client.get(f'{BASE}/work?queue=mine').json()['items'])
        self.assertEqual(self.client.get(f'{BASE}/projects/{self.case.pk}/money').status_code, 404)

    def test_native_invoice_claim_review_and_stale_revision(self):
        native = self.data
        factory.run_until_wait(self.work.pk)
        work = factory_identified(native)
        task = HumanTask.objects.filter(case=self.case, kind='factory_review', status='open').latest('pk')
        self.client.force_login(self.outsider)
        claim_url = f'/tasks/{task.pk}/claim'
        self.assertEqual(self.post(claim_url, {'expected_revision': task.revision}).status_code, 404)
        self.client.force_login(self.actor)
        packet = self.check(self.client.get(f'{BASE}/tasks/{task.pk}'), '/tasks/{task_id}')['invoice_packet']
        self.assertEqual(packet['amount'], '42.00')
        self.assertNotIn('recipient_id', packet)
        claim = self.check(self.post(claim_url, {'expected_revision': task.revision}),
                           '/tasks/{task_id}/claim', method='post')
        self.assertEqual(self.post(claim_url, {'expected_revision': task.revision}).status_code, 409)
        current = self.client.get(f'{BASE}/tasks/{task.pk}').json()
        self.assertIn(native['proof'].pk, [row['id'] for row in current['review_evidence']])
        decision = self.check(self.post(f'/tasks/{task.pk}/decision', {
            'expected_revision': claim['revision'], 'verdict': 'approve',
            'evidence_id': native['proof'].pk, 'note': 'Reviewed the exact fictional invoice packet.',
        }), '/tasks/{task_id}/decision', method='post')
        self.assertEqual(decision['verdict'], 'approve')
        history = self.client.get(f'{BASE}/work/{work.pk}/history?kind=decision').json()
        self.assertIn('approve', [row['status'] for row in history['items']])
        self.assertFalse(InvoiceJob.objects.filter(invoice=work.invoice).exists())
        self.assertFalse(InvoiceIssue.objects.filter(invoice=work.invoice).exists())

    @patch.dict(os.environ, {'OPENROUTER_MODEL': 'synthetic', 'OPENROUTER_API_KEY': 'synthetic'})
    def test_assistant_replays_current_sources_and_hides_answer_after_revocation(self):
        self.client.force_login(self.actor)
        opened = self.check(self.post('/assistant/conversations', {
            'case_id': str(self.case.pk), 'agent': 'tola', 'idempotency_key': str(uuid4()),
        }), '/assistant/conversations', method='post')
        conversation_url = '/assistant/conversations/' + opened['conversation_id']
        source = next(item['key'] for item in self.client.get(BASE + conversation_url).json()['available_sources']
                      if item['label'] == 'Commercial requirements')
        body = {'text': 'What did the fictional requirements say?', 'source_keys': [source],
                'idempotency_key': str(uuid4())}
        for _ in range(2):
            self.check(self.post(conversation_url + '/messages', body),
                       '/assistant/conversations/{conversation_id}/messages', method='post', status=202)
        with patch('adapters.openrouter.answer', return_value={
            'answer': 'The source describes the fictional requirement.', 'citations': ['S1'], 'next_work': '',
        }):
            self.assertTrue(assistant.worker_once())
        response = self.check(self.client.get(BASE + conversation_url), '/assistant/conversations/{conversation_id}')
        self.assertEqual(len(response['messages']), 1)
        self.assertTrue(response['messages'][0]['answer'])
        Grant.objects.filter(case=self.case, user=self.actor, action='commercial.read').update(active=False)
        response = self.client.get(BASE + conversation_url).json()
        self.assertEqual(response['messages'][0]['status'], 'source_changed')
        self.assertIsNone(response['messages'][0]['answer'])
        self.assertEqual(response['messages'][0]['sources'], [])
        self.assertNotContains(self.client.get(opened['django_url']), 'The source describes the fictional requirement.')

    @patch.dict(os.environ, {'OPENROUTER_MODEL': 'synthetic', 'OPENROUTER_API_KEY': 'synthetic'})
    def test_assistant_draft_version_starts_only_the_exact_reviewed_work(self):
        self.client.force_login(self.actor)
        started = self.post('/assistant/conversations', {
            'case_id': str(self.case.pk), 'agent': 'chidi', 'idempotency_key': str(uuid4()),
        }).json()
        url = '/assistant/conversations/' + started['conversation_id']
        key = str(uuid4())
        self.assertEqual(self.post(url + '/messages', {
            'text': 'Can I prepare the invoice for this exact milestone?', 'idempotency_key': key,
        }).status_code, 202)
        with patch('adapters.openrouter.answer', return_value={
            'answer': 'Use the exact fictional milestone handoff.', 'citations': ['S2'], 'next_work': 'pmo-finance/v1',
        }):
            self.assertTrue(assistant.worker_once())
        draft_url = '/assistant/turns/' + key + '/draft'
        payload = {
            'line': 'pmo-finance/v1', 'case_revision': rev(self.case), 'draft_version': None, 'background': False,
            'draft': {'reference': self.work.request['reference'], 'mode': 'completion', 'due_date': None,
                      'coverage': self.data['coverage'].pk, 'handoff': self.data['handoff'].pk,
                      'preparation': None, 'invoice': None},
        }
        saved = self.check(self.post(draft_url, payload), '/assistant/turns/{turn_id}/draft', method='post')
        self.assertEqual(saved['draft_version'], 1)
        self.assertIsNone(saved['started_work_id'])
        self.assertEqual(self.check(self.client.get(BASE + draft_url), '/assistant/turns/{turn_id}/draft'), saved)
        start_url = '/assistant/turns/' + key + '/start'
        payload['draft_version'] = 1
        changed = {**payload, 'draft': {**payload['draft'], 'reference': 'UNREVIEWED-TEST'}}
        self.assertEqual(self.post(start_url, changed).status_code, 422)
        for _ in range(2):
            result = self.check(self.post(start_url, payload), '/assistant/turns/{turn_id}/start', method='post')
            self.assertEqual(result['work_id'], self.work.pk)
        self.assertEqual(FactoryWork.objects.filter(case=self.case).count(), 1)
        self.assertFalse(InvoiceIssue.objects.filter(invoice__case=self.case).exists())

    @patch.dict(os.environ, {'OPENROUTER_MODEL': 'synthetic'})
    def test_private_file_review_and_exact_handoff(self):
        self.client.force_login(self.actor)
        route = f'/cases/{self.case.pk}/files'
        with patch('adapters.case_uploads.put') as store:
            file = self.check(self.client.post(BASE + route, {
                'file': SimpleUploadedFile('facts.txt', b'Fictional release facts.'),
            }), '/cases/{case_id}/files', method='post')
            self.assertEqual(store.call_args.args[1], b'Fictional release facts.')
        self.assertTrue(CaseUpload.objects.filter(pk=file['upload_id'], actor=self.actor).exists())
        queue_path = f'{route}/{file["upload_id"]}/drafts'
        for role in ROLES:
            queued = self.check(self.post(queue_path, {'role': role}), '/cases/{case_id}/files/{upload_id}/drafts',
                                method='post', status=202)
            self.assertEqual(queued['role'], role)
        self.assertEqual(AgentJob.objects.filter(upload_id=file['upload_id']).count(), 8)
        job = AgentJob.objects.get(upload_id=file['upload_id'], role='A02')
        job.status = 'draft'
        job.result = {'summary': 'Synthetic release source', 'quotes': ['Fictional release facts.'], 'gaps': [],
                      'source_sha256': file['sha256'], 'model': 'synthetic'}
        job.save()
        job_path = f'/cases/{self.case.pk}/file-drafts/{job.pk}'
        draft = self.check(self.client.get(BASE + job_path), '/cases/{case_id}/file-drafts/{job_id}')['draft']
        self.assertEqual(draft['excerpts'], ['Fictional release facts.'])
        response = self.check(self.post(job_path + '/review', {
            'draft': draft['pin'], 'summary': 'Human-reviewed fictional release evidence', 'gaps': [],
            'note': 'Compared with the test file.',
        }), '/cases/{case_id}/file-drafts/{job_id}/review', method='post')
        self.assertEqual(response['status'], 'reviewed')
        response = self.check(self.post(job_path + '/handoff', {'role': 'A02', 'confirm': True}),
                              '/cases/{case_id}/file-drafts/{job_id}/handoff', method='post')
        self.assertIsNotNone(response['workflow_record_id'])
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(BASE + job_path).status_code, 404)


class FactoryApiIntakeTests(TestCase):
    def test_minutes_reuses_native_intake_and_holds_background_without_execute_authority(self):
        actor, case, _, notes, template, *_ = meetings_fixture()
        for action in ('factory.start', 'factory.read'):
            Grant.objects.get_or_create(case=case, user=actor, action=action)
        Grant.objects.filter(case=case, user=actor, action='factory.execute').update(active=False)
        self.client.force_login(actor)
        payload = {
            'line': factory_minutes.DEFINITION, 'case_id': str(case.pk), 'case_revision': rev(case),
            'reference': 'API-MINUTES', 'idempotency_key': 'API-MINUTES', 'background': True,
            'intake': {'data': {'protocol': factory_minutes.PROTOCOL, 'meeting_version_id': None,
                                'evidence_id': notes.pk, 'template_id': template.pk, 'audience': 'internal', 'publish': False}},
        }
        created = self.client.post(f'{BASE}/work', payload, content_type='application/json')
        self.assertEqual(created.status_code, 200, created.content[:500])
        work = FactoryWork.objects.get(pk=created.json()['work_id'])
        self.assertEqual(work.definition, factory_minutes.DEFINITION)
        self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
        self.assertEqual(created.json()['background'], 'held')
        self.assertContains(self.client.get(reverse('factory_detail', args=[work.pk])), 'API-MINUTES')
