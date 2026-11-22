"""Source-owned HR disclosure, private Finance receipt and correction commands."""

from time import monotonic

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Func, JSONField, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime

from adapters.forecast import KEY
from apps.agents import hrfinance as investigator
from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.read_observation import read_observation
from apps.core.views import accessible_case
from apps.finance import hr_scope, hrfinance as native
from apps.finance.hrfinance_models import HRDisclosure, HRFinanceNeed, HRHandoffRecord, HRReadSnapshot
from apps.finance.hrfinance_recipient import recipient_scope
from apps.identity.services import active_case_grants, require
from apps.policy.hrfinance_drafts import draft_hrfinance_policy
from apps.policy.hrfinance_validators import DISCLOSURE, EXTENDED_DISCLOSURE_SCHEMA, EXTENDED_FIELDS, MONTH, SCHEMAS
from apps.policy.services import active_component
from apps.workflows.models import HumanTask

from .delivery import PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, Problem, array, choice, endpoint, nullable, obj
from .work import PAGE, page_number


CHECKED = {'type': 'integer', 'minimum': 0}
VERDICT = choice('approve', 'return', 'revoke')
EXPORT_STATUS = choice('accepted', 'rejected')
FIELD = choice(*EXTENDED_FIELDS)
DISPOSITIONS = ('response', 'correction_return', 'correction_reject')
NEED = obj({'id': ID, 'reference': KEY, 'version': REVISION, 'entity': KEY, 'period': MONTH,
            'purpose': KEY, 'fields': array(FIELD, limit=len(EXTENDED_FIELDS))})
DISCLOSURE_ITEM = obj({'id': ID, 'need_id': ID, 'latest_decision': nullable(VERDICT), 'created_at': DATETIME})
HISTORY_DECISION = obj({'id': ID, 'verdict': VERDICT, 'created_at': DATETIME})
SNAPSHOT = obj({'id': ID, 'status': EXPORT_STATUS, 'retain_until': DATETIME, 'findings': array(TEXT),
                'receipt_id': nullable(ID)})
CORRECTION = obj({'id': ID, 'snapshot_id': ID, 'decision': nullable(choice(*DISPOSITIONS)),
                  'successor_id': nullable(ID)})
QUESTION = obj({'task_id': ID, 'revision': REVISION, 'snapshot_id': ID, 'owner_id': ID, 'question': TEXT,
                'status': choice('held', 'cancelled', 'awaiting_owner', 'await_proper_minimal_resubmission'),
                'reason': TEXT, 'can_reply': BOOLEAN, 'can_cancel': BOOLEAN})
PROOF_TYPES = {
    'need': ('hr_finance_need',), 'contract': ('hr_contract_source', 'hr_contract_source_v2'),
    'authorize': ('hr_disclosure_decision',), 'receive': ('hr_disclosure_decision',),
    'correction': ('hr_correction_request',), 'decide_correction': ('hr_correction_response',),
    'bind': ('policy_decision',), 'draft_policy': ('policy_decision',),
}
AUTHORITY = {'authorize': 'authorize', 'capture': 'authorize', 'decide_correction': 'respond', 'receive': 'receive'}
EVIDENCED = {'operation_key': KEY, 'evidence_id': ID}
COMMANDS = {
    'need': {'reference': KEY, 'need': {'oneOf': [native.NEED, native.EXTENDED_NEED]}, 'evidence_id': ID},
    'contract': {'need_id': ID, **EVIDENCED},
    'authorize': {'contract_id': ID, 'verdict': VERDICT, **EVIDENCED},
    'receive': {'snapshot_id': ID, **EVIDENCED},
    'correction': {'snapshot_id': ID, **EVIDENCED},
    'decide_correction': {'request_id': ID, 'verdict': choice('approve', 'return', 'reject'),
                         'successor_id': nullable(ID), **EVIDENCED},
    'scope_request': {'snapshot_id': ID},
    'scope_reply': {'task_id': ID, 'task_revision': REVISION, 'reply': choice(*hr_scope.REPLIES)},
    'scope_cancel': {'task_id': ID, 'task_revision': REVISION},
    'bind': {'snapshot_id': ID, 'evidence_id': ID},
    'investigate': {},
    'draft_policy': {'evidence_id': ID, 'effective_from': DATETIME},
}
POLICIES = [obj({'component': {'const': key}, 'content': shape}) for key, (_, shape) in SCHEMAS.items()]
POLICIES.append(obj({'component': {'const': DISCLOSURE}, 'content': EXTENDED_DISCLOSURE_SCHEMA}))
COMMANDS['draft_policy']['policy'] = {'oneOf': POLICIES}
EXPORT_LIMIT = 256000
GRANTS = {key: 'hrfinance.' + key for key in ('need', 'contract', 'authorize', 'capture', 'receive', 'correction', 'bind')}
GRANTS.update(decide_correction='hrfinance.respond', scope_reply='hrfinance.respond',
              scope_request='agent.hrfinance', scope_cancel='agent.hrfinance', investigate='agent.hrfinance',
              draft_policy='policy.configure')


def workspace(request, case_id):
    case = accessible_case(request.user, case_id, source_action='hrfinance.read')
    require(request.user, case, 'hrfinance.read')
    return case


def admitted_actions(actor, case, grants):
    actions = []
    authorities = {}
    for command, grant in GRANTS.items():
        if grant not in grants:
            continue
        purpose = AUTHORITY.get(command)
        if purpose not in authorities:
            try:
                if purpose:
                    native.authority(actor, case, purpose)
                authorities[purpose] = True
            except (PermissionDenied, ValidationError):
                authorities[purpose] = False
        if authorities[purpose] and (command not in {'bind', 'draft_policy'} or 'policy.configure' in grants):
            actions.append(command)
    if 'contract' in actions:
        try:
            active_component(DISCLOSURE, case)
        except (PermissionDenied, ValidationError):
            actions.remove('contract')
    return actions


def disclosure_payload(disclosure):
    return {'id': disclosure.pk, 'need_id': disclosure.need_id, 'created_at': disclosure.created_at,
            'latest_decision': disclosure.latest_decision}


def disclosures_for(case):
    decision = HRHandoffRecord.objects.filter(contract_id=OuterRef('pk'), kind__in=VERDICT['enum']).order_by('-pk')
    return HRDisclosure.objects.filter(need__case=case).annotate(latest_decision=Subquery(decision.values('kind')[:1]))


@endpoint(response=obj({'revision': REVISION, 'needs': array(NEED, limit=25),
    'disclosures': array(DISCLOSURE_ITEM, limit=25), 'actions': array(choice(*GRANTS)),
    'proofs': obj({key: array(PROOF, limit=25) for key in PROOF_TYPES}), 'next_page': nullable(PAGE)}),
    query={'page': PAGE}, summary='List the current HR and Finance disclosure records and authorised evidence choices')
def options(request, case_id):
    actor = request.user
    case = workspace(request, case_id)
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    actions = admitted_actions(actor, case, grants)
    number = page_number(request)
    offset = (number - 1) * 25
    rows = HRFinanceNeed.objects.filter(case=case)
    latest = rows.filter(reference=OuterRef('reference')).order_by('-version').values('pk')[:1]
    needs = list(rows.filter(pk=Subquery(latest)).order_by('-pk')[offset:offset + 26])
    disclosures = list(disclosures_for(case).defer('payload', 'policy_ids').order_by('-pk')[offset:offset + 26])
    return {'revision': case.revision, 'actions': actions,
            'needs': [{'id': row.pk, 'reference': row.reference, 'version': row.version,
                       **{k: row.payload[k] for k in ('entity', 'period', 'purpose', 'fields')}} for row in needs[:25]],
            'disclosures': [disclosure_payload(row) for row in disclosures[:25]],
            'proofs': {key: proof_rows(public_evidence(case.evidence.filter(kind__in=kinds)).only('kind', 'version')
                                      .order_by('-pk')[:25]) if key in actions else []
                       for key, kinds in PROOF_TYPES.items()},
            'next_page': number + 1 if number < PAGE['maximum'] and max(len(needs), len(disclosures)) > 25 else None}


@endpoint(response=obj({'revision': REVISION, 'disclosure': DISCLOSURE_ITEM, 'current_approval_id': nullable(ID),
    'fields': array(FIELD, limit=len(EXTENDED_FIELDS)), 'entity': KEY, 'period': MONTH,
    'decisions': array(HISTORY_DECISION, limit=25),
    'snapshots': array(SNAPSHOT, limit=25), 'corrections': array(CORRECTION, limit=25),
    'questions': array(QUESTION, limit=10)}), summary='Read an exact disclosure, its export receipts and private correction status')
@read_observation
def detail(request, case_id, contract_id):
    actor = request.user
    case = workspace(request, case_id)
    disclosure = get_object_or_404(disclosures_for(case).select_related('need__case'), pk=contract_id)
    try:
        approval = native.authorized(disclosure).pk
    except (PermissionDenied, ValidationError):
        approval = None
    receipt = disclosure.records.filter(snapshot_id=OuterRef('pk'), actor=actor, kind='receipt').values('pk')[:1]
    snapshots = disclosure.snapshots.defer('payload').annotate(receipt_id=Subquery(receipt)).order_by('-pk')[:25]
    decisions = disclosure.records.filter(kind__in=VERDICT['enum']).values('pk', 'kind', 'created_at').order_by('-pk')[:25]
    corrections = []
    try:
        hr_scope.owner_access(actor, case)
        reviews = disclosure.records.filter(kind='correction')
    except (PermissionDenied, ValidationError):
        reviews = disclosure.records.filter(kind='correction', actor=actor)
    decision = disclosure.records.filter(kind__in=DISPOSITIONS,
        payload__request_id=Func(OuterRef('pk'), function='to_jsonb', output_field=JSONField())).order_by('-pk')
    for row in reviews.annotate(decision_kind=Subquery(decision.values('kind')[:1]),
                                  successor_id=Subquery(decision.values('snapshot_id')[:1])).order_by('-pk')[:25]:
        corrections.append({'id': row.pk, 'snapshot_id': row.snapshot_id, 'decision': row.decision_kind,
                            'successor_id': row.successor_id if row.decision_kind == 'response' else None})
    tasks = HumanTask.objects.filter(Q(claimed_by=actor) | Q(created_by=actor), case=case,
        context__purpose=hr_scope.PURPOSE, context__contract_id=disclosure.pk).select_related('case', 'created_by').order_by('-pk')[:10]
    with limit_queries(650, deadline=monotonic() + 8):
        questions = [question_payload(actor, task) for task in tasks]
    return {'revision': case.revision, 'disclosure': disclosure_payload(disclosure), 'current_approval_id': approval,
            **{key: disclosure.payload[key] for key in ('fields', 'entity', 'period')},
            'decisions': [{'id': row['pk'], 'verdict': row['kind'], 'created_at': row['created_at']} for row in decisions],
            'snapshots': [{'id': row.pk, 'status': row.status, 'retain_until': row.retain_until,
                           'findings': row.manifest['findings'], 'receipt_id': row.receipt_id} for row in snapshots],
            'corrections': corrections, 'questions': questions}


def question_payload(actor, task):
    can_cancel = (task.status == 'open' and task.created_by_id == actor.pk
                  and (task.case_id, 'agent.hrfinance') in active_case_grants(actor, [task.case_id]))
    return {**hr_scope.projection(actor, task), 'can_cancel': can_cancel}


@endpoint(response=QUESTION, summary='Read the exact internal wording and reply status for an assigned HR clarification')
def scope_question(request, case_id, task_id):
    case = workspace(request, case_id)
    task = get_object_or_404(HumanTask.objects.select_related('case', 'created_by'), case=case,
                             context__purpose=hr_scope.PURPOSE, pk=task_id)
    if request.user.pk not in {task.created_by_id, task.claimed_by_id}:
        raise PermissionDenied
    return question_payload(request.user, task)


@endpoint(response=obj({'snapshot_id': ID, 'entity': KEY, 'period': MONTH, 'as_of': TEXT,
    'completeness': choice('complete', 'partial', 'unknown'), 'total': CHECKED,
    'fields': array(FIELD, limit=len(EXTENDED_FIELDS)), 'rows': array(obj(
        {key: nullable(TEXT) for key in EXTENDED_FIELDS}, optional=set(EXTENDED_FIELDS) - set(('employee_id', 'bu', 'effective_from', 'effective_until'))),
        limit=25), 'next_page': nullable(PAGE)}), query={'page': PAGE},
    summary='Read a page of the exact private HR export as its named Finance recipient')
def snapshot_rows(request, case_id, snapshot_id):
    case = accessible_case(request.user, case_id, source_action='hrfinance.read')
    snapshot = get_object_or_404(HRReadSnapshot.objects.defer('payload').select_related('contract__need__case'),
                                 contract__need__case=case, pk=snapshot_id)
    try:
        with recipient_scope(request.user, case, snapshot.contract.payload['recipient_ids']):
            data = native.read_snapshot(request.user, snapshot)
    except ValidationError as exc:
        raise Problem(409, 'disclosure_held', 'Current HR authority, retention or source freshness requires reassessment.') from exc
    page = Paginator(data['rows'], 25).get_page(page_number(request))
    return {'snapshot_id': snapshot.pk, 'fields': snapshot.contract.payload['fields'], 'total': len(data['rows']),
            **{key: data[key] for key in ('entity', 'period', 'as_of', 'completeness')}, 'rows': list(page),
            'next_page': page.next_page_number() if page.has_next() else None}


@endpoint(method='POST', request=obj({'revision': REVISION, 'operation_key': KEY,
    'file': {'type': 'string', 'format': 'binary', 'description': 'Original UTF-8 JSON export, up to 256000 bytes.'}}),
    multipart=True, response=obj({'revision': REVISION, 'snapshot_id': ID, 'status': EXPORT_STATUS,
                                   'findings': array(TEXT)}), status=201,
    summary='Capture an original private HR export under its exact active disclosure')
def capture(request, case_id, contract_id):
    actor = request.user
    case = workspace(request, case_id)
    require(actor, case, 'hrfinance.capture')
    revision = request.POST['revision']
    key = request.POST['operation_key']
    if not revision.isascii() or not revision.isdecimal() or len(revision) > 10 or not 1 <= int(revision) <= REVISION['maximum']:
        raise Problem(422, 'invalid_input', 'Use the exact current workspace revision.')
    file = request.FILES['file']
    if file.size > EXPORT_LIMIT:
        raise Problem(413, 'request_too_large', 'The private export exceeds the supplied export size limit.')
    try:
        export = file.read(EXPORT_LIMIT + 1).decode('utf-8')
    except UnicodeDecodeError as exc:
        raise Problem(422, 'invalid_export', 'Choose a UTF-8 JSON export.') from exc
    try:
        record = native.capture(actor, case.pk, contract_id, key, export, int(revision))
    except ValidationError as exc:
        if exc.messages[0].startswith('Stale revision'):
            raise
        raise Problem(422, 'export_held', 'Check the current disclosure approval and original export.') from exc
    case.refresh_from_db(fields=['revision'])
    return {'revision': case.revision, 'snapshot_id': record.pk, 'status': record.status, 'findings': record.manifest['findings']}


@endpoint(method='POST', request={'oneOf': [obj({'action': {'const': action}, 'revision': REVISION, **fields})
    for action, fields in COMMANDS.items()]}, response=obj({'revision': REVISION, 'record_id': nullable(ID),
        'configuration_ids': array(ID)}),
    summary='Record a typed HR human decision, Finance receipt or private follow-up')
def operate(request, case_id, *, body):
    actor = request.user
    action = body['action']
    if action == 'receive':
        case = accessible_case(actor, case_id, source_action='hrfinance.read')
    else:
        case = workspace(request, case_id)
        require(actor, case, GRANTS[action])
    if action in PROOF_TYPES:
        get_object_or_404(public_evidence(case.evidence.filter(kind__in=PROOF_TYPES[action])), pk=body['evidence_id'])
    revision = body['revision']
    args = (actor, case.pk)
    key = body.get('operation_key')
    evidence = body.get('evidence_id')
    record = None
    configurations = []
    if action == 'need':
        record = native.need(*args, body['reference'], body['need'], evidence, revision)
    elif action == 'contract':
        record = native.contract(*args, body['need_id'], key, evidence, revision)
    elif action == 'authorize':
        record = native.decide(*args, body['contract_id'], body['verdict'], key, evidence, revision)
    elif action in {'receive', 'correction'}:
        service = native.receive if action == 'receive' else native.correction
        record = service(*args, body['snapshot_id'], key, evidence, revision)
    elif action == 'decide_correction':
        record = native.decide_correction(*args, body['request_id'], body['verdict'], body['successor_id'], key, evidence, revision)
    elif action == 'scope_request':
        record = hr_scope.request(*args, body['snapshot_id'], revision)
    elif action == 'scope_reply':
        hr_scope.respond(*args, body['task_id'], body['task_revision'], body['reply'], revision)
        record = HumanTask.objects.only('pk').get(pk=body['task_id'], case=case)
    elif action == 'scope_cancel':
        record = hr_scope.cancel(*args, body['task_id'], body['task_revision'], revision)
    elif action == 'bind':
        configurations = [draft.pk for draft in native.draft_basis(*args, body['snapshot_id'], evidence, revision)]
    elif action == 'draft_policy':
        with transaction.atomic():
            native.locked(*args, 'policy.configure', revision)
            policy = body['policy']
            record = draft_hrfinance_policy(*args, policy['component'], policy['content'], evidence,
                                            parse_datetime(body['effective_from']))
    else:
        record = investigator.investigate(*args, revision)
    case.refresh_from_db(fields=['revision'])
    return {'revision': case.revision, 'record_id': record.pk if record else None, 'configuration_ids': configurations}
