"""Income schedule source corrections and reviewed adjustment handoffs."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.finance import schedules
from apps.identity.services import active_case_grants
from apps.workflows import factory_schedules as native
from apps.workflows.factory_execution import can_control

from .commands import require_line
from .delivery import PROOF, proof_rows, recorded
from .http import BOOLEAN, ID, TEXT, array, choice, endpoint, nullable, obj
from .reviews import VERSIONS
from .work import WORK_RESULT


RELATIONSHIP = choice(*native.INCOME_RELATIONSHIPS)
ADJUSTMENT = choice('additive', 'reclassification')
TREATMENT = choice('already_represented', 'separately_justified')
REASON = {**TEXT, 'maxLength': 2000}
ROW_KEY = schedules.ROW['properties']['key']
REVIEW = choice('approve', 'return', 'reject', 'revoke')
AMOUNT = nullable({'type': 'string', 'maxLength': 128})
RESULT = obj({'status': choice('ready', 'held'), 'findings': array(TEXT),
              'adjusted_total': AMOUNT, 'parent_amount': AMOUNT, 'additive_total': AMOUNT,
              'reclassification_total': AMOUNT, 'target_unit': nullable(TEXT),
              'coverage': nullable(choice('partial', 'declared_complete')), 'complete_inventory': nullable(BOOLEAN),
              'missing_required': array(ROW_KEY),
              'included_schedules': array(obj({'key': ROW_KEY, 'included': BOOLEAN, 'gaps': array(TEXT)}), limit=100)})
COMMANDS = {
    'resolve_duplicates': {'schedule_id': ID, 'decisions': array(obj({'key': ROW_KEY, 'treatment': TREATMENT}), limit=100),
                           'evidence_id': ID, 'reason': REASON},
    'resubmit_row': {'schedule_id': ID, 'return_id': ID, 'row_key': ROW_KEY, 'relationship': RELATIONSHIP},
    'export_adjustment': {'schedule_id': ID, 'kind': ADJUSTMENT, 'evidence_id': ID},
}


def review_options(actor, schedule, stage, last):
    if schedule is None or stage not in ('output_review', 'withdrawn', 'complete'):
        return []
    try:
        schedules.authority(actor, schedule)
    except (PermissionDenied, ValidationError):
        return []
    if last and last.verdict == 'approve':
        return ['revoke']
    return ['approve'] if stage == 'withdrawn' else ['approve', 'return', 'reject'] if stage == 'output_review' else []


def summary(result):
    keys = ('status', 'adjusted_total', 'parent_amount', 'additive_total', 'reclassification_total', 'target_unit',
            'coverage', 'complete_inventory')
    return {**{key: result.get(key) for key in keys}, 'findings': result['findings'],
            'missing_required': result.get('missing_required', []),
            'included_schedules': [{key: row[key] for key in ('key', 'included', 'gaps')}
                                   for row in result.get('schedules', [])]}


@endpoint(response=obj({**VERSIONS, 'schedule_id': nullable(ID), 'kind': choice('income', 'inventory'), 'stage': TEXT,
    'finding': {'type': 'string'}, 'duplicates': array(ROW_KEY, limit=100),
    'returned': nullable(obj({'review_id': ID, 'rows': array(obj({'key': ROW_KEY, 'relationship': RELATIONSHIP}), limit=100)})),
    'review_id': nullable(ID), 'review_verdicts': array(REVIEW), 'can_export': BOOLEAN,
    'evidence': array(PROOF, limit=35), 'exports': array(obj({'id': ID, 'kind': ADJUSTMENT, 'adjustment_id': ID}), limit=20),
    'income': nullable(schedules.DETAIL), 'inventory': nullable(schedules.INVENTORY_BODY), 'result': nullable(RESULT)}),
    summary='Read the exact schedule, scoped duplicate and returned rows, reviews and adjustment handoffs')
def detail(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    with transaction.atomic(), limit_queries(950):
        grants = {action for _, action in active_case_grants(actor, [work.case_id])}
        can_read = 'schedules.report' in grants
        if can_read:
            work.case = schedules.locked(actor, work.case_id, 'schedules.report')
        current = native.schedule(work)
        facts = native.report(work, actor)
        last = current.reviews.order_by('-pk').first() if current else None
        stage = facts['stage']
        live = not work.cancel_requested and work.status not in ('cancelled', 'followup_needed')
        can_fix = live and can_control(actor, work) and {
            'factory.manage', 'schedules.prepare', 'schedules.report', 'finance.calculate', 'evidence.add',
        } <= grants
        returned = native.returned_income_review(current) if can_fix and stage == 'returned' and actor.pk == work.actor_id else None
        exports = list(current.scheduleadjustment_set.order_by('-pk').values('id', 'kind', 'adjustment_id')[:20]) if current and can_read else []
        proof = public_evidence(work.case.evidence.filter(kind__in=('finance_review', 'finance_adjustment'))).only('id', 'kind', 'version')
        show_current = current and can_read and stage in ('source_correction', 'output_review', 'complete')
        payload = current.payload if show_current else None
        return {'expected_revision': work.revision, 'case_revision': work.case.revision,
                'schedule_id': facts['schedule'], 'kind': facts['kind'], 'stage': stage, 'finding': facts['finding'],
                'duplicates': [row['key'] for row in native.duplicate_rows(current)] if can_fix else [],
                'returned': {'review_id': returned.pk, 'rows': [{'key': row['key'], 'relationship': row['relationship']}
                                                               for row in current.payload['rows']]} if returned else None,
                'review_id': last.pk if last else None, 'review_verdicts': review_options(actor, current, stage, last) if live else [],
                'can_export': stage == 'complete' and facts['kind'] == 'income' and {'schedules.adjust', 'finance.adjust'} <= grants,
                'evidence': proof_rows(proof.order_by('-pk')[:35]) if can_read else [], 'exports': exports,
                'income': payload if facts['kind'] == 'income' else None, 'inventory': payload if facts['kind'] == 'inventory' else None,
                'result': summary(current.result) if show_current else None}


@endpoint(method='POST', request={'oneOf': [obj({'action': {'const': action}, **VERSIONS, **fields})
    for action, fields in COMMANDS.items()]}, response=obj({**WORK_RESULT['properties'], 'record_id': ID}), status=201,
    summary='Correct an exact held or returned row or export a reviewed reporting adjustment')
def command(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    args = (actor, work.pk, body['expected_revision'], body['case_revision'], body['schedule_id'])
    action = body['action']
    if action == 'resolve_duplicates':
        choices = {item['key']: item['treatment'] for item in body['decisions']}
        if len(choices) != len(body['decisions']):
            raise ValidationError('Record each held row exactly once.')
        row = native.resolve_duplicates(*args, choices, body['evidence_id'], body['reason'])
    elif action == 'resubmit_row':
        row = native.resubmit_returned_row(*args, body['return_id'], body['row_key'], body['relationship'])
    else:
        row = native.export(*args, body['kind'], body['evidence_id'])
    return recorded(work, row)
