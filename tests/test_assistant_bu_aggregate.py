import json
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from apps.agents import assistant
from apps.agents.assistant_models import AssistantConversation, AssistantTurn
from apps.documents.contracts import digest
from apps.finance import bu
from apps.identity.models import Grant
from tests import bu_helpers
from tests.helpers import rev


@patch.dict('os.environ', {'OPENROUTER_MODEL': 'synthetic', 'OPENROUTER_API_KEY': 'synthetic'})
class AssistantBusinessUnitAggregateTests(TestCase):
    def test_only_current_received_aggregate_reaches_the_finance_assistant(self):
        data = bu_helpers.fixture()
        case, recipient, publisher = data['case'], data['manager'], data['preparer']
        report = bu_helpers.publish(data, bu_helpers.staff(data))
        currency = report.payload['currency']
        Grant.objects.create(user=recipient, case=case, action='agent.extract')
        self.assertFalse(assistant.cases_for(recipient, 'chidi').filter(pk=case.pk).exists())
        self.assertFalse(Grant.objects.filter(user=recipient, case=case, action='finance.read', active=True).exists())

        bu.receive(recipient, case.pk, report.pk, rev(case))
        self.client.force_login(recipient)
        key = uuid4()
        path = reverse('assistant_thread', args=[key])
        self.assertRedirects(self.client.post(reverse('assistant_start', args=['chidi']),
                                              {'workspace': case.pk, 'key': key}), path)
        conversation = AssistantConversation.objects.get(pk=key)
        sources, next_work = assistant.tool_context(conversation)
        self.assertEqual([s['label'] for s in sources], ['Workspace', f'Reviewed business unit report {report.pk}'])
        self.assertFalse(next_work)
        self.assertEqual(sources[1]['url'], reverse('bu_inspect', args=[case.pk, 'report', report.pk]))
        self.assertIn(f'{currency} 250.00', sources[1]['fact'])
        self.assertIn(f'BU-A: {currency} 220.00', sources[1]['fact'])
        for private in ('E900', 'E002', 'staff_counts', 'weights'):
            self.assertNotIn(private, json.dumps(sources))

        focus = [digest(sources[1])]
        answer = f'The reviewed business units have {currency} 250.00 allocated.'
        question = {'key': uuid4(), 'question': 'What is the total in the received report?', 'focus': focus}
        self.assertRedirects(self.client.post(path, question), path)
        with patch('adapters.openrouter.answer', return_value={
            'answer': answer, 'citations': ['S1'], 'next_work': '',
        }) as model:
            self.assertTrue(assistant.worker_once())
            supplied = model.call_args.args[3]
            self.assertEqual([(item['label'], item['fact']) for item in supplied],
                             [(sources[1]['label'], sources[1]['fact'])])
            self.assertEqual(model.call_args.args[4], [])
        self.assertContains(self.client.get(path), answer)

        waiting = dict(question, key=uuid4(), question='Confirm the current total.')
        self.assertRedirects(self.client.post(path, waiting), path)
        Grant.objects.filter(user=publisher, case=case, action='bu.publish').update(active=False)
        with patch('adapters.openrouter.answer') as model:
            self.assertTrue(assistant.worker_once())
            model.assert_not_called()
        self.assertEqual(AssistantTurn.objects.get(pk=waiting['key']).status, 'held')
        self.assertNotContains(self.client.get(path), answer)
        unfocused = {'key': uuid4(), 'question': 'What can I see now?'}
        self.assertRedirects(self.client.post(path, unfocused), path)
        with patch('adapters.openrouter.answer') as model:
            self.assertTrue(assistant.worker_once())
            model.assert_not_called()
        self.assertEqual(AssistantTurn.objects.get(pk=unfocused['key']).answer, assistant.INSUFFICIENT_EVIDENCE)

    def test_received_f44_event_aggregate_hides_private_transactions_from_the_model(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from tests import payroll_helpers

        data = bu_helpers.configure(payroll_helpers.fixture())
        case, recipient = data['case'], data['manager']
        event_ids = ('PRIVATE-EVENT-F44-001', 'PRIVATE-EVENT-F44-002')
        source = bu_helpers.source(data, control_total='100', rows=[
            {'event_id': event_ids[0], 'amount': '70', 'tags': ['DIRECT-A']},
            {'event_id': event_ids[1], 'amount': '30', 'tags': ['DIRECT-A']},
        ])
        work = bu_helpers.event(data, s=source)
        report = bu_helpers.publish(data, work)
        currency = report.payload['currency']
        Grant.objects.create(user=recipient, case=case, action='agent.extract')
        self.assertFalse(Grant.objects.filter(user=recipient, case=case, active=True,
                                              action__in=['finance.read', 'bu.private.read']).exists())
        self.assertFalse(assistant.cases_for(recipient, 'chidi').filter(pk=case.pk).exists())
        bu.receive(recipient, case.pk, report.pk, rev(case))

        self.client.force_login(recipient)
        key = uuid4()
        path = reverse('assistant_thread', args=[key])
        self.assertRedirects(self.client.post(reverse('assistant_start', args=['chidi']),
                                              {'workspace': case.pk, 'key': key}), path)
        conversation = AssistantConversation.objects.get(pk=key)
        with CaptureQueriesContext(connection) as queries:
            sources, next_work = assistant.tool_context(conversation)
        self.assertEqual(len(sources), 2)
        self.assertFalse(next_work)
        for query in queries.captured_queries:
            self.assertNotIn('"finance_invoice"', query['sql'])
            self.assertNotIn('"finance_handoff"', query['sql'])

        aggregate = sources[1]
        self.assertEqual(aggregate['url'], reverse('bu_inspect', args=[case.pk, 'report', report.pk]))
        readback = self.client.get(aggregate['url'])
        self.assertContains(readback, 'BU-A')
        self.assertContains(readback, '100.00')
        for private in event_ids:
            self.assertNotContains(readback, private)
        self.assertEqual(self.client.get(reverse('bu_inspect', args=[case.pk, 'work', work.pk])).status_code, 403)

        request = {'key': uuid4(), 'question': 'What was allocated in the received transaction report?',
                   'focus': [digest(aggregate)]}
        self.assertRedirects(self.client.post(path, request), path)
        answer = f'The reviewed business unit report allocated {currency} 100.00 to BU-A.'
        with patch('adapters.openrouter.answer', return_value={'answer': answer, 'citations': ['S1'], 'next_work': ''}) as model:
            self.assertTrue(assistant.worker_once())
        model.assert_called_once()
        supplied = model.call_args.args[3]
        self.assertEqual(supplied, [{'handle': 'S1', 'label': aggregate['label'], 'fact': aggregate['fact']}])
        self.assertIn(f'BU-A: {currency} 100.00', supplied[0]['fact'])
        for private in (*event_ids, 'DIRECT-A', 'event_id', 'cost_delta'):
            self.assertNotIn(private, json.dumps(supplied))
        self.assertContains(self.client.get(path), answer)
