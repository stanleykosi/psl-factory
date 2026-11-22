"""Source-bound forecast review, actuals and disclosure decisions."""

from datetime import date, datetime
from io import BytesIO

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from adapters import case_uploads
from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.read_observation import read_observation
from apps.core.models import Evidence
from apps.documents.models import Version
from apps.finance import forecast as domain, forecast_actuals, group_disclosure_forms
from apps.finance.models import CashVerification, ForecastActual, ForecastItemSupport, ForecastMatch
from apps.identity.services import require
from apps.policy.document_validators import ROLES
from apps.policy.group_forecast_validators import FIELDS, METADATA
from apps.policy.services import active_component, reference_values
from apps.workflows import factory_forecast as native, factory_forecast_recovery as recovery
from apps.workflows.factory_progress import wake_waiting
from apps.workflows.models import FactoryWork

from .commands import require_line
from .delivery import NOTE, PROOF, proof_rows, recorded
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj
from .intake import STARTS, progress_result
from .reviews import VERSIONS
from .work import WORK_RESULT, result


ROLE = choice(*ROLES)
VERDICT = choice('approve', 'return', 'reject')
DATE = {'type': 'string', 'format': 'date'}
PERIOD = {'type': 'string', 'pattern': r'^\d{4}-(0[1-9]|1[0-2])$'}
FILE = {'type': 'string', 'format': 'binary'}
KEY = {**TEXT, 'maxLength': 100}
AMOUNT = {'type': 'string', 'maxLength': 128}
ACTUAL = obj({'id': ID, 'direction': choice('inflow', 'outflow'), 'amount': nullable(AMOUNT),
              'verified': BOOLEAN, 'unmatched': nullable(AMOUNT)})
MONTH = obj({'month': TEXT, **{key: nullable(AMOUNT) for key in ('opening', 'inflow', 'outflow', 'closing',
    'expected_inflow', 'expected_outflow', 'actual_inflow', 'actual_outflow')}})
ITEM = obj({'key': KEY, 'kind': TEXT, 'expected_on': nullable(DATE), 'matched': nullable(AMOUNT),
            'residual': nullable(AMOUNT), 'evidence_id': ID})
RESULT = obj({'status': TEXT, 'entity': TEXT, 'currency': TEXT, 'basis': TEXT, 'as_of': DATE, 'findings': array(TEXT),
              'items': array(ITEM, limit=2000), 'periods': array(MONTH, limit=120), 'actuals': array(ACTUAL, limit=200)})
JOB = obj({'id': ID, 'status': TEXT, 'receipt_ids': array(ID), 'can_retry': BOOLEAN, 'can_operate': BOOLEAN})
DISCLOSURE = obj({'configuration_id': ID, 'row_keys': array(KEY), 'recipient_ids': array(ID, limit=100),
                  'oracle_choices': array(PROOF, limit=35), 'decision_choices': array(PROOF, limit=35),
                  'selected_rows': array(KEY), 'selected_fields': array(choice(*FIELDS)),
                  'selected_metadata': array(choice(*METADATA))})


def read_result(result):
    keys = ('status', 'entity', 'currency', 'basis', 'as_of', 'findings', 'periods')
    return {**{key: result[key] for key in keys}, 'actuals': result['actuals'][-200:],
            'items': [{key: row[key] for key in ('key', 'kind', 'expected_on', 'matched', 'residual', 'evidence_id')}
                      for row in result['items']]}


def disclosure_options(actor, work, run):
    if run is None:
        return None
    try:
        require(actor, work.case, 'policy.configure')
        domain.approved(run)
        config = active_component('D10.audience_projection_rules', work.case)
    except (PermissionDenied, ValidationError):
        return None
    group = reference_values(config)[0].get('group', {})
    if group.get('run_id') != run.pk or group.get('run_hash') != run.sha256:
        group = {}
    evidence = work.case.evidence.only('id', 'version', 'kind').order_by('-pk')
    recipients = get_user_model().objects.filter(is_active=True, grant__case=work.case,
        grant__active=True, grant__action='document.receive:group').distinct().order_by('pk')
    return {'configuration_id': config.pk, 'row_keys': [row['key'] for row in run.result['items']],
            'recipient_ids': list(recipients.values_list('id', flat=True)[:100]),
            'oracle_choices': proof_rows(evidence.filter(kind='forecast_group_oracle')[:35]),
            'decision_choices': proof_rows(public_evidence(evidence.filter(kind='policy_decision'))[:35]),
            'selected_rows': group.get('rows', []), 'selected_fields': group.get('fields', []),
            'selected_metadata': group.get('metadata', [])}


@endpoint(response=obj({**VERSIONS, 'scenario_id': ID, 'run_id': nullable(ID), 'version_id': nullable(ID),
    'stage': TEXT, 'finding': {'type': 'string'}, 'review_roles': array(ROLE), 'audience': choice('internal', 'management', 'group'),
    'result': nullable(RESULT), 'jobs': array(JOB, limit=30), 'disclosure': nullable(DISCLOSURE),
    'can_restart': BOOLEAN, 'restart_policy_id': nullable(ID),
    'observation': nullable(obj({'id': ID, 'outcome': choice(*recovery.OUTCOMES), 'has_proof': BOOLEAN})),
    'matches': array(obj({'id': ID, 'item_key': TEXT, 'actual_id': ID, 'amount': AMOUNT}), limit=100)}),
    summary='Read the exact forecast calculation, actual links, group state and original delivery receipt references')
@read_observation
def detail(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    with limit_queries(1400):
        row = native.projection(actor, work)
        run, scenario = row['run'], row['scenario']
        stage = row['status']['stage']
        result = read_result(run.result) if run and row['intake_current'] and stage not in ('source', 'rework') else None
        matches = domain.active_matches().filter(case=work.case, root=domain.root_of(scenario)).order_by('-pk')[:100]
        observation = recovery.observations(work).filter(actor=actor, data__source=work.source_head_id).order_by('-pk').first()
        return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'scenario_id': scenario.pk,
                'run_id': run.pk if run else None, 'stage': stage, 'finding': row['finding'] or row['status']['finding'],
                'audience': row['selection']['audience'], 'result': result, 'review_roles': row['review_roles'],
                'disclosure': disclosure_options(actor, work, run) if result and row['selection']['audience'] == 'group' else None,
                'can_restart': row['can_restart'], 'restart_policy_id': row['restart_policy'] if row['can_restart'] else None,
                'observation': {'id': observation.pk, 'outcome': observation.data['outcome'],
                                'has_proof': bool(observation.data['proof'])} if observation else None,
                'version_id': row['document'].version_id if row['document'] else None,
                'jobs': [{'id': job.pk, 'status': job.status, 'receipt_ids': [item.pk for item in job.receipts],
                          'can_retry': job.can_retry, 'can_operate': job.can_operate} for job in row['jobs'][:30]],
                'matches': [{'id': item.pk, 'item_key': item.item_key, 'actual_id': item.actual_id, 'amount': item.amount}
                            for item in matches] if row['intake_current'] else []}


HUMAN_ACTIONS = {
    'review': {'run_id': ID, 'role': ROLE, 'verdict': VERDICT, 'evidence_id': ID, 'reason': NOTE},
    'priority': {'run_id': ID, 'role': ROLE, 'reference': {**TEXT, 'maxLength': 160},
                 'description': {**TEXT, 'maxLength': 1000}, 'owner_id': ID, 'due_at': DATETIME,
                 'evidence_id': ID, 'reason': NOTE},
    'support': {'item_key': KEY, 'previous_id': nullable(ID), 'evidence_id': ID, 'role': ROLE, 'reason': NOTE,
                'observed_on': nullable(DATE), 'mode': choice('renewed_support', 'reaffirmation'),
                'uncertainty': choice('unknown', 'disputed', 'uncertain', 'no_known_uncertainty')},
    'actual': {'evidence_id': ID, 'lot_id': nullable(ID)},
    'verify': {'actual_id': ID, 'role': ROLE, 'evidence_id': ID},
    'match': {'item_key': KEY, 'actual_id': ID, 'amount': AMOUNT, 'operation_key': KEY, 'evidence_id': ID},
    'unmatch': {'match_id': ID, 'evidence_id': ID, 'reason': NOTE},
    'group_review': {'version_id': ID, 'role': ROLE, 'verdict': VERDICT, 'reason': NOTE},
}
REFERENCES = {
    'actual': (ForecastActual, 'case'), 'evidence': (Evidence, 'case'), 'lot': (CashVerification, 'receipt__case'),
    'match': (ForecastMatch, 'case'), 'previous': (ForecastItemSupport, 'case'), 'run': (domain.ForecastRun, 'case'),
    'scenario': (domain.ForecastScenario, 'case'), 'version': (Version, 'document__case'),
    'owner': (get_user_model(), 'grant__case'),
}


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': action}, **VERSIONS, 'scenario_id': ID, **fields}) for action, fields in HUMAN_ACTIONS.items()
]}, response=obj({**WORK_RESULT['properties'], 'record_id': ID}), status=201,
    summary='Record an exact human forecast, disclosure, actual or match decision on the selected work')
def command(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    excluded = {'action', 'expected_revision', 'case_revision'}
    data = {}
    for key, value in body.items():
        if key in excluded:
            continue
        if key.endswith('_id') and key[:-3] in REFERENCES:
            field = key[:-3]
            model, case_relation = REFERENCES[field]
            rows = model.objects.filter(**{case_relation: work.case}).distinct()
            data[field] = get_object_or_404(rows, pk=value) if value is not None else None
        else:
            data[key] = value
    if data.get('observed_on'):
        data['observed_on'] = date.fromisoformat(data['observed_on'])
    if data.get('due_at'):
        data['due_at'] = datetime.fromisoformat(data['due_at'])
    row = native.human_action(actor, work.pk, body['expected_revision'], body['case_revision'],
                              body['scenario_id'], body['action'], data)
    wake_waiting(work.pk)
    return recorded(work, row)


@endpoint(method='POST', request=obj({**VERSIONS, 'run_id': ID, 'base_configuration': ID,
    'rows': array(KEY, limit=200), 'fields': array(choice(*FIELDS)), 'metadata': array(choice(*METADATA)),
    'recipients': array(ID, limit=100), 'reviewer_roles': array(ROLE), 'publisher_roles': array(ROLE),
    'allow_preparer_review': BOOLEAN, 'oracle': ID, 'decision': ID, 'effective_from': DATETIME}),
    response=obj({**WORK_RESULT['properties'], 'record_id': ID}), status=201,
    summary='Draft exact group forecast disclosure against a reviewed run and independent expected output')
@transaction.atomic
def disclosure(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    work = FactoryWork.objects.select_for_update(of=('self',)).select_related('case', 'source_head').get(pk=work.pk)
    require(actor, work.case, 'policy.configure')
    _, selection = native.source(work, actor)
    if selection['audience'] != 'group':
        raise PermissionDenied('Select group forecast work for this disclosure.')
    run = native.calculation(work, actor)
    if not run or run.pk != body['run_id'] or work.revision != body['expected_revision']:
        raise ValidationError('STALE_VERSION: Open the current exact group forecast before drafting disclosure.')
    fields = {key: value for key, value in body.items() if key not in {*VERSIONS, 'run_id'}}
    fields['allow_preparer_review'] = 'yes' if fields['allow_preparer_review'] else 'no'
    row = group_disclosure_forms.save(actor, work.case, run, fields, body['case_revision'])
    return recorded(work, row)


@endpoint(response=obj({**VERSIONS, 'scenario_id': ID, 'month': PERIOD,
    'rows': array(obj({'key': KEY, 'expected': nullable(AMOUNT), 'actual': nullable(AMOUNT), 'status': TEXT,
                       'notes': array(obj({'id': ID, 'actual_id': ID, 'reason': NOTE}), limit=50)})),
    'actuals': array(obj({'id': ID, 'direction': choice('inflow', 'outflow'), 'amount': nullable(AMOUNT),
                          'verified': BOOLEAN}), limit=50),
    'history': array(obj({'id': ID, 'item_key': KEY, 'actual_id': ID, 'amount': AMOUNT, 'reversed': BOOLEAN}), limit=50),
    'more_actuals': BOOLEAN, 'more_history': BOOLEAN, 'more_notes': BOOLEAN}),
    path_parameters={'month': PERIOD}, summary='Read expected and actual cash for one exact forecast month')
def month(request, work_id, month):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    scenario, _ = native.source(work, actor)
    values = forecast_actuals.monthly(actor, work.case, scenario, month)
    return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'scenario_id': scenario.pk,
            'month': month, 'rows': [{'key': row['item']['key'], 'expected': row['item']['amount'],
                                      'actual': row['actual'], 'status': row['status'],
                                      'notes': [{'id': note.pk, 'actual_id': note.data['actual'], 'reason': note.data['reason']}
                                                for note in row['notes']]} for row in values['rows']],
            'actuals': [{'id': item.pk, 'direction': item.payload['direction'], 'amount': item.payload['amount'],
                         'verified': item.independently_verified or item.lot_id is not None} for item in values['actuals']],
            'history': [{'id': item.pk, 'item_key': item.item_key, 'actual_id': item.actual_id, 'amount': item.amount,
                         'reversed': hasattr(item, 'reversal')} for item in values['history']],
            **{key: values[key] for key in ('more_actuals', 'more_history', 'more_notes')}}


@endpoint(method='POST', request=obj({**VERSIONS, 'item_key': KEY, 'actual_id': ID, 'reason': NOTE}),
    response=obj({**WORK_RESULT['properties'], 'record_id': ID}), status=201, path_parameters={'month': PERIOD},
    summary='Record a source-bound reason that the selected forecast item and actual remain unmatched')
@transaction.atomic
def leave_unmatched(request, work_id, month, *, body):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    work = FactoryWork.objects.select_for_update(of=('self',)).select_related('case', 'source_head').get(pk=work.pk)
    scenario, _ = native.source(work, actor)
    if work.revision != body['expected_revision']:
        raise ValidationError('STALE_VERSION: Refresh the selected forecast and actuals.')
    row = forecast_actuals.leave_unmatched(actor, work.case_id, scenario.pk, month, body['item_key'],
                                           body['actual_id'], body['reason'], body['case_revision'])
    return recorded(work, row)


class ObservationForm(forms.Form):
    expected_revision = forms.IntegerField(min_value=1, max_value=REVISION['maximum'])
    case_revision = forms.IntegerField(min_value=1, max_value=REVISION['maximum'])
    job_id = forms.IntegerField(min_value=1, max_value=ID['maximum'])
    outcome = forms.ChoiceField(choices=recovery.OUTCOMES.items())
    proof = forms.FileField(required=False)


@endpoint(method='POST', multipart=True, request=obj({**VERSIONS, 'job_id': ID,
    'outcome': choice(*recovery.OUTCOMES), 'proof': FILE}, optional=('proof',)),
    response=WORK_RESULT, summary='Record a human observation about the exact uncertain original forecast delivery')
def observe_delivery(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    form = ObservationForm(request.POST, request.FILES)
    if not form.is_valid():
        raise ValidationError('Choose the original job and a recorded delivery outcome.')
    data = form.cleaned_data
    recovery.observe(actor, work.pk, data['expected_revision'], data['case_revision'], data['job_id'],
                     data['outcome'], data['proof'])
    work.refresh_from_db()
    return result(work)


@endpoint(response=FILE, media_type='application/octet-stream', summary='Read private evidence of the actor’s delivery observation')
def delivery_proof(request, work_id, observation_id):
    work = require_line(request.user, work_id, native.DEFINITION)
    try:
        proof = recovery.attachment(request.user, work, observation_id)
        body = case_uploads.read(proof)
    except (OSError, ValidationError) as exc:
        raise Http404 from exc
    return FileResponse(BytesIO(body), as_attachment=True, filename=proof.name, content_type='application/octet-stream')


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': 'cancel'}, 'expected_revision': REVISION}),
    obj({'action': {'const': 'lookup'}, 'expected_revision': REVISION, 'job_id': ID}),
    obj({'action': {'const': 'operate'}, **VERSIONS, 'job_id': ID, 'operation': choice('cancel', 'retry'), 'reason': NOTE}),
    obj({'action': {'const': 'restart'}, **VERSIONS, 'configuration_id': ID, 'reason': {**TEXT, 'maxLength': 2000},
         'selection': STARTS[native.DEFINITION][1]['properties']['value']}),
]}, response=WORK_RESULT, summary='Check the original forecast delivery or explicitly stop or restart allowed work')
def lifecycle(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    expected = body['expected_revision']
    if body['action'] == 'cancel':
        work = native.cancel(actor, work.pk, expected)
    elif body['action'] == 'lookup':
        work = recovery.reconcile(actor, work.pk, expected, job_id=body['job_id'])
    elif body['action'] == 'operate':
        work = native.operate(actor, work.pk, expected, body['case_revision'], body['job_id'], body['operation'], body['reason'])
        wake_waiting(work.pk)
    else:
        work = native.restart(actor, work.pk, expected, body['case_revision'], body['selection'],
                              body['configuration_id'], body['reason'])
        progress_result(actor, work, True)
    return result(work)
