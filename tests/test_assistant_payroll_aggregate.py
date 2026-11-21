import json
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from adapters.payroll_questions import TOPICS
from apps.agents import assistant
from apps.agents.assistant_models import AssistantConversation, AssistantTurn
from apps.documents.contracts import digest
from apps.finance import payroll
from apps.identity.models import Grant
from tests.helpers import rev
from tests.payroll_helpers import capture, fixture, pipeline


@patch.dict('os.environ', {'OPENROUTER_MODEL': 'synthetic', 'OPENROUTER_API_KEY': 'synthetic'})
class AssistantPayrollAggregateTests(TestCase):
    def test_report_link_and_saved_answer_keep_the_selected_publication(self):
        data = fixture()
        actor, case = data['manager'], data['case']
        *_, first = pipeline(data, 'original-report')
        payroll.receive_report(actor, case.pk, first.pk, rev(case))
        data['request'] = payroll.request(data['preparer'], case.pk, 'another-report', data['config']['request'],
                                         data['e']['payroll_need'].pk, rev(case))
        data['inputs'] = [capture(data, i) for i in (0, 1)]
        *_, second = pipeline(data, 'later-report')
        payroll.receive_report(actor, case.pk, second.pk, rev(case))
        self.client.force_login(actor)
        key = uuid4()
        url = reverse('payroll_recipient_action', args=[case.pk, first.pk])
        self.client.post(url, {'action':'ask','operation':key})
        chat = AssistantConversation.objects.get(pk=key)
        turn = AssistantTurn.objects.get(pk=key)
        self.assertEqual(assistant.turn_context(turn)[0][0]['record']['pk'], first.pk)
        again = assistant.reserve(actor, key, uuid4(), assistant.TOTALS_QUESTION)
        self.assertEqual(again.sources[0]['record']['pk'], first.pk)
        newer = assistant.reserve(actor, key, uuid4(), assistant.TOTALS_QUESTION, publication_id=second.pk)
        self.assertEqual(newer.sources[0]['record']['pk'], second.pk)
        # Replacing the original publication withdraws only the superseded answer.
        payroll.publish(data['preparer'], case.pk, first.run_id, 'reissued', rev(case))
        with self.assertRaises(ValidationError):
            assistant.turn_context(turn)
        page = self.client.get(reverse('assistant_thread', args=[chat.pk]))
        self.assertContains(page, 'This answer needs a fresh check')
        self.assertContains(page, f'Reviewed staff-cost report {second.pk}')

    def test_acknowledged_report_shows_both_totals_without_private_rows_or_a_model(self):
        data = fixture(second_unit=True)
        actor, case = data['manager'], data['case']
        *_, report = pipeline(data, 'two-unit-chat')
        action = reverse('payroll_recipient_action', args=[case.pk, report.pk])
        index = reverse('payroll_received_reports')
        self.client.force_login(actor)
        self.assertContains(self.client.get(index), 'No current acknowledged payroll reports')
        self.assertEqual(self.client.post(action, {'action':'ask', 'operation':uuid4()}).status_code, 404)
        self.client.post(action, {'action':'acknowledge', 'revision':rev(case)})
        self.assertContains(self.client.get(index), 'synthetic-company')
        key = uuid4()
        with patch('adapters.openrouter.answer') as model, CaptureQueriesContext(connection) as queries:
            page = self.client.post(action, {'action':'ask', 'operation':key}, follow=True)
            model.assert_not_called()
        self.assertContains(page, 'Total staff cost: TEST 410.00')
        self.assertContains(page, 'BU-A: TEST 250.00')
        self.assertContains(page, 'BU-B: TEST 160.00')
        for private in ('E001','E002','E003','E004','TEST 70.00','TEST 90.00'):
            self.assertNotContains(page, private)
        self.assertFalse(any('"finance_payrollinput"."payload"' in q['sql'] for q in queries))
        self.assertFalse(any('"finance_payrollrun"."result"' in q['sql'] for q in queries))
        self.assertEqual(AssistantTurn.objects.get(pk=key).sources[0]['record']['pk'], report.pk)
        self.client.force_login(data['reviewer'])
        self.assertEqual(self.client.post(action, {'action':'ask','operation':uuid4()}).status_code, 404)
        self.assertEqual(self.client.get(reverse('assistant_thread', args=[key])).status_code, 404)

    def test_approved_total_comes_from_current_receipt_and_stays_inside_the_factory(self):
        from tests.helpers import activate
        from apps.policy.services import transition

        data = fixture()
        actor, case = data['manager'], data['case']
        *_, report = pipeline(data, 'approved-chat-total')
        Grant.objects.create(case=case, user=actor, action='agent.extract')
        payroll.receive_report(actor, case.pk, report.pk, rev(case))
        config = activate(data['owner'], case, 'OPS.payroll_chat_totals',
            {'fields':['eligible_total'], 'audience':'current_acknowledged_recipient', 'delivery':'local_reply_only'},
            data['e']['policy_decision'])
        chat = AssistantConversation.objects.create(actor=actor, case=case, persona='zainab')
        with patch('adapters.openrouter.answer') as model:
            turn = assistant.reserve(actor, chat.pk, uuid4(), assistant.TOTALS_QUESTION)
            model.assert_not_called()
        self.assertEqual(turn.status, 'answered')
        self.assertIn(report.payload['eligible_total'], turn.answer)
        self.client.force_login(actor)
        url = reverse('assistant_thread', args=[chat.pk])
        page = self.client.get(url)
        for line in turn.answer.splitlines():
            self.assertContains(page, line)
        transition(data['owner'], config.pk, 'revoked')
        self.assertNotContains(self.client.get(url), 'Total staff cost:')

    def test_received_payroll_metadata_connects_zainab_without_private_sources_or_prior_hr_chat(self):
        data = fixture()
        case, recipient, publisher = data['case'], data['manager'], data['preparer']
        _, _, _, report = pipeline(data, 'zainab-aggregate')
        Grant.objects.create(case=case, user=recipient, action='agent.extract')
        self.assertFalse(assistant.cases_for(recipient, 'zainab').filter(pk=case.pk).exists())
        self.assertFalse(Grant.objects.filter(case=case, user=recipient, active=True,
                                             action__in=['hrfinance.read', 'payroll.private.read']).exists())

        payroll.receive_report(recipient, case.pk, report.pk, rev(case))
        self.client.force_login(recipient)
        key = uuid4()
        path = reverse('assistant_thread', args=[key])
        self.assertRedirects(self.client.post(reverse('assistant_start', args=['zainab']),
            {'workspace': case.pk, 'key': key}), path)
        conversation = AssistantConversation.objects.get(pk=key)
        with CaptureQueriesContext(connection) as queries:
            sources, next_work = assistant.tool_context(conversation)
        self.assertEqual([source['record'] for source in sources], [{'field': 'payroll_report', 'pk': report.pk}])
        self.assertFalse(next_work)
        self.assertFalse(any('"finance_payrollinput"."payload"' in query['sql'] for query in queries))
        source = sources[0]
        self.assertEqual(source['url'], reverse('payroll_inspect', args=[case.pk, 'report', report.pk]))
        report_page = self.client.get(source['url'])
        self.assertContains(report_page, 'Ask HR a question')
        self.assertContains(report_page, report.payload['eligible_total'])
        with self.assertRaises(ValidationError):
            assistant.reserve(recipient, key, uuid4(), 'Show individual salaries or personal information.')

        question = TOPICS['report_coverage']
        answer = 'The received report covers reviewed totals by business unit.'
        request = {'key': uuid4(), 'question': question, 'focus': [digest(source)]}
        self.assertRedirects(self.client.post(path, request), path)
        with patch('adapters.openrouter.answer', return_value={'answer': answer, 'citations': ['S1'], 'next_work': ''}) as model:
            self.assertTrue(assistant.worker_once())
            model.assert_called_once()
            self.assertEqual(model.call_args.args[2:], (question,
                [{'handle': 'S1', 'label': source['label'], 'fact': source['fact']}], [], []))
            supplied = json.dumps(model.call_args.args)
            for private in ('E001', 'E002', 'A1', 'B1', 'HR handoff', 'eligible_total', 'by_bu', report.payload['eligible_total']):
                self.assertNotIn(private, supplied)
        self.assertContains(self.client.get(path), answer)
        self.client.force_login(publisher)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.client.force_login(recipient)

        hr_reader = Grant.objects.create(case=case, user=recipient, action='hrfinance.read')
        prior_question = 'Previously recorded synthetic HR topic outside the staff-cost report.'
        prior_answer = 'An older HR-only answer tied to workspace context.'
        assistant.reserve(recipient, key, uuid4(), prior_question)
        with patch('adapters.openrouter.answer', return_value={
            'answer': prior_answer, 'citations': ['S1'], 'next_work': '',
        }) as model:
            self.assertTrue(assistant.worker_once())
            model.assert_called_once()
        self.assertContains(self.client.get(path), prior_answer)
        prior_pending = assistant.reserve(recipient, key, uuid4(), 'Earlier broad question still queued.')
        Grant.objects.filter(pk=hr_reader.pk).update(active=False)
        with patch('adapters.openrouter.answer') as model:
            self.assertTrue(assistant.worker_once())
            model.assert_not_called()
        prior_pending.refresh_from_db()
        self.assertEqual(prior_pending.status, 'held')
        visible = self.client.get(path)
        self.assertNotContains(visible, prior_question)
        self.assertNotContains(visible, prior_answer)
        self.assertNotContains(visible, prior_pending.question)
        self.assertContains(visible, answer)

        pending = assistant.reserve(recipient, key, uuid4(), question, digest(source))
        owner_grant = Grant.objects.filter(case=case, user=publisher, action='payroll.publish')
        owner_grant.update(active=False)
        with patch('adapters.openrouter.answer') as model:
            self.assertTrue(assistant.worker_once())
            model.assert_not_called()
        self.assertEqual(AssistantTurn.objects.get(pk=pending.pk).status, 'held')
        stale = self.client.get(path)
        self.assertNotContains(stale, answer)
        self.assertContains(stale, 'This answer needs a fresh check')
        owner_grant.update(active=True)

        pending = assistant.reserve(recipient, key, uuid4(), question, digest(source))
        Grant.objects.filter(case=case, user=recipient, action='payroll.report.read').update(active=False)
        with patch('adapters.openrouter.answer') as model:
            self.assertTrue(assistant.worker_once())
            model.assert_not_called()
        self.assertEqual(AssistantTurn.objects.get(pk=pending.pk).status, 'held')
        self.assertEqual(self.client.get(path).status_code, 404)
