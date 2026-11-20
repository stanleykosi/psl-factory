"""Private settlement timing investigation, independent of payroll preparation."""

import hashlib
import json
import re

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from adapters.forecast import KEY
from adapters.hrfinance import timestamp
from apps.core.models import Audit, Evidence
from apps.core.services import add_evidence, bump, event, lock_case
from apps.documents.contracts import validate
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.payroll_drafts import draft_payroll_policy
from apps.policy.payroll_validators import DEPARTURE_CHECK, DEPARTURE_SOURCES
from apps.policy.services import active_component, decision_authority, reference_values

from . import hrfinance, payroll
from .payroll_models import PayrollInput


FORMAT = 'psl.payroll-departure-payment-proof/v1'
KIND = 'agent_private_payroll_departure_payment'
FACT = 'factory.payroll_timing_evidence_recorded'
CHECK = 'factory.payroll_timing_checked'
REVIEW = 'factory.payroll_timing_acknowledged'
STATUSES = {'employment': ('ended', 'unknown'), 'settlement': ('settled', 'pending', 'failed', 'reversed', 'unknown')}
KNOWN = {'employment': 'ended', 'settlement': 'settled'}
PROOF_FIELDS = {'format', 'entity', 'employee', 'episode', 'status', 'instant', 'source_reference', 'source_version'}
HOLDER_GRANTS = {'employment': ('case.read', 'evidence.add', 'hrfinance.read', 'hrfinance.capture'),
                 'settlement': ('case.read', 'evidence.add', 'payroll.read', 'payroll.capture', 'payroll.private.read')}
REVIEW_GRANTS = ('case.read', 'hrfinance.read', 'hrfinance.respond')
CHECK_GRANTS = ('case.read', 'payroll.read', 'payroll.private.read')
INSTANT = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})')
READ_ONLY = object()


def rule(case):
    config = active_component(DEPARTURE_CHECK, case)
    scope = reference_values(config)[0]['check']
    if scope is None:
        raise ValidationError('This check needs approved employment and payment sources.')
    return config.pk, scope


def locked(actor, case_id, action, expected):
    if expected is not READ_ONLY and type(expected) is not int:
        raise ValidationError('Open the current payroll work before recording a change.')
    case = lock_case(actor, case_id, action, None if expected is READ_ONLY else expected)
    # Use the same case and grant locking order as the private payroll reader.
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    return case


@transaction.atomic
def draft_rule(actor, case_id, content, decision_id, effective_from, expected):
    case = locked(actor, case_id, 'policy.configure', expected)
    require(actor, case, 'policy.read')
    require(actor, case, 'case.read')
    return draft_payroll_policy(actor, case.pk, DEPARTURE_CHECK, content, decision_id, effective_from)


@transaction.atomic
@sensitive_variables()
def record_source_contract(actor, case_id, side, document_ref, expected):
    case = locked(actor, case_id, 'policy.configure', expected)
    for action in ('case.read', 'policy.read', 'evidence.add'):
        require(actor, case, action)
    if not isinstance(side, str) or side not in DEPARTURE_SOURCES:
        raise ValidationError('Choose the employment or settlement source contract.')
    validate(KEY, document_ref)
    kind = DEPARTURE_SOURCES[side]
    latest = Evidence.objects.filter(case=case, kind=kind).order_by('-version').only('sha256').first()
    if latest and latest.sha256 == hashlib.sha256(document_ref.encode()).hexdigest():
        return latest
    return add_evidence(actor, case.pk, kind, document_ref, FORMAT, expected)


def holder(case, scope, side):
    owner = get_user_model().objects.filter(pk=scope[side + '_holder_id'], is_active=True).first()
    if owner is None:
        raise PermissionDenied
    for action in HOLDER_GRANTS[side]:
        require(owner, case, action)
    return (hrfinance.authority(owner, case, 'authorize') if side == 'employment'
            else decision_authority(owner, case, 'Finance'))


def reviewer(actor, case, scope):
    if actor.pk != scope['reviewer_id']:
        raise PermissionDenied
    for action in REVIEW_GRANTS:
        require(actor, case, action)
    return hrfinance.authority(actor, case, 'respond')


def reader(actor, case, scope):
    if actor.pk not in scope['reader_ids']:
        raise PermissionDenied
    for action in CHECK_GRANTS:
        require(actor, case, action)


def fingerprint(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()


def source_input(actor, case, scope, input_id):
    item = payroll.exact(case, PayrollInput, input_id)
    payroll.access(item.request, actor, private=True)
    payroll.input_current(item)
    if item.request.metadata['entity'] != scope['entity']:
        raise ValidationError('Choose a payroll row for the approved employer.')
    return item


def clean_instant(side, status, value):
    if status not in STATUSES[side]:
        raise ValidationError('Choose a recorded source status.')
    if status != KNOWN[side]:
        if value is not None:
            raise ValidationError('Supply an instant only for a known settled payment or departure.')
        return None
    if not isinstance(value, str) or not INSTANT.fullmatch(value) or value.endswith('-00:00'):
        raise ValidationError('Use an exact date and time with its known time offset.')
    at = timestamp(value)
    if at > timezone.now():
        raise ValidationError('The recorded event must already have occurred.')
    return at


def facts(case, policy, side):
    return Audit.objects.filter(case=case, action=FACT, data__policy=policy, data__side=side)


@transaction.atomic
@sensitive_variables()
def capture(actor, case_id, side, episode, status, instant, source_reference, source_version, expected,
            *, employee=None, input_id=None, row=None):
    if not isinstance(side, str) or side not in STATUSES:
        raise ValidationError('Choose an employment or settlement source.')
    grants = HOLDER_GRANTS[side]
    case = locked(actor, case_id, grants[-1], expected)
    policy, scope = rule(case)
    if actor.pk != scope[side + '_holder_id']:
        raise PermissionDenied
    authority = holder(case, scope, side)
    for key in (episode, source_reference, source_version):
        validate(KEY, key)
    clean_instant(side, status, instant)
    if side == 'settlement':
        validate(KEY, row)
        item = source_input(actor, case, scope, input_id)
        rows = [candidate for candidate in item.payload['rows'] if candidate['row_ref'] == row]
        if len(rows) != 1 or rows[0].get('quarantine_codes'):
            raise ValidationError('Choose one current, unambiguous row from the original payroll source.')
        employee = rows[0]['employee_id']
        input_pin = {'input': item.pk, 'input_sha256': item.sha256, 'row': fingerprint(row)}
    else:
        validate(KEY, employee)
        input_pin = {}
    subject = fingerprint(scope['entity'], employee, episode)
    series = subject if side == 'employment' else fingerprint(scope['entity'], source_reference)
    latest = facts(case, policy, side).filter(data__series=series).order_by('-pk').first()
    if latest and (latest.data['subject'] != subject or any(latest.data[key] != pin for key, pin in input_pin.items())):
        raise ValidationError('A corrected settlement must keep the employee, episode and original payroll row.')
    value = {'format': FORMAT, 'entity': scope['entity'], 'employee': employee, 'episode': episode,
             'status': status, 'instant': instant, 'source_reference': source_reference, 'source_version': source_version}
    body = json.dumps(value, sort_keys=True)
    sha256 = hashlib.sha256(body.encode()).hexdigest()
    version = fingerprint(source_version)
    prior = facts(case, policy, side).filter(data__series=series, data__version=version).first()
    if prior:
        if prior != latest or prior.data['sha256'] != sha256 or prior.data['authority'] != authority:
            raise ValidationError('Use a fresh source version for a correction.')
        return prior
    proof = add_evidence(actor, case.pk, KIND, body, FORMAT, expected)
    return event(actor, case, FACT, policy=policy, side=side, subject=subject, series=series, version=version,
                 authority=authority, contract=scope[side + '_contract_id'], evidence=proof.pk, sha256=proof.sha256,
                 **input_pin)


def current_fact(case, policy, scope, side, selected):
    data = selected.data
    if (selected.actor_id != scope[side + '_holder_id'] or data['contract'] != scope[side + '_contract_id']
            or holder(case, scope, side) != data['authority']):
        raise PermissionDenied
    if (timezone.now() - selected.created_at).total_seconds() > scope['proof_max_age_seconds']:
        raise ValidationError('The authorised source evidence is no longer current.')
    if facts(case, policy, side).filter(data__series=data['series'], pk__gt=selected.pk).exists():
        raise ValidationError('This source evidence was corrected. Open the current records.')
    if not pinned_proof(case, selected).exists():
        raise ValidationError('The recorded source proof has changed.')


def pinned_proof(case, record):
    return Evidence.objects.filter(case=case, kind=KIND, source=FORMAT, created_by_id=record.actor_id,
        pk=record.data['evidence'], sha256=record.data['sha256'])


@sensitive_variables()
def proof_instant(case, record):
    data = record.data
    proof = pinned_proof(case, record).only('body').first()
    if proof is None or hashlib.sha256(proof.body.encode()).hexdigest() != data['sha256']:
        raise ValidationError('The recorded source proof has changed.')
    try:
        value = json.loads(proof.body)
    except ValueError as exc:
        raise ValidationError('The recorded source proof is invalid.') from exc
    if (not isinstance(value, dict) or set(value) != PROOF_FIELDS or value['format'] != FORMAT
            or fingerprint(value['entity'], value['employee'], value['episode']) != data['subject']
            or fingerprint(value['source_version']) != data['version']
            or data['side'] == 'settlement' and fingerprint(value['entity'], value['source_reference']) != data['series']):
        raise ValidationError('The recorded source proof has changed.')
    return clean_instant(data['side'], value['status'], value['instant'])


def sources(actor, case, policy, scope, settlement_id):
    reader(actor, case, scope)
    payment = facts(case, policy, 'settlement').filter(pk=settlement_id).first()
    if payment is None:
        raise ValidationError('Choose one exact settlement record from this work.')
    current_fact(case, policy, scope, 'settlement', payment)
    item = source_input(actor, case, scope, payment.data['input'])
    # Check the settlement holder's continuing access to the exact original payroll input too.
    payroll.access(item.request, payment.actor, private=True)
    if item.sha256 != payment.data['input_sha256']:
        raise ValidationError('The settlement no longer matches the original payroll source.')
    employment = facts(case, policy, 'employment').filter(data__subject=payment.data['subject']).order_by('-pk').first()
    if employment:
        current_fact(case, policy, scope, 'employment', employment)
    return payment, employment


@transaction.atomic
@sensitive_variables()
def check(actor, case_id, settlement_id, expected):
    case = locked(actor, case_id, 'payroll.private.read', expected)
    policy, scope = rule(case)
    payment, employment = sources(actor, case, policy, scope, settlement_id)
    result = 'awaiting_evidence'
    if employment:
        settled_at = proof_instant(case, payment)
        departed_at = proof_instant(case, employment)
        if settled_at is not None and departed_at is not None:
            result = 'after' if settled_at > departed_at else 'on_or_before'
        else:
            result = 'inconclusive'
    data = {'policy': policy, 'settlement': payment.pk, 'employment': employment.pk if employment else None,
            'result': result}
    existing = Audit.objects.filter(case=case, actor=actor, action=CHECK, data=data).first()
    if existing:
        return existing
    result = event(actor, case, CHECK, **data)
    bump(case)
    return result


def current_check(case, policy, scope, check_id):
    recorded = Audit.objects.filter(case=case, action=CHECK, pk=check_id, data__policy=policy).first()
    if recorded is None:
        raise ValidationError('Choose one exact private timing check.')
    _, employment = sources(recorded.actor, case, policy, scope, recorded.data['settlement'])
    if recorded.data['employment'] != (employment.pk if employment else None):
        raise ValidationError('Source evidence changed. Run the current check again.')
    return recorded


@transaction.atomic
def readback(actor, case_id, check_id):
    case = locked(actor, case_id, 'case.read', READ_ONLY)
    policy, scope = rule(case)
    is_reviewer = actor.pk == scope['reviewer_id']
    if is_reviewer:
        reviewer(actor, case, scope)
    else:
        reader(actor, case, scope)
    record = current_check(case, policy, scope, check_id)
    current = Audit.objects.filter(case=case, actor_id=scope['reviewer_id'], action=REVIEW,
                                   data__comparison=record.pk).order_by('-pk').first()
    try:
        acknowledged = current is not None and reviewer(current.actor, case, scope) == current.data['authority']
    except (PermissionDenied, ValidationError):
        acknowledged = False
    return {'id': record.pk, 'result': record.data['result'], 'acknowledged': acknowledged,
            'can_acknowledge': is_reviewer and record.data['result'] in ('after', 'on_or_before')}


@transaction.atomic
def acknowledge(actor, case_id, check_id, expected):
    case = locked(actor, case_id, 'hrfinance.respond', expected)
    policy, scope = rule(case)
    authority = reviewer(actor, case, scope)
    recorded = current_check(case, policy, scope, check_id)
    if recorded.data['result'] not in ('after', 'on_or_before'):
        raise ValidationError('Wait for both comparable source records before acknowledging a finding.')
    data = {'comparison': recorded.pk, 'policy': policy, 'authority': authority}
    existing = Audit.objects.filter(case=case, actor=actor, action=REVIEW, data=data).first()
    if existing:
        return existing
    result = event(actor, case, REVIEW, **data)
    bump(case)
    return result
