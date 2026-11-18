import os
from uuid import uuid4
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.agents import assistant
from apps.agents.rfp_answer_models import RFPAnswerReview, RFPAnswerSuggestion
from apps.identity.models import Grant
from apps.pmo import rfp, rfp_answers
from apps.workflows import factory, factory_rfp
from tests.factory_rfp_helpers import configured, start, reviewed_document
from tests.helpers import rev


def fixture():
    data = configured('RFP-ANSWER-REVIEW')
    actor, case = data['actor'], data['case']
    for action in ['agent.extract', 'agent.rfp']:
        Grant.objects.get_or_create(user=actor, case=case, action=action, defaults={'active': True})
    data['payload']['matrix'].append(dict(data['payload']['matrix'][0], key='R2', response='Second cited coverage'))
    data['work'] = start(data)
    return data


def request(data, key='R1'):
    work = data['work']
    work.refresh_from_db()
    return rfp_answers.request(data['actor'], work.pk, key, uuid4(), work.revision, rev(data['case']))


def answer(suggestion, text='SAMPLE supported answer.'):
    with patch('adapters.openrouter.answer', return_value={'answer': text, 'citations': ['S1'], 'next_work': ''}) as model:
        assert assistant.worker_once()
    suggestion.turn.refresh_from_db()
    return model


def decision(suggestion, **changes):
    value = {'suggestion': suggestion.pk, 'predecessor': 0, 'verdict': 'accept', 'answer': '',
             'disposition': 'addressed', 'note': ''}
    value.update(changes)
    return value


@patch.dict(os.environ, {'OPENROUTER_MODEL': 'synthetic-model', 'OPENROUTER_API_KEY': 'synthetic'})
class RFPAnswerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = fixture()

    def save(self, decisions):
        data = self.data
        work = data['work']
        work.refresh_from_db()
        return rfp_answers.review(data['actor'], work.pk, work.revision, rev(data['case']), decisions)

    def test_model_draft_human_edit_native_reviews_submission_outcome_and_verified_route(self):
        data = self.data
        actor, case, work = data['actor'], data['case'], data['work']
        suggestion = request(data)
        self.assertEqual(suggestion.turn.status, 'queued')
        model = answer(suggestion)
        self.assertEqual(len(model.call_args.args[3]), 1)
        self.assertEqual(model.call_args.args[3][0]['fact']['requirement'], 'R1')
        self.assertEqual(model.call_args.args[4], [])
        self.save([decision(suggestion, verdict='edit', answer='SAMPLE reviewed answer with explicit source scope.')])
        work.refresh_from_db()
        self.assertEqual(factory_rfp.inputs(work)['matrix'][0]['response'], 'SAMPLE reviewed answer with explicit source scope.')
        self.assertEqual(suggestion.turn.answer, 'SAMPLE supported answer.')
        self.assertEqual(RFPAnswerReview.objects.get().actor_id, actor.pk)
        response, document = reviewed_document(data, work)
        self.assertEqual(response.matrix[0]['response'], 'SAMPLE reviewed answer with explicit source scope.')
        self.assertIn('SAMPLE reviewed answer', str(document.payload))
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        submitted = factory_rfp.submission_for(work)
        self.assertIsNotNone(submitted)
        rfp.outcome(actor, case.pk, submitted.pk, 'won', timezone.now(), 'Client',
            data['evidence']['rfp_outcome'].pk, 'SAMPLE customer award evidence.', rev(case))
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertEqual(work.status, 'verified', work.finding)
        self.assertFalse(factory_rfp.verify(work)['signed_baseline_imported'])

    def test_bulk_review_is_atomic_and_independent_rows_survive_undo(self):
        data = self.data
        one, two = request(data), request(data, 'R2')
        answer(one, 'SAMPLE first suggestion.')
        answer(two, 'SAMPLE second suggestion.')
        with self.assertRaises(ValidationError):
            self.save([decision(one), decision(two, disposition='invented')])
        self.assertFalse(RFPAnswerReview.objects.exists())
        saved = self.save([decision(one), decision(two)])
        work = data['work']
        work.refresh_from_db()
        rfp_answers.undo(data['actor'], work.pk, saved[0].pk, work.revision, rev(data['case']))
        work.refresh_from_db()
        matrix = factory_rfp.inputs(work)['matrix']
        self.assertEqual(matrix[0]['response'], one.row['response'])
        self.assertEqual(matrix[1]['response'], 'SAMPLE second suggestion.')
        self.assertEqual(RFPAnswerReview.objects.count(), 3)
        with self.assertRaises(ValidationError):
            rfp_answers.undo(data['actor'], work.pk, saved[0].pk, work.revision, rev(data['case']))

    def test_replace_keeps_private_reason_and_original_answer_out_of_native_wording(self):
        suggestion = request(self.data)
        answer(suggestion, 'SAMPLE original suggestion not adopted.')
        self.save([decision(suggestion, verdict='replace', answer='SAMPLE own answer.',
            disposition='clarification', note='SAMPLE internal rejection explanation.')])
        work = self.data['work']
        work.refresh_from_db()
        self.assertNotIn('internal rejection', work.source_head.body)
        self.assertNotIn('not adopted', work.source_head.body)
        self.assertEqual(RFPAnswerReview.objects.get().note, 'SAMPLE internal rejection explanation.')
        self.assertEqual(factory_rfp.inputs(work)['matrix'][0]['disposition'], 'clarification')
        with self.assertRaises(DatabaseError), transaction.atomic():
            RFPAnswerReview.objects.filter(suggestion=suggestion).update(note='overwrite')
        with self.assertRaises(DatabaseError), transaction.atomic():
            RFPAnswerSuggestion.objects.filter(pk=suggestion.pk).update(key='forged requirement')

    def test_changed_row_or_current_source_permission_holds_draft_and_hides_history(self):
        data = self.data
        suggestion = request(data)
        def revoke(*args):
            Grant.objects.filter(case=data['case'], user=data['actor'], action='rfp.prepare').update(active=False)
            return {'answer': 'SAMPLE withheld draft.', 'citations': ['S1'], 'next_work': ''}
        with patch('adapters.openrouter.answer', side_effect=revoke):
            self.assertTrue(assistant.worker_once())
        suggestion.turn.refresh_from_db()
        self.assertEqual(suggestion.turn.status, 'held')
        self.assertEqual(suggestion.turn.answer, '')
        self.client.force_login(data['actor'])
        self.assertEqual(self.client.get(reverse('factory_rfp_answers', args=[data['work'].pk])).status_code, 403)
        Grant.objects.filter(case=data['case'], user=data['actor'], action='rfp.prepare').update(active=True)
        fresh = request(data)
        answer(fresh)
        self.save([decision(fresh, verdict='replace', answer='SAMPLE current own answer.', note='SAMPLE private reason.')])
        Grant.objects.filter(case=data['case'], user=data['actor'], action='evidence.add').update(active=False)
        page = self.client.get(reverse('factory_rfp_answers', args=[data['work'].pk]))
        self.assertNotContains(page, 'SAMPLE private reason.')
        self.assertNotContains(page, 'SAMPLE supported answer.')
        self.assertNotContains(page, 'SAMPLE current own answer.')

    def test_http_review_replay_filters_and_retained_replacement_fields(self):
        data = self.data
        suggestion = request(data)
        answer(suggestion)
        self.client.force_login(data['actor'])
        url = reverse('factory_rfp_answers', args=[data['work'].pk])
        page = self.client.get(url + '?status=suggested')
        self.assertContains(page, 'Suggested by Tola')
        values = dict(decision(suggestion, verdict='replace', note='SAMPLE kept explanation.'),
            action='review', requirement='R1', revision=data['work'].revision, case_revision=rev(data['case']))
        self.assertContains(self.client.post(url, values), 'SAMPLE kept explanation.')
        values['answer'] = 'SAMPLE browser reviewed replacement.'
        self.assertEqual(self.client.post(url, values).status_code, 302)
        self.assertEqual(RFPAnswerReview.objects.count(), 1)
        self.assertContains(self.client.post(url, values), 'bid changed')
        self.assertEqual(RFPAnswerReview.objects.count(), 1)
        page = self.client.get(url + '?status=accepted&q=R1')
        self.assertContains(page, 'Own answer')
        self.assertContains(page, 'Undo this answer')

    def test_pending_request_replays_and_conflicting_identity_or_changed_row_is_rejected(self):
        data = self.data
        suggestion = request(data)
        work = data['work']
        same = rfp_answers.request(data['actor'], work.pk, 'R1', suggestion.turn_id, work.revision, rev(data['case']))
        self.assertEqual(same.pk, suggestion.pk)
        with self.assertRaises(ValidationError):
            rfp_answers.request(data['actor'], work.pk, 'R2', suggestion.turn_id, work.revision, rev(data['case']))
        with self.assertRaises(ValidationError):
            request(data)
        answer(suggestion)
        payload = {key: factory_rfp.inputs(work)[key] for key in factory_rfp.FIELDS}
        payload['matrix'] = [dict(payload['matrix'][0], response='SAMPLE independent current correction.'), payload['matrix'][1]]
        factory_rfp.correct(data['actor'], work.pk, work.revision, rev(data['case']), payload, 'SAMPLE changed requirement.')
        with self.assertRaises(ValidationError):
            self.save([decision(suggestion)])

    def test_many_requirement_rows_share_authority_and_source_reads(self):
        data = self.data
        work = data['work']
        current = factory_rfp.inputs(work)
        payload = {key: current[key] for key in factory_rfp.FIELDS}
        payload['matrix'] = [dict(current['matrix'][0], key='R' + str(number)) for number in range(1, 101)]
        factory_rfp.correct(data['actor'], work.pk, work.revision, rev(data['case']), payload,
            'SAMPLE hundred-requirement source inventory.')
        self.client.force_login(data['actor'])
        with CaptureQueriesContext(connection) as queries:
            page = self.client.get(reverse('factory_rfp_answers', args=[work.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, '100 of 100 requirements')
        print('PSL_RFP_ANSWER_LIST_QUERIES=' + str(len(queries)))
        self.assertLess(len(queries), 180)


@patch.dict(os.environ, {'OPENROUTER_MODEL': 'synthetic-model', 'OPENROUTER_API_KEY': 'synthetic'})
class RFPAnswerConcurrencyTests(TransactionTestCase):
    def test_competing_requests_create_one_durable_model_turn(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections

        data = fixture()
        barrier = Barrier(2)
        expected, case_revision = data['work'].revision, rev(data['case'])
        def reserve(_):
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                try:
                    return rfp_answers.request(data['actor'], data['work'].pk, 'R1', uuid4(), expected, case_revision).pk
                except ValidationError:
                    return None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, range(2)))
        self.assertEqual(sum(item is not None for item in results), 1)
        self.assertEqual(RFPAnswerSuggestion.objects.count(), 1)


class RFPAnswerFormTests(SimpleTestCase):
    def test_typed_review_and_templates(self):
        from apps.pmo.rfp_answer_views import AnswerForm
        from django.template.loader import get_template

        self.assertIsNotNone(get_template('factory/rfp_answers.html'))
        self.assertTrue(AnswerForm(decision(type('Suggestion', (), {'pk': 1})())).is_valid())
        self.assertFalse(AnswerForm({'suggestion': 1, 'predecessor': 0, 'verdict': 'replace',
                                    'answer': '', 'disposition': 'addressed'}).is_valid())
