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

    def test_reuse_requires_a_released_winning_answer_and_current_access(self):
        from apps.pmo import winning_answers
        from apps.policy.services import transition
        from tests.helpers import activate, setup_case

        destination = self.data
        owner, project = setup_case(username='prior-award-owner')
        original = configured('SAMPLE-PRIOR-WIN', context=(owner, project))
        work = start(original)
        response, _ = reviewed_document(original, work)
        factory.run_until_wait(work.pk)
        submission = factory_rfp.submission_for(work)
        outcome = rfp.outcome(owner, project.pk, submission.pk, 'won', timezone.now(), 'Client',
            original['evidence']['rfp_outcome'].pk, 'Sample award for this version.', rev(project))
        factory.run_until_wait(work.pk)
        actor, case = destination['actor'], destination['case']
        rule = activate(owner, project, 'OPS.winning_bid_reuse', {'answers': [
            {'outcome_id':outcome.pk, 'requirement':'R1', 'destination':str(case.pk)}]}, original['evidence']['policy_decision'])
        self.assertEqual(winning_answers.options(actor, case), [])
        for action in ['case.read', 'rfp.read']:
            Grant.objects.create(case=project, user=actor, action=action)
        token, _, citation = winning_answers.options(actor, case)[0]
        self.assertEqual(citation['fact'], response.matrix[0]['response'])
        target = destination['work']
        suggestion = rfp_answers.request(actor, target.pk, 'R1', uuid4(), target.revision, rev(case), prior_choice=token)
        self.assertEqual(suggestion.turn.answer, citation['fact'])
        self.assertFalse(suggestion.reviews.exists())
        transition(owner, rule.pk, 'revoked')
        with self.assertRaises(PermissionDenied):
            self.save([decision(suggestion)])

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

    def test_api_answer_review_and_verified_winning_handoff(self):
        data = self.data
        actor, case, work = data['actor'], data['case'], data['work']
        self.client.force_login(actor)
        url = f'/api/v1/work/{work.pk}/bid-answers'
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200, page.content)
        self.assertTrue(page.json()['can_write'])
        requested = self.client.post(url, {'action': 'suggest', 'key': 'R1', 'operation_key': str(uuid4()),
            'expected_revision': page.json()['expected_revision'], 'case_revision': page.json()['case_revision']},
            content_type='application/json')
        self.assertEqual(requested.status_code, 201, requested.content)
        suggestion = RFPAnswerSuggestion.objects.get(pk=requested.json()['record_ids'][0])
        answer(suggestion)
        current = self.client.get(url).json()
        item = current['rows'][0]
        self.assertTrue(item['can_review'])
        wording = 'Synthetic reviewed API response citing the original requirement.'
        reviewed = self.client.post(url, {'action': 'review', 'expected_revision': current['expected_revision'],
            'case_revision': current['case_revision'], 'decisions': [decision(suggestion, verdict='edit', answer=wording)]},
            content_type='application/json')
        self.assertEqual(reviewed.status_code, 201, reviewed.content)
        self.assertEqual(self.client.get(url).json()['rows'][0]['response'], wording)
        work.refresh_from_db()
        _, document = reviewed_document(data, work)
        self.assertIn(wording, str(document.payload))
        submission_api = f'/api/v1/work/{work.pk}/bid-submission'
        ready = self.client.get(submission_api)
        self.assertEqual(ready.status_code, 200, ready.content)
        queued = self.client.post(submission_api, {key: ready.json()[key]
            for key in ('expected_revision', 'case_revision', 'version_id')}, content_type='application/json')
        self.assertEqual(queued.status_code, 202, queued.content)
        factory.run_until_wait(work.pk)
        submitted = factory_rfp.submission_for(work)
        self.assertIsNotNone(submitted)
        self.assertEqual(self.client.get(submission_api).json()['submission']['id'], submitted.pk)
        rfp.outcome(actor, case.pk, submitted.pk, 'won', timezone.now(), 'Client',
                    data['evidence']['rfp_outcome'].pk, 'Actual synthetic customer award.', rev(case))
        factory.run_until_wait(work.pk)
        report = self.client.get(f'/api/v1/work/{work.pk}/bid-outcomes')
        self.assertEqual(report.status_code, 200, report.content)
        self.assertEqual(report.json()['submissions'][0]['id'], submitted.pk)
        self.assertEqual(report.json()['handoff']['kind'], 'route_a')
        self.assertFalse(report.json()['handoff']['baseline_imported'])

    def test_bulk_review_is_atomic_and_independent_rows_survive_undo(self):
        data = self.data
        one, two = request(data), request(data, 'R2')
        answer(one, 'SAMPLE first suggestion.')
        answer(two, 'SAMPLE second suggestion.')
        with self.assertRaises(ValidationError):
            self.save([decision(one), decision(two, disposition='invented')])
        self.assertFalse(RFPAnswerReview.objects.exists())
        work = data['work']
        self.client.force_login(data['actor'])
        url = f'/api/v1/work/{work.pk}/bid-answers'
        def record(action, **fields):
            current = self.client.get(url).json()
            return self.client.post(url, {'action': action, 'expected_revision': current['expected_revision'],
                'case_revision': current['case_revision'], **fields}, content_type='application/json')
        applied = record('review', decisions=[decision(one), decision(two)])
        self.assertEqual(applied.status_code, 201, applied.content)
        saved = [RFPAnswerReview.objects.get(pk=pk) for pk in applied.json()['record_ids']]
        accepted = self.client.get(url).json()['rows']
        self.assertEqual([row['review_verdict'] for row in accepted], ['accept', 'accept'])
        work.refresh_from_db()
        undone = record('undo', review_id=saved[0].pk)
        self.assertEqual(undone.status_code, 201, undone.content)
        work.refresh_from_db()
        matrix = factory_rfp.inputs(work)['matrix']
        self.assertEqual(matrix[0]['response'], one.row['response'])
        self.assertEqual(matrix[1]['response'], 'SAMPLE second suggestion.')
        self.assertEqual(RFPAnswerReview.objects.count(), 3)
        self.assertEqual([row['review_verdict'] for row in self.client.get(url).json()['rows']], ['undo', 'accept'])
        with self.assertRaises(ValidationError):
            rfp_answers.undo(data['actor'], work.pk, saved[0].pk, work.revision, rev(data['case']))

    def test_replace_keeps_private_reason_and_original_answer_out_of_native_wording(self):
        suggestion = request(self.data)
        answer(suggestion, 'SAMPLE original suggestion not adopted.')
        work = self.data['work']
        self.client.force_login(self.data['actor'])
        url = f'/api/v1/work/{work.pk}/bid-answers'
        current = self.client.get(url).json()
        saved = self.client.post(url, {'action': 'review', 'expected_revision': current['expected_revision'],
            'case_revision': current['case_revision'],
            'decisions': [decision(suggestion, verdict='replace', answer='SAMPLE own answer.',
                disposition='clarification', note='SAMPLE internal rejection explanation.')]}, content_type='application/json')
        self.assertEqual(saved.status_code, 201, saved.content)
        row = self.client.get(url).json()['rows'][0]
        self.assertEqual((row['response'], row['suggested_answer'], row['review_verdict']),
                         ('SAMPLE own answer.', 'SAMPLE original suggestion not adopted.', 'replace'))
        work.refresh_from_db()
        self.assertNotIn('internal rejection', work.source_head.body)
        self.assertNotIn('not adopted', work.source_head.body)
        self.assertEqual(RFPAnswerReview.objects.get().note, 'SAMPLE internal rejection explanation.')
        self.assertEqual(factory_rfp.inputs(work)['matrix'][0]['disposition'], 'clarification')
        endpoint = f'/api/v1/work/{work.pk}/bid-clarifications'
        evidence = self.data['evidence']['requirements']
        current = {'expected_revision': work.revision, 'case_revision': rev(work.case), 'key': 'R1'}
        citation = self.client.post(endpoint, {**current, 'action': 'cite', 'operation_key': str(uuid4()),
            'text': evidence.body, 'page': 1, 'checked': True}, content_type='application/json')
        self.assertEqual(citation.status_code, 201, citation.content)
        self.assertEqual(self.client.get(url).json()['rows'][0]['citation']['page'], 1)
        current['case_revision'] = rev(work.case)
        question = self.client.post(endpoint, {**current, 'action': 'record_question', 'operation_key': str(uuid4()),
            'text': 'Which delivery date applies?', 'observed_at': timezone.now().isoformat(),
            'evidence_id': evidence.pk, 'question_id': None}, content_type='application/json')
        self.assertEqual(question.status_code, 201, question.content)
        current['case_revision'] = rev(work.case)
        reply = self.client.post(endpoint, {**current, 'action': 'record_reply', 'operation_key': str(uuid4()),
            'text': 'The client confirmed the date in the source.', 'observed_at': timezone.now().isoformat(),
            'evidence_id': evidence.pk, 'question_id': question.json()['record_id']}, content_type='application/json')
        self.assertEqual(reply.status_code, 201, reply.content)
        self.assertEqual([item['kind'] for item in self.client.get(endpoint).json()['items']], ['reply', 'question'])
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
        self.assertNotContains(page, 'Requirement source · version')

    def test_http_review_replay_filters_and_retained_replacement_fields(self):
        data = self.data
        suggestion = request(data)
        answer(suggestion)
        self.client.force_login(data['actor'])
        url = reverse('factory_rfp_answers', args=[data['work'].pk])
        page = self.client.get(url + '?status=suggested')
        self.assertContains(page, 'Suggested by Tola')
        self.assertContains(page, 'Requirement source · version')
        self.assertContains(page, data['evidence']['requirements'].body)
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

    def test_next_answer_skips_an_older_unreviewed_suggestion_for_an_accepted_requirement(self):
        data = self.data
        old = request(data)
        answer(old, 'SAMPLE older unreviewed draft.')
        current = request(data)
        answer(current, 'SAMPLE current accepted draft.')
        second = request(data, 'R2')
        answer(second, 'SAMPLE second current draft.')
        self.save([decision(current)])
        data['work'].refresh_from_db()
        self.client.force_login(data['actor'])
        url = reverse('factory_rfp_answers', args=[data['work'].pk])
        values = dict(decision(second), action='review', requirement='R2',
            revision=data['work'].revision, case_revision=rev(data['case']))
        response = self.client.post(url, values)
        self.assertRedirects(response, url + '?requirement=R2')
        self.assertFalse(old.reviews.exists())
        self.assertContains(self.client.get(url), 'Discard your answer edits?')
        reviewed = RFPAnswerReview.objects.get(suggestion=current)
        data['work'].refresh_from_db()
        rfp_answers.undo(data['actor'], data['work'].pk, reviewed.pk,
            data['work'].revision, rev(data['case']))
        replacement = request(data, 'R2')
        answer(replacement, 'SAMPLE newer second draft.')
        data['work'].refresh_from_db()
        values = dict(decision(replacement), action='review', requirement='R2',
            revision=data['work'].revision, case_revision=rev(data['case']))
        self.assertRedirects(self.client.post(url, values), url + '?requirement=R1')

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

    def test_oversized_requirement_is_filtered_in_postgresql_before_provider_context_loading(self):
        from apps.core.services import add_evidence

        data = self.data
        work = data['work']
        large = add_evidence(data['actor'], data['case'].pk, 'requirements', 'S' * 64001,
            'synthetic:oversized-requirement')
        current = factory_rfp.inputs(work)
        payload = {key: current[key] for key in factory_rfp.FIELDS}
        payload['sources'] = dict(payload['sources'], requirements=large.pk)
        payload['matrix'] = [dict(row, evidence_id=large.pk) for row in payload['matrix']]
        factory_rfp.correct(data['actor'], work.pk, work.revision, rev(data['case']), payload,
            'SAMPLE large imported requirement source.')
        with CaptureQueriesContext(connection) as queries, self.assertRaisesMessage(ValidationError, '64,000 bytes'):
            request(data)
        self.assertTrue(any('OCTET_LENGTH' in query['sql'] and '<= 64000' in query['sql'] for query in queries))
        self.assertFalse(RFPAnswerSuggestion.objects.exists())

    def test_current_response_reviewer_can_read_history_without_changing_answers(self):
        from django.contrib.auth import get_user_model
        from apps.policy.services import active_component, register_reference
        from tests.helpers import activate

        data = self.data
        actor, case = data['actor'], data['case']
        reviewer = get_user_model().objects.create_user(username='sample-answer-reviewer')
        for action in ['case.read', 'rfp.read', 'factory.read', 'rfp.review']:
            Grant.objects.create(case=case, user=reviewer, action=action)
        roles = active_component('D05.role_principal_assignments', case)
        reference = register_reference(actor, case.pk, 'synthetic:answer-reviewer', 'schema:psl/role-assignment/v1',
            {'role': 'PMO Lead', 'user_id': reviewer.pk}, data['evidence']['policy_decision'].pk)
        activate(actor, case, 'D05.role_principal_assignments', [*roles.envelope['value'], reference.ref],
            data['evidence']['policy_decision'])
        rfp.assign(actor, case.pk, actor, 'CEO', data['evidence']['policy_decision'].pk,
            'SAMPLE current assignment after reviewer configuration.', rev(case))
        suggestion = request(data)
        answer(suggestion)
        self.save([decision(suggestion, verdict='edit', answer='SAMPLE reviewed change.', note='SAMPLE internal review history.')])
        self.client.force_login(reviewer)
        page = self.client.get(reverse('factory_rfp_answers', args=[data['work'].pk]))
        self.assertContains(page, 'SAMPLE supported answer.')
        self.assertContains(page, 'SAMPLE internal review history.')
        self.assertNotContains(page, 'Undo this answer')
        self.assertNotContains(page, 'Ask Tola for an answer')
        with self.assertRaises(PermissionDenied):
            rfp_answers.writable(reviewer, data['work'])
        Grant.objects.filter(case=case, user=reviewer, action='rfp.review').update(active=False)
        self.assertEqual(self.client.get(reverse('factory_rfp_answers', args=[data['work'].pk])).status_code, 403)


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
