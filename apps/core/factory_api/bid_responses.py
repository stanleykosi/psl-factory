"""Requirement answers and the actual submitted-bid outcome handoff."""

from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404

from apps.agents.rfp_answer_models import RFPAnswerReview, RFPAnswerSuggestion
from apps.core.evidence_access import public_evidence, restricted
from apps.core.read_budget import limit_queries
from apps.core.views import accessible_case
from apps.identity.services import active_case_grants, require
from apps.pmo import rfp, rfp_answers, rfp_outcomes, rfp_pricing, winning_answers
from apps.pmo.models import RFPCase, RFPDisposition, RFPOutcome, RFPSubmission
from apps.workflows import factory_rfp as native

from .commands import require_line
from .delivery import PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, array, choice, endpoint, nullable, obj
from .reviews import VERSIONS
from .work import WORK_RESULT, result


KEY = {**TEXT, 'maxLength': 100}
PROSE = {'type': 'string', 'maxLength': 4000}
DISPOSITION = choice('addressed', 'clarification', 'out_of_scope')
ANSWER_REVIEW = choice('accept', 'edit', 'replace', 'undo')
ROW = obj({'key': KEY, 'evidence_id': nullable(ID), 'response': nullable(PROSE), 'disposition': DISPOSITION,
           'status': choice('current', 'queued', 'running', 'held', 'suggested', 'reviewed', 'stale'),
           'suggestion_id': nullable(ID), 'suggested_answer': nullable(PROSE), 'review_id': nullable(ID),
           'review_verdict': nullable(ANSWER_REVIEW), 'can_review': BOOLEAN, 'can_undo': BOOLEAN})
PRIOR = obj({'token': TEXT, 'label': TEXT})
TEAM = choice(*rfp.TEAMS)
DAYS = {'type': 'string', 'pattern': r'^\d{1,9}(\.\d{1,3})?$'}
TEAM_INPUT = obj({'id': ID, 'intake_id': ID, 'team': TEAM, 'evidence_id': ID,
    'received_at': nullable(DATETIME), 'source_party': nullable({'type': 'string'}), 'summary': nullable({'type': 'string'}),
    'person_days': nullable(DAYS)})


def team_input(row):
    return {**{key: getattr(row, key) for key in ('id', 'intake_id', 'team', 'evidence_id',
                                                 'received_at', 'source_party', 'summary')},
            'person_days': str(row.person_days) if row.person_days is not None else None}


def team_case(actor, case_id):
    case = accessible_case(actor, case_id, source_action='rfp.read')
    require(actor, case, 'rfp.read')
    return case


@endpoint(response=obj({'revision': REVISION, 'intake_id': ID, 'items': array(TEAM_INPUT, limit=4),
    'choices': array(obj({'team': TEAM, 'proofs': array(PROOF, limit=40)}), limit=4)}),
    summary='Read the current bid team inputs and allowed original proofs')
def team_inputs(request, case_id):
    actor = request.user
    case = team_case(actor, case_id)
    bid = get_object_or_404(RFPCase.objects.select_related('current_intake'), case=case, current_intake__isnull=False)
    current = bid.current_intake
    rows = (current.contributions.filter(team__in=rfp.TEAMS).select_related('evidence')
            .defer('evidence__body').order_by('team', '-pk').distinct('team'))
    actions = active_case_grants(actor, [case.pk])
    proofs = public_evidence(case.evidence.all()).only('kind', 'version').order_by('-pk')
    return {'revision': case.revision, 'intake_id': current.pk,
            'items': [team_input(row) for row in rows if not restricted(row.evidence)],
            'choices': [{'team': team, 'proofs': proof_rows(proofs.filter(kind=kind)[:40])}
                        for team, kind in rfp.TEAMS.items() if (case.pk, f'rfp.contribute:{team}') in actions]}


@endpoint(method='POST', request=obj({'revision': REVISION, 'team': TEAM, 'evidence_id': ID, 'received_at': DATETIME,
    'source_party': {**TEXT, 'maxLength': 160}, 'summary': {**TEXT, 'maxLength': 4000},
    'person_days': nullable(DAYS), 'attested': BOOLEAN}), response=TEAM_INPUT, status=201,
    summary='Record actual named-team evidence, time and exact known or unknown person-days')
def record_team_input(request, case_id, *, body):
    actor = request.user
    case = team_case(actor, case_id)
    facts = {key: body[key] for key in ('source_party', 'summary', 'person_days', 'attested')}
    row = rfp.record_team_input(actor, case.pk, body['team'], body['evidence_id'], body['revision'],
                                received_at=datetime.fromisoformat(body['received_at']), **facts)
    row.refresh_from_db(fields=['person_days'])
    return team_input(row)


def answer_row(actor, work, row, suggestion, anchors, writable, readable_source):
    available = anchors is not None and readable_source
    base = {'key': row['key'], 'disposition': row['disposition'], 'evidence_id': row['evidence_id'] if available else None,
            'response': row['response'] if available else None, 'status': 'current' if available else 'stale',
            'suggestion_id': None, 'suggested_answer': None, 'review_id': None, 'review_verdict': None,
            'can_review': False, 'can_undo': False}
    if not available or not suggestion:
        return base
    original = {key: value for key, value in suggestion.context.items() if key != 'prior_answer'}
    if anchors != original or suggestion.row['evidence_id'] != row['evidence_id']:
        return dict(base, status='stale')
    if 'prior_answer' in suggestion.context:
        try:
            winning_answers.read(actor, work.case, suggestion.context['prior_answer'])
        except (ValidationError, PermissionDenied):
            return dict(base, status='stale')
    review = suggestion.last_review
    entry = {'suggestion_id': suggestion.pk, 'review_id': review.pk if review else None,
             'review_verdict': review.verdict if review else None, 'suggested_answer': suggestion.turn.answer or None}
    if review and review.verdict != 'undo':
        return {**base, **entry, 'status': 'reviewed', 'can_undo': writable and row == review.row}
    if row != suggestion.row:
        return dict(base, status='stale')
    status = 'suggested' if suggestion.turn.status == 'answered' else suggestion.turn.status
    return {**base, **entry, 'status': status,
            'can_review': writable and status == 'suggested' and bool(suggestion.turn.sources)}


@endpoint(response=obj({**VERSIONS, 'can_write': BOOLEAN, 'rows': array(ROW, limit=100),
                        'prior_options': array(PRIOR, limit=100)}),
          summary='Read current requirement answers, authorised suggestions and reusable reviewed winning precedents')
def answers(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    with limit_queries(1400):
        anchors, writable = rfp_answers.read_state(actor, work)
        rows = native.inputs(work)['matrix']
        latest_review = RFPAnswerReview.objects.filter(suggestion_id=OuterRef('pk')).order_by('-pk').values('pk')[:1]
        suggestions = {item.key: item for item in RFPAnswerSuggestion.objects.filter(work=work,
            key__in=[row['key'] for row in rows]).select_related('turn').order_by('key', '-pk').distinct('key')
            .annotate(last_review_id=Subquery(latest_review))}
        reviews = RFPAnswerReview.objects.in_bulk({item.last_review_id for item in suggestions.values() if item.last_review_id})
        for item in suggestions.values():
            item.last_review = reviews.get(item.last_review_id)
        source_access = {}
        if anchors is not None:
            for row in rows:
                pk = row['evidence_id']
                if pk in source_access:
                    continue
                try:
                    rfp_answers.source_for(actor, work, row)
                except (PermissionDenied, ValidationError):
                    source_access[pk] = False
                else:
                    source_access[pk] = True
        options = winning_answers.options(actor, work.case)[:100] if writable else []
        return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'can_write': writable,
                'rows': [answer_row(actor, work, row, suggestions.get(row['key']), anchors,
                                   writable, source_access.get(row['evidence_id'], False)) for row in rows],
                'prior_options': [{'token': token, 'label': facts['label']} for token, _, facts in options]}


ENTRY = obj({'suggestion': ID, 'predecessor': {'type': 'integer', 'minimum': 0}, 'verdict': choice('accept', 'edit', 'replace'),
             'answer': PROSE, 'disposition': DISPOSITION, 'note': {'type': 'string', 'maxLength': 2000}})


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': 'suggest'}, **VERSIONS, 'key': KEY, 'operation_key': UUID,
         'prior_answer': {**TEXT, 'maxLength': 512}}, optional=('prior_answer',)),
    obj({'action': {'const': 'review'}, **VERSIONS, 'decisions': array(ENTRY, limit=100)}),
    obj({'action': {'const': 'undo'}, **VERSIONS, 'review_id': ID}),
]}, response=obj({**WORK_RESULT['properties'], 'record_ids': array(ID, limit=100)}), status=201,
    summary='Request a source-owned answer, review selected suggestions or restore the previous answer')
def answer_command(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    expected, case = body['expected_revision'], body['case_revision']
    if body['action'] == 'suggest':
        row = rfp_answers.request(actor, work.pk, body['key'], body['operation_key'], expected, case,
                                  prior_choice=body.get('prior_answer', ''))
        ids = [row.pk]
    elif body['action'] == 'review':
        ids = [item.pk for item in rfp_answers.review(actor, work.pk, expected, case, body['decisions'])]
    else:
        row = rfp_answers.undo(actor, work.pk, body['review_id'], expected, case)
        ids = [row.pk]
    work.refresh_from_db()
    return {**result(work), 'record_ids': ids}


SUBMISSION = obj({'id': ID, 'version_id': ID, 'response_id': ID, 'submitted_at': DATETIME, 'late': BOOLEAN,
                  'receipt_ids': array(ID)})
OUTCOME = obj({'id': ID, 'submission_id': ID, 'result': choice('won', 'lost', 'pending', 'unknown'),
               'observed_at': DATETIME, 'award_amount': nullable(TEXT), 'award_currency': nullable(TEXT),
               'customer_expected_on': nullable({'type': 'string', 'format': 'date'}),
               'followup_on': nullable({'type': 'string', 'format': 'date'}), 'remind_at': nullable(DATETIME),
               'comparison': nullable(obj({'finding': TEXT, 'quote_amount': nullable(TEXT), 'quote_currency': nullable(TEXT),
                                          'quote_basis': nullable(TEXT), 'award_basis': nullable(TEXT)}))})


@endpoint(response=obj({**VERSIONS, 'submissions': array(SUBMISSION, limit=100), 'submission_count': {'type': 'integer'},
    'selection_required': BOOLEAN, 'selection_packet': TEXT, 'selection_policy_id': nullable(ID),
    'selection_finding': {'type': 'string'}, 'outcome': nullable(OUTCOME),
    'handoff': nullable(obj({'id': ID, 'outcome_id': ID, 'kind': choice('route_a', 'loss_archive'),
                             'baseline_imported': {'const': False}}))}), query={'submission_id': ID},
    summary='Read original submissions, exact award comparison and verified conversion or loss disposition')
def outcomes(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    require(actor, work.case, 'rfp.read')
    root = native.subject(work)
    raw = request.GET.get('submission_id')
    with limit_queries(1200):
        selection = rfp_outcomes.outcome_selection_state(work.case)
        history = RFPSubmission.objects.filter(response__rfp=root).order_by('-pk')
        matching = RFPOutcome.objects.filter(submission__response__rfp=root)
        if raw:
            if not raw.isascii() or not raw.isdecimal() or len(raw) > 19 or not 1 <= int(raw) <= ID['maximum']:
                raise ValidationError('Choose the exact original submission.')
            selected = get_object_or_404(history, pk=int(raw))
            matching = matching.filter(submission=selected)
        current = matching.select_related('evidence', 'submission__response', 'submission__version').order_by('-pk').first()
        outcome = None
        if current:
            comparison = rfp_pricing.comparison(work.case, current)
            quote = comparison.get('quote', {}) if comparison else {}
            outcome = {'id': current.pk, 'submission_id': current.submission_id, 'result': current.result,
                       'observed_at': current.observed_at, 'award_amount': current.award_amount,
                       'customer_expected_on': current.customer_expected_on, 'followup_on': current.followup_on,
                       'remind_at': current.remind_at,
                       'award_currency': current.award_currency or None, 'comparison': {
                           'finding': comparison['finding'], 'quote_amount': quote.get('amount'),
                           'quote_currency': quote.get('currency'), 'quote_basis': quote.get('basis'),
                           'award_basis': comparison.get('award_basis')} if comparison else None}
        handoff = RFPDisposition.objects.filter(rfp=root).first()
        if work.status == 'verified' and handoff is not None:
            try:
                native.verify(work)
            except (PermissionDenied, ValidationError):
                handoff = None
        else:
            handoff = None
        return {'expected_revision': work.revision, 'case_revision': work.case.revision,
                'submissions': [{'id': row.pk, 'version_id': row.version_id, 'response_id': row.response_id,
                                 'submitted_at': row.submitted_at, 'late': row.late, 'receipt_ids': row.receipt_ids}
                                for row in history[:100]],
                'submission_count': selection['inventory']['coverage']['submissions']['count'],
                'selection_required': selection['required'], 'selection_packet': selection['packet'],
                'selection_policy_id': selection['configuration'], 'selection_finding': selection['finding'],
                'outcome': outcome, 'handoff': {'id': handoff.pk, 'outcome_id': handoff.outcome_id,
                                             'kind': handoff.kind, 'baseline_imported': False} if handoff else None}
