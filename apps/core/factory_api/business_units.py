"""Private source choices and reviewed aggregate publication."""

import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404

from adapters.bu import EXPORT
from adapters.forecast import KEY
from apps.core.models import Case
from apps.core.read_budget import limit_queries
from apps.finance import bu as domain
from apps.finance.models import BUReceipt, BUWork, FinanceRun, PayrollRun
from apps.identity.services import active_case_grants, require
from apps.workflows import factory_bu as native
from apps.workflows.factory_bu_views import presentation

from .commands import require_line
from .delivery import PROOF, proof_rows, recorded
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj
from .reviews import VERSIONS
from .work import WORK_RESULT


SCOPE = obj({'entity': KEY, 'period': {'type': 'string', 'pattern': r'^\d{4}-(0[1-9]|1[0-2])$'}, 'currency': KEY})
REFERENCE = {'type': 'string', 'pattern': r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$'}
AMOUNT = nullable({'type': 'string', 'maxLength': 128})
TOTALS = {'type': 'object', 'additionalProperties': AMOUNT}
RESULT = obj({'id': ID, 'kind': choice('event', 'staff'), 'status': choice('held', 'complete'),
              'codes': array(TEXT), 'scope': nullable(SCOPE), 'totals': nullable(TOTALS)})
VERSION = obj({'id': ID, 'reference': TEXT, 'version': ID})


def private_case(actor, case_id):
    case = get_object_or_404(Case, pk=case_id)
    for action in ('case.read', 'bu.read', 'bu.private.read'):
        require(actor, case, action)
    return case


@endpoint(response=obj({'case_revision': REVISION, 'payroll': array(obj({'id': ID, 'reference': TEXT}), limit=40),
    'events': array(VERSION, limit=40), 'rules': array(obj({**VERSION['properties'], 'payroll_id': ID}), limit=60),
    'comparisons': array(ID, limit=40)}),
    summary='Read exact private payroll matches and exception rule versions and accepted event sources')
def intake_options(request, case_id):
    actor = request.user
    case = private_case(actor, case_id)
    payroll, rules, events = [], [], []
    with limit_queries(1400):
        for row in PayrollRun.objects.filter(request__case=case, kind='match').select_related('request').defer('result').order_by('-pk')[:40]:
            inputs = {'mode': 'staff', 'payroll_id': row.pk, 'source_id': None, 'rule_ids': [], 'comparison': None}
            try:
                native.inputs_checked(actor, case, inputs)
            except (PermissionDenied, ValidationError):
                continue
            payroll.append({'id': row.pk, 'reference': row.request.reference})
        for row in BUWork.objects.filter(case=case, kind='source', metadata__accepted=True).defer('payload').order_by('-pk')[:40]:
            try:
                domain.private_access(actor, row)
                domain.current(row)
            except (PermissionDenied, ValidationError):
                continue
            events.append({'id': row.pk, 'reference': row.reference, 'version': row.version})
        rule_rows = BUWork.objects.filter(case=case, kind='rule', payroll_id__in=[row['id'] for row in payroll])
        for row in rule_rows.defer('payload').order_by('-pk')[:60]:
            rules.append({'id': row.pk, 'reference': row.reference, 'version': row.version, 'payroll_id': row.payroll_id})
        grants = {action for _, action in active_case_grants(actor, [case.pk])}
        comparisons = FinanceRun.objects.filter(case=case, kind='allocation').order_by('-pk').values_list('pk', flat=True)
        return {'case_revision': case.revision, 'payroll': payroll, 'events': events, 'rules': rules,
                'comparisons': list(comparisons[:40]) if 'finance.calculate' in grants else []}


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'reference': REFERENCE,
    'operation_key': {**TEXT, 'maxLength': 100}, 'scope': SCOPE, 'export': EXPORT}),
    response=obj({**VERSION['properties'], 'accepted': BOOLEAN, 'findings': array(TEXT)}), status=201,
    summary='Capture a bounded private event export under the configured original owner and control totals')
def capture(request, case_id, *, body):
    actor = request.user
    case = private_case(actor, case_id)
    row = domain.capture(actor, case.pk, body['reference'], body['operation_key'], body['scope'],
                         json.dumps(body['export'], ensure_ascii=False, sort_keys=True), body['case_revision'])
    return {'id': row.pk, 'reference': row.reference, 'version': row.version,
            'accepted': row.metadata['accepted'], 'findings': row.metadata['codes']}


SUBJECT = obj({'id': ID, 'kind': choice('source', 'rule', 'event', 'staff'),
               'version': ID, 'purposes': array(choice('source', 'rule', 'event', 'staff', 'historical'))})


@endpoint(response=obj({**VERSIONS, 'stage': TEXT, 'finding': {'type': 'string'}, 'recipient_only': BOOLEAN,
    'inputs': nullable(native.INPUT), 'result': nullable(RESULT), 'publication_id': nullable(ID),
    'receipt_id': nullable(ID), 'receipt_ids': array(ID), 'totals': nullable(TOTALS), 'period': nullable(TEXT),
    'currency': nullable(TEXT), 'review_subjects': array(SUBJECT), 'proofs': array(PROOF, limit=35),
    'can_publish': BOOLEAN, 'can_correct': BOOLEAN, 'verified_at': nullable(DATETIME)}),
    summary='Read current scoped BU input, review or aggregate receipt without exposing private working rows')
def detail(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    with limit_queries(1500):
        panel = presentation(actor, work)['bu']
        if panel.get('restricted'):
            raise PermissionDenied
        common = {'expected_revision': work.revision, 'case_revision': work.case.revision,
                  'publication_id': panel.get('publication')}
        if panel.get('recipient_only'):
            receipt = panel['receipt']
            return {**common, 'stage': 'receipt', 'recipient_only': True, 'receipt_id': receipt.pk if receipt else None,
                    'finding': '', 'inputs': None, 'result': None, 'receipt_ids': [], 'review_subjects': [],
                    'proofs': [], 'can_publish': False, 'can_correct': False,
                    **{key: panel[key] for key in ('totals', 'period', 'currency', 'verified_at')}}
        subjects = []
        if panel.get('can_review'):
            for item in panel.get('subjects', []):
                row = domain.exact(work.case, item['id'])
                allowed = []
                for purpose in [row.kind] + (['historical'] if row.metadata.get('historical') else []):
                    try:
                        domain.authority(actor, row, purpose)
                    except (PermissionDenied, ValidationError):
                        continue
                    allowed.append(purpose)
                if allowed:
                    subjects.append({'id': row.pk, 'kind': row.kind, 'version': row.version, 'purposes': allowed})
        result = panel.get('result')
        totals = scope = None
        if result and result['status'] == 'complete':
            row = native.checked_result(work, actor)
            if row is not None:
                totals, scope = row.payload['by_bu'], row.metadata['scope']
        response = {**result, 'totals': totals, 'scope': scope} if result else None
        receipt_id = BUReceipt.objects.filter(report_id=common['publication_id'], actor=actor).values_list('pk', flat=True).first()
        proofs = work.case.evidence.filter(kind='bu_review').only('id', 'kind', 'version').order_by('-pk')[:35]
        return {**common, 'stage': panel['stage'], 'finding': panel['finding'], 'recipient_only': False,
                'inputs': panel['inputs'], 'result': response, 'receipt_id': receipt_id,
                'receipt_ids': panel.get('receipt_ids', []), 'totals': totals, 'period': scope['period'] if scope else None,
                'currency': scope['currency'] if scope else None, 'review_subjects': subjects,
                'proofs': proof_rows(proofs) if subjects else [], 'can_publish': panel['can_publish'],
                'can_correct': panel['can_correct'], 'verified_at': work.updated_at if panel['stage'] == 'complete' else None}


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': 'prepare_rule'}, **VERSIONS, 'reference': REFERENCE,
         'operation_key': {**TEXT, 'maxLength': 100}, 'payload': domain.RULE}),
    obj({'action': {'const': 'publish'}, **VERSIONS}),
    obj({'action': {'const': 'restart'}, **VERSIONS, 'inputs': native.INPUT, 'configuration_id': ID,
         'instruction_key': {**TEXT, 'maxLength': 100}, 'reason': {**TEXT, 'maxLength': 2000}}),
]}, response=obj({**WORK_RESULT['properties'], 'record_id': ID}), status=201,
    summary='Prepare an exact private payroll exception, publish the reviewed aggregate or restart settled work')
def command(request, work_id, *, body):
    work = require_line(request.user, work_id, native.DEFINITION)
    args = (request.user, work.pk, body['expected_revision'], body['case_revision'])
    action = body['action']
    if action == 'restart':
        row = native.restart(*args, body['inputs'], body['configuration_id'], body['instruction_key'], body['reason'])
    else:
        values = {key: body[key] for key in ('reference', 'operation_key', 'payload')} if action == 'prepare_rule' else {}
        row = native.human_action(*args, action, values)
    return recorded(work, row)
