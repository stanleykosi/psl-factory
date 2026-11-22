"""Private name attestations for the same, already matched payroll employee."""

import hashlib
import json
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.views.decorators.debug import sensitive_variables

from adapters.forecast import KEY
from apps.core.models import Audit, Evidence
from apps.core.services import add_evidence, event
from apps.documents.contracts import validate
from apps.identity.services import require
from apps.policy.payroll_validators import NAME_CHECK
from apps.policy.services import active_component, reference_values

from . import hrfinance as hr, payroll
from .hrfinance_models import HRReadSnapshot
from .payroll_models import PayrollHRFollowup, PayrollInput, PayrollRun


PROTOCOL = 'psl.payroll-name-attestation/v1'
KIND = 'agent_private_payroll_name_attestation'
FACT = 'factory.payroll_name_attested'
CHECK = 'factory.payroll_names_checked'
ROUTED = 'factory.payroll_name_correction_routed'
CAPTURE_ACTIONS = {'payroll': 'payroll.capture', 'hr': 'hrfinance.capture'}


def rule(case):
    config = active_component(NAME_CHECK, case)
    selection = reference_values(config)[0]
    if selection['comparison'] is None:
        raise ValidationError('Staff name checks need a reviewed rule. Ordinary payroll matching can continue.')
    return config, selection


def valid_text(value, limit):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit and all(ord(ch) >= 32 for ch in value)


def exact_row(rows, key, selected):
    matches = [item for item in rows if item[key] == selected]
    if len(matches) != 1:
        raise ValidationError('Choose one exact row from the recorded source.')
    return matches[0]


def holder_access(actor, case, side):
    read = 'payroll.read' if side == 'payroll' else 'hrfinance.read'
    for action in ('case.read', 'evidence.add', CAPTURE_ACTIONS[side], read):
        require(actor, case, action)


def payroll_holder(item):
    holder_access(item.actor, item.request.case, 'payroll')
    payroll.input_current(item)


def payroll_row(item, row_key):
    payroll_holder(item)
    row = exact_row(item.payload['rows'], 'row_ref', row_key)
    if row.get('quarantine_codes'):
        raise ValidationError('Resolve the original payroll row before checking its name.')
    return row['employee_id']


def hr_holder(item):
    case = item.contract.need.case
    holder_access(item.actor, case, 'hr')
    hr.authority(item.actor, case, 'authorize')


def current_hr_source(item):
    hr_holder(item)
    hr.current_snapshot(item, for_use=True)
    if item.contract.payload['purpose'] != 'payroll_matching':
        raise ValidationError('Choose the approved HR snapshot for payroll matching.')


def fact_pin(config, side, item, staff_key, employee):
    return {'policy': config.pk, 'side': side, 'record': item.pk, 'source_sha256': item.sha256,
            'row': staff_key, 'employee': employee}


@transaction.atomic
@sensitive_variables()
def capture(actor, case_id, side, record_id, staff_key, name, source_reference, expected):
    if (not isinstance(side, str) or side not in CAPTURE_ACTIONS or type(expected) is not int
            or not valid_text(name, 160) or not valid_text(source_reference, 160)):
        raise ValidationError('Supply the exact recorded name and its source reference.')
    validate(KEY, staff_key)
    lock = payroll.locked if side == 'payroll' else hr.locked
    case = lock(actor, case_id, CAPTURE_ACTIONS[side], expected)
    config, _ = rule(case)
    if side == 'payroll':
        item = payroll.exact(case, PayrollInput, record_id)
        if item.actor_id != actor.pk:
            raise PermissionDenied('The current payroll source owner records this name.')
        employee = payroll_row(item, staff_key)
    else:
        item = hr.exact(case, HRReadSnapshot, record_id)
        if item.actor_id != actor.pk:
            raise PermissionDenied('The authorised HR source holder records this name.')
        current_hr_source(item)
        employee = exact_row(item.payload['rows'], 'employee_id', staff_key)['employee_id']
    body = json.dumps({'protocol': PROTOCOL, 'name': name, 'source_reference': source_reference}, ensure_ascii=False)
    pin = fact_pin(config, side, item, staff_key, employee)
    latest = Audit.objects.filter(case=case, actor=actor, action=FACT, data__contains=pin).order_by('-pk').first()
    sha = hashlib.sha256(body.encode()).hexdigest()
    if latest and latest.data['attestation_sha256'] == sha:
        return latest
    proof = add_evidence(actor, case.pk, KIND, body, PROTOCOL, expected)
    return event(actor, case, FACT, **pin, evidence=proof.pk, attestation_sha256=proof.sha256)


@sensitive_variables()
def current_fact(case, config, side, item, staff_key, employee):
    attestation = Audit.objects.filter(case=case, actor_id=item.actor_id, action=FACT,
        data__contains=fact_pin(config, side, item, staff_key, employee)).order_by('-pk').first()
    if attestation is None:
        return None, None
    proof = Evidence.objects.filter(case=case, kind=KIND, source=PROTOCOL, created_by_id=item.actor_id,
        pk=attestation.data['evidence'], sha256=attestation.data['attestation_sha256']).first()
    if proof is None or hashlib.sha256(proof.body.encode()).hexdigest() != proof.sha256:
        raise ValidationError('The recorded source attestation no longer matches its proof.')
    try:
        value = json.loads(proof.body)
    except ValueError as exc:
        raise ValidationError('The recorded source attestation is invalid.') from exc
    if (not isinstance(value, dict) or set(value) != {'protocol', 'name', 'source_reference'} or value['protocol'] != PROTOCOL
            or not valid_text(value['name'], 160) or not valid_text(value['source_reference'], 160)):
        raise ValidationError('The recorded source attestation is invalid.')
    return attestation.pk, value['name']


def reader_policy(actor, case):
    config, selection = rule(case)
    if actor.pk not in selection['reader_ids']:
        raise PermissionDenied('Use the current nominated staff name reviewer.')
    return config


@sensitive_variables()
def assess(actor, case, run_id, input_id, row_key):
    validate(KEY, row_key)
    config = reader_policy(actor, case)
    run = payroll.exact(case, PayrollRun, run_id)
    if run.kind != 'match' or not run.hr_snapshot_id or input_id not in run.metadata['input_ids']:
        raise ValidationError('Choose an exact matched payroll sheet and its original input.')
    payroll.check_run_access(actor, run)
    item = payroll.exact(case, PayrollInput, input_id)
    employee = payroll_row(item, row_key)
    if not any(row['employee_id'] == employee and row['match_status'] == 'matched' and any(
            p['input_id'] == item.pk and p['row_ref'] == row_key for p in row['provenance']) for row in run.result['rows']):
        raise ValidationError('Name checks require the same exact employee ID already matched for this source row.')
    snapshot = hr.exact(case, HRReadSnapshot, run.hr_snapshot_id)
    current_hr_source(snapshot)
    if not snapshot.contract.records.filter(kind='receipt', snapshot=snapshot, actor=actor).exists():
        raise PermissionDenied('Acknowledge the exact HR snapshot before checking names.')
    exact_row(snapshot.payload['rows'], 'employee_id', employee)
    left, payroll_name = current_fact(case, config, 'payroll', item, row_key, employee)
    right, hr_name = current_fact(case, config, 'hr', snapshot, employee, employee)
    result = 'awaiting_source' if not left or not right else 'same' if payroll_name == hr_name else 'different'
    return run, {'run': run.pk, 'input': item.pk, 'row': row_key, 'policy': config.pk, 'snapshot': snapshot.pk,
                 'payroll_attestation': left, 'hr_attestation': right, 'result': result}


@transaction.atomic
def check(actor, case_id, run_id, input_id, row_key, expected):
    if type(expected) is not int:
        raise ValidationError('Open the current payroll work version.')
    case = payroll.locked(actor, case_id, 'payroll.private.read', expected)
    _, result = assess(actor, case, run_id, input_id, row_key)
    previous = Audit.objects.filter(case=case, action=CHECK, data=result).first()
    return previous or event(actor, case, CHECK, **result)


def exact_check(case, comparison_id):
    recorded = Audit.objects.filter(case=case, action=CHECK, pk=comparison_id).first()
    if recorded is None:
        raise ValidationError('Open the exact recorded payroll name check.')
    return recorded


def current_check(actor, case, recorded):
    value = recorded.data
    run, current = assess(actor, case, value['run'], value['input'], value['row'])
    if current != value:
        raise ValidationError('Source evidence changed. Check the current names again.')
    return run


@transaction.atomic
def readback(actor, case_id, comparison_id):
    case = payroll.locked(actor, case_id, 'payroll.private.read')
    recorded = exact_check(case, comparison_id)
    routed = Audit.objects.filter(case=case, action=ROUTED, data__comparison=recorded.pk).first()
    job = PayrollHRFollowup.objects.filter(pk=routed.data['followup'], run_id=recorded.data['run']).first() if routed else None
    review = hr.correction_disposition(job.record).order_by('-pk').first() if job else None
    if review and hr.authority(review.actor, case, 'respond') != review.authority:
        raise ValidationError('Current authority differs from the recorded HR decision.')
    if review and review.kind == 'response':
        # An approved HR successor deliberately supersedes the old source details.
        if reader_policy(actor, case).pk != recorded.data['policy']:
            raise ValidationError('Current authority differs from the recorded name check.')
        payroll.access(job.run.request, actor, private=True)
        payroll_holder(payroll.exact(case, PayrollInput, recorded.data['input']))
        hr_holder(hr.exact(case, HRReadSnapshot, recorded.data['snapshot']))
        if review.contract_id != job.record.contract_id:
            raise ValidationError('The correction must retain its original HR disclosure.')
        hr.snapshot_access(actor, review.snapshot)
    else:
        current_check(actor, case, recorded)
    return {'id': recorded.pk, 'result': recorded.data['result'], 'followup': job.pk if job else None,
            'review': review.kind if review else None}


@transaction.atomic
def route(actor, case_id, comparison_id, expected):
    if type(expected) is not int:
        raise ValidationError('Open the current payroll work version.')
    case = payroll.locked(actor, case_id, 'payroll.hr_correction', expected)
    recorded = exact_check(case, comparison_id)
    run = current_check(actor, case, recorded)
    if recorded.data['result'] != 'different':
        raise ValidationError('Only a confirmed name difference needs an HR correction request.')
    previous = Audit.objects.filter(case=case, action=ROUTED, data__comparison=recorded.pk).first()
    if previous:
        return PayrollHRFollowup.objects.get(pk=previous.data['followup'], run=run)
    proof = add_evidence(actor, case.pk, 'hr_correction_request', 'Check the recorded same-ID name difference.', PROTOCOL, expected)
    case.refresh_from_db(fields=['revision'])
    followup = payroll.hr_correction(actor, case.pk, run.pk, uuid4().hex, proof.pk, case.revision)
    event(actor, case, ROUTED, comparison=recorded.pk, followup=followup.pk)
    return followup
