"""Nominee-scoped payroll imports and private working rows."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Exists, Func, JSONField, OuterRef, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone

from adapters.forecast import KEY
from apps.core.evidence_access import public_evidence
from apps.core.models import Audit
from apps.core.read_budget import limit_queries
from apps.core.read_observation import read_observation
from apps.core.views import accessible_case
from apps.finance import payroll as native, payroll_working
from apps.finance.hrfinance_models import HRHandoffRecord
from apps.finance.payroll_forms import commands
from apps.finance.payroll_models import PayrollInput, PayrollPublication, PayrollReportReceipt, PayrollRequest, PayrollRun
from apps.identity.services import active_case_grants, require, visible_cases
from apps.policy.services import active_component, decision_authority
from apps.workflows import factory_payroll
from apps.workflows.factory_definitions import definition
from apps.workflows.factory_payroll_views import recipient_withdrawal
from apps.workflows.factory_views import permitted

from .commands import require_line
from .delivery import PROOF, RESPONSE, proof_rows, recorded
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, Problem, array, choice, endpoint, nullable, obj
from .reviews import VERSIONS
from .work import PAGE, page_number


def workspace(request, case_id):
    case = get_object_or_404(visible_cases(request.user), pk=case_id)
    require(request.user, case, 'payroll.read')
    return case


REQUEST = obj({'id': ID, 'reference': TEXT, 'version': REVISION, 'period': TEXT, 'currency': TEXT, 'providers': array(TEXT, limit=2)})


def request_payload(row):
    return {'id': row.pk, 'reference': row.reference, 'version': row.version,
            **{key: row.metadata[key] for key in ('period', 'currency', 'providers')}}


@endpoint(response=obj({'revision': REVISION, 'items': array(REQUEST, limit=25), 'next_page': nullable(PAGE)}), query={'page': PAGE},
          summary='List current payroll requests and their exact export periods')
def requests(request, case_id):
    case = workspace(request, case_id)
    rows = PayrollRequest.objects.filter(case=case)
    current = rows.exclude(Exists(rows.filter(reference=OuterRef('reference'), version__gt=OuterRef('version'))))
    page = Paginator(current.order_by('-pk'), 25).get_page(page_number(request))
    return {'revision': case.revision, 'items': [request_payload(row) for row in page],
            'next_page': page.next_page_number() if page.has_next() and page.number < PAGE['maximum'] else None}


@endpoint(method='POST', request=obj({'revision': REVISION, 'reference': KEY, 'metadata': native.REQUEST, 'evidence_id': ID}),
          response=obj({'revision': REVISION, 'request': REQUEST}), status=201,
          summary='Record a source-backed restricted payroll request for exactly two providers')
def create_request(request, case_id, *, body):
    case = workspace(request, case_id)
    get_object_or_404(public_evidence(case.evidence.filter(kind='payroll_need')), pk=body['evidence_id'])
    saved = native.request(request.user, case.pk, body['reference'], body['metadata'], body['evidence_id'], body['revision'])
    case.refresh_from_db(fields=['revision'])
    return {'revision': case.revision, 'request': request_payload(saved)}


IMPORT = obj({'id': ID, 'provider': TEXT, 'version': REVISION, 'accepted': BOOLEAN,
              'status': choice('complete', 'held'), 'codes': array(TEXT), 'created_at': DATETIME,
              'replaces_input_id': nullable(ID)})


def import_payload(row):
    return {'id': row.pk, 'provider': row.provider, 'version': row.version, 'created_at': row.created_at,
            'replaces_input_id': row.replaces_input_id,
            **{key: row.metadata[key] for key in ('accepted', 'status', 'codes')}}


@endpoint(response=obj({'revision': REVISION, 'request': REQUEST, 'provider_options': array(obj({
    'provider': TEXT, 'formats': array(choice('json', 'csv', 'xlsx'))}), limit=2),
    'inputs': array(IMPORT, limit=25), 'next_page': nullable(PAGE)}), query={'page': PAGE},
    summary='Read authorised payroll provider import options and status without exposing employee rows')
def imports(request, case_id, request_id):
    actor = request.user
    case = workspace(request, case_id)
    payroll = get_object_or_404(PayrollRequest.objects.filter(case=case).select_related('case'), pk=request_id)
    _, policy = native.access(payroll)
    try:
        native.check_reader(actor, payroll, policy)
        readable = True
    except PermissionDenied:
        readable = False
    available = []
    for entry in policy['providers']:
        if entry['owner_id'] != actor.pk:
            continue
        try:
            require(actor, case, 'payroll.capture')
            decision_authority(actor, case, entry['owner_role'])
        except (PermissionDenied, ValidationError):
            continue
        available.append({'provider': entry['provider'], 'formats': ['json', *[row['format']
                          for row in entry.get('spreadsheet_layouts', [])]]})
    if not (readable or available):
        raise PermissionDenied
    replacements = Audit.objects.filter(case=case, action=native.INPUT_REPLACED,
        data__input=Func(OuterRef('pk'), function='to_jsonb', output_field=JSONField())).order_by('-pk')
    rows = payroll.inputs.defer('payload').annotate(replaces_input_id=Subquery(replacements.values('data__previous')[:1])).order_by('-pk')
    if not readable:
        rows = rows.filter(actor=actor, provider__in=[row['provider'] for row in available])
    page = Paginator(rows, 25).get_page(page_number(request))
    return {'revision': case.revision, 'request': request_payload(payroll), 'provider_options': available,
            'inputs': [import_payload(row) for row in page],
            'next_page': page.next_page_number() if page.has_next() and page.number < PAGE['maximum'] else None}


@endpoint(method='POST', request=obj({'revision': REVISION, 'provider': {**TEXT, 'maxLength': 100}, 'operation_key': KEY,
    'file': {'type': 'string', 'format': 'binary'}, 'source_version': {**TEXT, 'maxLength': 100}, 'extracted_at': DATETIME,
    'completeness': choice('complete', 'partial', 'unknown'), 'control_total': {'type': 'string', 'maxLength': 100},
    'replaces_input_id': ID,
}, optional=('source_version', 'extracted_at', 'completeness', 'control_total', 'replaces_input_id')),
          response=obj({'revision': REVISION, 'input': IMPORT}), status=201, multipart=True,
          summary='Import an original provider JSON, CSV or Excel export as its authorised source owner')
def upload(request, case_id, request_id):
    case = workspace(request, case_id)
    require(request.user, case, 'payroll.capture')
    values = request.POST.copy()
    prior = values.pop('replaces_input_id', [None])[0]
    if prior is not None and (not prior.isascii() or not prior.isdecimal() or len(prior) > 19
                              or not 1 <= int(prior) <= ID['maximum']):
        raise Problem(422, 'invalid_input', 'Choose the exact previous export.')
    values['action'] = 'capture'
    values['request_record'] = str(request_id)
    form = next((item['form'] for item in commands(request.user, case, values, request.FILES) if item['action'] == 'capture'), None)
    if form is None:
        raise PermissionDenied
    if not form.is_valid():
        raise Problem(422, 'invalid_input', 'Check the payroll file and the required extraction details.')
    data = form.cleaned_data
    saved = native.capture(request.user, case.pk, request_id, data['provider'], data['operation_key'],
                          data['body'], data['revision'], spreadsheet=data.get('spreadsheet'),
                          replaces=int(prior) if prior is not None else None)
    saved.replaces_input_id = int(prior) if prior is not None else None
    case.refresh_from_db(fields=['revision'])
    return {'revision': case.revision, 'input': import_payload(saved)}


ROW_STATUS = choice('all', 'ready', 'held')
ROW = obj({'position': REVISION, 'employee': TEXT, 'component': TEXT, 'amount': nullable(TEXT), 'bu': nullable(TEXT),
    'codes': array(TEXT), 'findings': array(TEXT), 'ready': BOOLEAN, 'row_ref': nullable(TEXT), 'data_row': nullable(ID),
    'quarantined': BOOLEAN, 'has_source_amount': BOOLEAN, 'source_amount': nullable(TEXT), 'source_currency': nullable(TEXT),
    'sources': array(obj({'input_id': ID, 'row_ref': TEXT, 'provider': TEXT, 'data_row': nullable(ID)}))})
COUNT = {'type': 'integer', 'minimum': 0}


@endpoint(response=obj({'record_id': ID, 'currency': TEXT, 'period': TEXT, 'status': ROW_STATUS,
    'rows': array(ROW, limit=25), 'total': COUNT, 'ready': COUNT, 'held': COUNT, 'next_page': nullable(PAGE)}),
    query={'page': PAGE, 'status': ROW_STATUS}, path_parameters={'kind': choice('input', 'run')},
    summary='Read a page of exact currently authorised private payroll working rows')
@transaction.atomic
def working_rows(request, case_id, kind, record_id):
    case = workspace(request, case_id)
    require(request.user, case, 'payroll.private.read')
    model = {'input': PayrollInput, 'run': PayrollRun}.get(kind)
    if model is None:
        raise Problem(404, 'not_found', 'This record is unavailable.')
    subject = get_object_or_404(model.objects.defer('payload' if kind == 'input' else 'result')
                               .select_related('request'), request__case=case, pk=record_id)
    value = (native.private_input if kind == 'input' else native.private_run)(request.user, case.pk, subject.pk)
    table = payroll_working.rows(value, kind if kind == 'input' else subject.kind, page=page_number(request),
                                 status=request.GET.get('status', 'all'))
    page = table['page']
    return {'record_id': subject.pk, 'currency': subject.request.metadata['currency'], 'period': subject.request.metadata['period'],
            'rows': list(page), **{key: table[key] for key in ('status', 'total', 'ready', 'held')},
            'next_page': page.next_page_number() if page.has_next() and page.number < PAGE['maximum'] else None}


OPERATIONS = {
    'working': {'stage': choice('combine', 'match', 'aggregate')},
    'receive_hr': {'snapshot_id': ID, 'evidence_id': ID},
    'publish': {},
    'withdraw': {'publication_id': ID, 'evidence_id': ID, 'reason': {**TEXT, 'maxLength': 2000}},
    'successor': {'publication_id': ID, 'request_id': ID, 'inputs': factory_payroll.INPUT, 'reason': {**TEXT, 'maxLength': 2000}},
    'restart': {'request_id': ID, 'inputs': factory_payroll.INPUT, 'configuration_id': ID,
                'instruction_key': KEY, 'reason': {**TEXT, 'maxLength': 2000}},
}


@endpoint(response=obj({**VERSIONS, 'request_id': ID, 'selected': factory_payroll.INPUT, 'stage': TEXT,
    'finding': {'type': 'string'}, 'publication_id': nullable(ID), 'working': array(obj({
        'id': ID, 'kind': choice('combine', 'match', 'aggregate'), 'status': choice('complete', 'held'), 'codes': array(TEXT),
    }), limit=3), 'hr_receipt': nullable(obj({'snapshot_id': ID, 'receipt_id': nullable(ID),
        'can_acknowledge': BOOLEAN, 'proofs': array(PROOF, limit=50)})),
}), summary='Read authorised payroll working references and the assigned matcher’s exact HR receipt options')
@read_observation
def work_options(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, factory_payroll.DEFINITION)
    with limit_queries(1000):
        state = factory_payroll.report(work, actor)
        snapshot_id = state['inputs']['hr_snapshot_id']
        hr_receipt = None
        if snapshot_id:
            matcher = work.execution_actor
            recorded_id = HRHandoffRecord.objects.filter(snapshot_id=snapshot_id, actor=matcher,
                contract__need__case=work.case, kind='receipt').values_list('pk', flat=True).first()
            can_acknowledge = bool(not recorded_id and not work.cancel_requested and actor.pk == matcher.pk
                and (work.case_id, 'hrfinance.receive') in active_case_grants(actor, [work.case_id]))
            proofs = public_evidence(work.case.evidence.filter(kind='hr_disclosure_decision')).only('kind', 'version')
            hr_receipt = {'snapshot_id': snapshot_id, 'receipt_id': recorded_id, 'can_acknowledge': can_acknowledge,
                          'proofs': proof_rows(proofs.order_by('-pk')[:50]) if can_acknowledge else []}
    return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'request_id': state['request'],
            'selected': state['inputs'], 'stage': state['stage'], 'finding': state['finding'],
            'publication_id': state['publication'], 'hr_receipt': hr_receipt,
            'working': [{'id': row['id'], 'kind': kind, 'status': row['status'], 'codes': row['codes']}
                        for kind, row in state['working_runs'].items()]}


@endpoint(method='POST', request={'oneOf': [obj({'action': {'const': action}, **VERSIONS, **fields})
          for action, fields in OPERATIONS.items()]}, response=RESPONSE,
          summary='Apply a native private payroll task, HR receipt or reviewed publication follow-up')
def operate(request, work_id, *, body):
    work = require_line(request.user, work_id, factory_payroll.DEFINITION)
    action = body['action']
    args = (request.user, work.pk, body['expected_revision'], body['case_revision'])
    values = {field: body[field] for field in OPERATIONS[action]}
    if action == 'withdraw':
        row = factory_payroll.withdraw_publication(*args, **values)
    elif action == 'successor':
        row = factory_payroll.prepare_successor(*args, **values)
    elif action == 'restart':
        row = factory_payroll.restart(*args, **values)
    else:
        row = factory_payroll.human_action(*args, action, values)
    return recorded(work, row)


@endpoint(response=obj({'work_id': ID, 'restart': nullable(obj({**VERSIONS, 'request_id': ID,
    'selected': factory_payroll.INPUT, 'configuration_id': ID})), 'previous_receipt': nullable(obj({
        'publication': ID, 'version': REVISION, 'withdrawn_at': DATETIME,
        'receipt_id': nullable(ID), 'received_at': nullable(DATETIME),
    }))}), summary='Read the caller’s prior payroll receipt or the current profile for a fresh preparation instruction')
def recovery(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, factory_payroll.DEFINITION)
    restart = None
    if (work.status == 'cancelled' and work.cancel_requested and permitted(actor, work, 'factory.manage')
            and (work.lease_until is None or work.lease_until <= timezone.now())
            and not factory_payroll.publication_history(work).exists()):
        try:
            payroll, selected = factory_payroll.source(work, actor, False)
            configuration = active_component(definition(work.definition)['component'], work.case)
        except (PermissionDenied, ValidationError):
            pass
        else:
            restart = {'expected_revision': work.revision, 'case_revision': work.case.revision,
                       'request_id': payroll.pk, 'selected': selected['inputs'], 'configuration_id': configuration.pk}
    previous = recipient_withdrawal(actor, work)
    if previous is None and restart is None:
        # Match the exact source boundary used by the Django recovery screen before revealing a protected work ID.
        factory_payroll.source(work, actor, False)
    return {'work_id': work.pk, 'previous_receipt': previous, 'restart': restart}


AGGREGATE = obj({'id': ID, 'version': REVISION, 'period': TEXT, 'entity': TEXT, 'currency': TEXT,
                 'by_business_unit': {'type': 'object', 'additionalProperties': TEXT}, 'eligible_total': TEXT,
                 'receipt_id': nullable(ID), 'can_acknowledge': BOOLEAN, 'revision': REVISION})


@endpoint(response=AGGREGATE, summary='Read a current aggregate payroll report and your own receipt')
@transaction.atomic
def report(request, case_id, publication_id):
    actor = request.user
    case = accessible_case(actor, case_id)
    publication = get_object_or_404(PayrollPublication.objects.defer('payload'), request__case=case, pk=publication_id)
    data = native.observe_publication(actor, publication.pk)
    receipt_id = PayrollReportReceipt.objects.filter(publication=publication, actor=actor).values_list('pk', flat=True).first()
    try:
        native.recipient_access(actor, case, acknowledge=True)
        can_acknowledge = receipt_id is None
    except PermissionDenied:
        can_acknowledge = False
    case.refresh_from_db(fields=['revision'])
    return {'id': publication.pk, 'version': publication.version, 'revision': case.revision,
            **{key: data[key] for key in ('period', 'entity', 'currency', 'eligible_total')},
            'by_business_unit': data['by_bu'], 'receipt_id': receipt_id, 'can_acknowledge': can_acknowledge}


@endpoint(method='POST', request=obj({'revision': REVISION}), response=obj({'receipt_id': ID, 'revision': REVISION}),
          summary='Acknowledge an exact current aggregate report as its named recipient')
def receive_report(request, case_id, publication_id, *, body):
    case = accessible_case(request.user, case_id)
    receipt = native.receive_report(request.user, case.pk, publication_id, body['revision'])
    case.refresh_from_db(fields=['revision'])
    return {'receipt_id': receipt.pk, 'revision': case.revision}
