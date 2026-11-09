"""F28 supplied multi-customer envelope, deterministic reconciliation and native F29 origin.

Identity is explicitly local to one case, provider namespace and provider reference.
This is NOT provider authentication or cross-case/global customer identity. An actual
redelivery needs a new delivery_ref AND operation_key. A request retry reuses both;
lookup/reconciliation precedes all writes. Acceptance is not a Finance signature.
"""
import json
from datetime import date, datetime
from decimal import Decimal, localcontext
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.services import lock_case, event, bump
from apps.identity.models import Grant
from apps.identity.services import require
from apps.pmo.services import subject
from apps.documents.contracts import validate
from apps.finance.rules import decimal, number
from apps.agents.models import AgentRun
from .billing import digest, coverage_current
from .models import (BillingCoverage, BillingUsage, UsageIntakeSource,
                     UsageIntakeReceipt, UsageIntakeAcceptance, UsageIntakeWithdrawal)

KEY = {'type': 'string', 'pattern': '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'}
ID = {'type': 'integer', 'minimum': 1}
QUANTITY = {'anyOf': [{'type': 'string', 'pattern': '^[0-9]{1,24}(\\.[0-9]{1,8})?$'}, {'type': 'null'}]}
PERIOD = {'type': 'string', 'pattern': '^[0-9]{4}-(0[1-9]|1[0-2])$'}
STAMP = {'anyOf': [{'type': 'string'}, {'type': 'null'}]}

def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}

def array(items, maximum=1000):
    return {'type': 'array', 'items': items, 'minItems': 1, 'maxItems': maximum}

SCOPE = obj({'case_id': {'type': 'string', 'format': 'uuid'}, 'provider_namespace': KEY, 'provider_ref': KEY})
ROW = obj({**{k: KEY for k in ['transaction_id', 'customer', 'service', 'contract', 'unit']}, 'period': PERIOD, 'quantity': QUANTITY})
POPULATION = obj({**{k: KEY for k in ['customer', 'service', 'contract', 'unit']}, 'coverage_id': ID,
                  'currency': {'type': 'string', 'pattern': '^[A-Z]{3}$'}, 'row_count': ID, 'quantity': QUANTITY})
TOTAL = obj({'unit': KEY, 'row_count': ID, 'quantity': QUANTITY})
SOURCE = obj({'schema': {'const': 'finance-collective-usage/v1'}, 'scope': SCOPE,
              'report_ref': KEY, 'source_version': KEY, 'period': PERIOD, 'controls_version': KEY,
              'extracted_at': STAMP, 'cutoff_at': STAMP, 'completeness': {'enum': ['complete', 'partial', 'unknown']}, 'rows': array(ROW)})
CONTROLS = obj({'schema': {'const': 'finance-collective-controls/v1'}, 'scope': SCOPE,
                'report_ref': KEY, 'source_version': KEY, 'period': PERIOD, 'version': KEY,
                'approval_reference': {'anyOf': [KEY, {'type': 'null'}]}, 'population': array(POPULATION, 100), 'totals': array(TOTAL, 100)})
DIMENSIONS = ('customer', 'service', 'contract', 'unit')


def access(actor, case, action='finance.read'):
    if not get_user_model().objects.filter(pk=actor.pk, is_active=True).exists():
        raise PermissionDenied('Active authenticated principal required')
    for key in ['case.read', 'finance.read', action]:
        require(actor, case, key)


def locked(actor, case_id, action):
    case = lock_case(actor, case_id, action)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    access(actor, case, action)
    return case


def revision(case, expected):
    if expected is not None and case.revision != expected:
        raise ValidationError('Stale revision; look up the operation receipt before retrying')


def exact(case, pk):
    source = UsageIntakeSource.objects.filter(case=case, pk=pk).first()
    if not source:
        raise ValidationError('Exact authorized case usage source required')
    return source


def parsed(case, evidence_id, kind, schema):
    evidence = subject(case, evidence_id, kind)
    try:
        payload = json.loads(evidence.body)
    except (TypeError, ValueError):
        raise ValidationError('Supplied intake evidence must be a typed JSON envelope')
    validate(schema, payload)
    if payload['scope']['case_id'] != str(case.pk):
        raise ValidationError('Supplied source scope does not match this case')
    try: date.fromisoformat(payload['period'] + '-01')
    except ValueError: raise ValidationError('Explicit valid billing year and month required')
    return evidence, payload


def current(source):
    access(source.actor, source.case, 'finance.billing.capture')
    if UsageIntakeSource.objects.filter(predecessor=source).exists():
        raise ValidationError('Collective source corrected; retain old partitions and reconcile the replacement')
    if UsageIntakeWithdrawal.objects.filter(source=source).exists():
        raise ValidationError('Collective source withdrawn; no dependent pricing or release')
    if source.sha256 != digest({'source': source.payload, 'controls': source.controls}):
        raise ValidationError('Collective source/control hash mismatch')


def routes(source):
    result = {}
    for item in source.controls['population']:
        cov = BillingCoverage.objects.filter(case=source.case, pk=item['coverage_id']).first()
        if not cov:
            raise ValidationError('Population routing requires an existing authorized case coverage')
        if (cov.customer, cov.service, cov.contract, cov.currency) != tuple(item[k] for k in ['customer', 'service', 'contract', 'currency']):
            raise ValidationError('Population dimensions differ from selected coverage')
        result[cov.pk] = cov
    return result


def inspect(source):
    """Read-only reconciliation. Unknown/absent is never an inferred zero."""
    findings = []
    try:
        current(source)
    except (ValidationError, PermissionDenied) as exc:
        findings += getattr(exc, 'messages', [str(exc)])
    selected = routes(source)
    for cov in selected.values():
        if not coverage_current(cov): findings.append('Coverage has a newer immutable version: ' + str(cov.pk))
        if not cov.from_period <= source.period <= cov.to_period: findings.append('Period outside selected coverage: ' + str(cov.pk))
        if cov.completeness != 'complete': findings.append('Selected coverage completeness is not complete: ' + str(cov.pk))
    payload, controls = source.payload, source.controls
    if payload['completeness'] != 'complete': findings.append('Provider completeness is not supplied as complete')
    if controls['approval_reference'] is None: findings.append('Supplied control approval reference is unknown')
    for key in ['extracted_at', 'cutoff_at']:
        if payload[key] is None:
            findings.append(key + ' is unknown')
    expected = {tuple(p[k] for k in DIMENSIONS): p for p in controls['population']}
    actual = {}
    identities = set()
    for row in payload['rows']:
        identity = (row['customer'], row['service'], row['contract'], row['transaction_id'])
        if identity in identities: findings.append('Duplicate transaction identity: ' + row['transaction_id'])
        identities.add(identity)
        key = tuple(row[k] for k in DIMENSIONS)
        actual.setdefault(key, []).append(row)
        if row['period'] != source.period: findings.append('Row period differs from report period: ' + row['transaction_id'])
        if row['quantity'] is None: findings.append('Unknown quantity: ' + row['transaction_id'])
    predecessors = [source.pk]
    previous = source.predecessor
    while previous:
        predecessors.append(previous.pk); previous = previous.predecessor
    for batch in BillingUsage.objects.filter(coverage__case=source.case).exclude(collective_acceptance__source_id__in=predecessors):
        prior = {(r['customer'], r['service'], r['contract'], r['transaction_id']) for r in batch.rows}
        if identities & prior:
            findings.append('Previously captured transaction needs explicit source correction lineage')
    reconciliation = []
    with localcontext() as ctx:
        ctx.prec = 128
        for key, wanted in expected.items():
            rows = actual.get(key, [])
            total = None if not rows or any(r['quantity'] is None for r in rows) else number(sum((Decimal(r['quantity']) for r in rows), Decimal(0)))
            if not rows: findings.append('Missing expected population: ' + '/'.join(key))
            if len(rows) != wanted['row_count']: findings.append('Population row count mismatch: ' + '/'.join(key))
            if total is None or wanted['quantity'] is None: findings.append('Population control quantity unknown: ' + '/'.join(key))
            elif Decimal(total) != Decimal(wanted['quantity']): findings.append('Population control total mismatch: ' + '/'.join(key))
            reconciliation.append({'coverage_id': wanted['coverage_id'], 'dimensions': list(key), 'row_count': len(rows), 'quantity': total})
        for key in actual.keys() - expected.keys(): findings.append('Unexpected population: ' + '/'.join(key))
        units = {p['unit'] for p in controls['population']}
        if units != {p['unit'] for p in controls['totals']}: findings.append('Collective control units do not match expected population')
        for total in controls['totals']:
            rows = [r for r in payload['rows'] if r['unit'] == total['unit']]
            if len(rows) != total['row_count']: findings.append('Collective row count mismatch: ' + total['unit'])
            if total['quantity'] is None or not rows or any(r['quantity'] is None for r in rows): findings.append('Collective control quantity unknown: ' + total['unit'])
            elif sum((Decimal(r['quantity']) for r in rows), Decimal(0)) != Decimal(total['quantity']): findings.append('Collective control total mismatch: ' + total['unit'])
    return {'status': 'held' if findings else 'reconciled', 'findings': list(dict.fromkeys(findings)),
            'source_id': source.pk, 'source_sha256': source.sha256, 'controls_version': controls['version'],
            'population': reconciliation, 'external_authenticity_verified': False, 'finance_approval_inferred': False}


def validate_delivery(case, source, controls):
    if source['scope'] != controls['scope'] or any(source[k] != controls[k] for k in ['report_ref', 'period', 'source_version']) or source['controls_version'] != controls['version']:
        raise ValidationError('Exact source, scope, period and version-bound controls required')
    for key in ['extracted_at', 'cutoff_at']:
        if source[key] is not None:
            try:
                timestamp = datetime.fromisoformat(source[key])
                if timestamp.utcoffset() is None or timestamp > timezone.now(): raise ValueError
            except (TypeError, ValueError):
                raise ValidationError('Supplied extraction/cut-off timestamps must be actual and timezone aware')
    populations = [tuple(p[k] for k in DIMENSIONS) for p in controls['population']]
    if len(set(populations)) != len(populations) or len({p['unit'] for p in controls['totals']}) != len(controls['totals']):
        raise ValidationError('Duplicate expected population or collective control unit')
    bindings = {}
    for item in controls['population']:
        key = tuple(item[k] for k in ['customer', 'service', 'contract'])
        if key in bindings and bindings[key] != item['coverage_id']:
            raise ValidationError('One explicit coverage per customer/service/contract across units required')
        bindings[key] = item['coverage_id']
    # Check authorized routing BEFORE capturing any source or receipt, never create coverage.
    temporary = UsageIntakeSource(case=case, controls=controls)
    routes(temporary)


@transaction.atomic
def receive(actor, case_id, evidence_id, control_evidence_id, delivery_ref, operation_key, expected=None, predecessor=None):
    case = locked(actor, case_id, 'finance.billing.capture')
    validate(KEY, delivery_ref); validate(KEY, operation_key)
    evidence, payload = parsed(case, evidence_id, 'usage_intake_source', SOURCE)
    control_evidence, controls = parsed(case, control_evidence_id, 'usage_intake_controls', CONTROLS)
    validate_delivery(case, payload, controls)
    sha = digest({'source': payload, 'controls': controls})
    intent = digest({'source_sha256': sha, 'delivery_ref': delivery_ref, 'predecessor': predecessor})
    old = UsageIntakeReceipt.objects.filter(case=case, operation_key=operation_key).first()
    if old:
        if old.actor_id != actor.pk or old.intent_sha256 != intent: raise ValidationError('Operation key conflicts with recorded delivery intent')
        return old  # Actual outcome lookup, even after a lost response or stale UI revision.
    delivery_key = digest({'scope': payload['scope'], 'delivery_ref': delivery_ref})
    old_delivery = UsageIntakeReceipt.objects.filter(case=case, delivery_key=delivery_key).first()
    if old_delivery:
        raise ValidationError('Actual delivery already recorded; use its original operation key or receipt lookup')
    revision(case, expected)
    family = dict(case=case, provider_namespace=payload['scope']['provider_namespace'], provider_ref=payload['scope']['provider_ref'], report_ref=payload['report_ref'], period=payload['period'])
    source = UsageIntakeSource.objects.filter(**family, source_version=payload['source_version']).first()
    if source:
        if source.sha256 != sha or source.predecessor_id != predecessor:
            raise ValidationError('Changed source/control content needs an explicit new correction version and predecessor')
    else:
        previous = UsageIntakeSource.objects.filter(**family).order_by('-version').first()
        if (previous.pk if previous else None) != predecessor:
            raise ValidationError('Explicit latest same-scope source predecessor required for correction')
        source = UsageIntakeSource.objects.create(**family, source_version=payload['source_version'], version=previous.version + 1 if previous else 1,
            predecessor=previous, payload=payload, controls=controls, sha256=sha, evidence=evidence, control_evidence=control_evidence, actor=actor)
    original = source.receipts.order_by('pk').first()
    receipt = UsageIntakeReceipt.objects.create(source=source, case=case, operation_key=operation_key, delivery_key=delivery_key, delivery_ref=delivery_ref,
        intent_sha256=intent, duplicate_of=original, evidence=evidence, control_evidence=control_evidence, actor=actor)
    event(actor, case, 'usage_intake.received', receipt=receipt.pk, source=source.pk, duplicate=bool(original))
    bump(case)
    return receipt


def lookup(actor, case_id, operation_key):
    from apps.core.models import Case
    case = Case.objects.get(pk=case_id)
    access(actor, case)
    return UsageIntakeReceipt.objects.filter(case=case, operation_key=operation_key).first()


@transaction.atomic
def accept(actor, case_id, source_id, expected=None):
    case = locked(actor, case_id, 'finance.billing.capture')
    source = exact(case, source_id)
    current(source)
    result = inspect(source)
    if result['status'] != 'reconciled': raise ValidationError(result['findings'])
    old = UsageIntakeAcceptance.objects.filter(source=source).first()
    if old:
        partition = old.partitions.first()
        if not partition: raise ValidationError('Committed acceptance lacks partitions; reconcile before retry')
        origin(partition)  # Reconcile committed partition set before returning.
        return old
    revision(case, expected)
    receipt = source.receipts.filter(duplicate_of=None).first()
    if not receipt: raise ValidationError('Original intake receipt required')
    acceptance = UsageIntakeAcceptance.objects.create(source=source, receipt=receipt, result=result, actor=actor)
    predecessors = []
    previous = source.predecessor
    while previous:
        predecessors.append(previous.pk); previous = previous.predecessor
    for cov in routes(source).values():
        rows = [dict(row, line=index + 1) for index, row in enumerate(source.payload['rows']) if (row['customer'], row['service'], row['contract']) == (cov.customer, cov.service, cov.contract)]
        # Existing ordinary source claims are not silently overwritten by a collective import.
        for batch in BillingUsage.objects.filter(coverage__case=case).exclude(collective_acceptance=acceptance).exclude(collective_acceptance__source_id__in=predecessors):
            prior = {(r['customer'], r['service'], r['contract'], r['transaction_id']) for r in batch.rows}
            if any((r['customer'], r['service'], r['contract'], r['transaction_id']) in prior for r in rows):
                raise ValidationError('Previously captured ordinary usage requires explicit reconciliation before collective acceptance')
        BillingUsage.objects.create(coverage=cov, collective_acceptance=acceptance, evidence=source.evidence, source_sha256=source.evidence.sha256,
            rows=rows, findings=[], source_context=context(source), actor=actor)
    event(actor, case, 'usage_intake.accepted', source=source.pk, acceptance=acceptance.pk, approval_inferred=False)
    bump(case)
    return acceptance


def context(source):
    return {'provider_ref': source.provider_ref, 'provider_scope': source.payload['scope'], 'extracted_at': source.payload['extracted_at'],
            'completeness': source.payload['completeness'], 'collective_source': source.pk, 'collective_sha256': source.sha256}


def origin(usage):
    acceptance = usage.collective_acceptance
    if not acceptance: raise ValidationError('Exact collective acceptance required')
    source = acceptance.source
    current(source); access(acceptance.actor, source.case, 'finance.billing.capture')
    result = inspect(source)
    if result['status'] != 'reconciled' or result != acceptance.result:
        raise ValidationError('Collective source/control reconciliation is no longer current')
    wanted = set(routes(source))
    partitions = list(acceptance.partitions.select_related('coverage'))
    if {p.coverage_id for p in partitions} != wanted or len(partitions) != len(wanted):
        raise ValidationError('Collective partition set is incomplete or ambiguous; reconcile before pricing')
    for partition in partitions:
        cov = partition.coverage
        rows = [dict(r, line=i+1) for i,r in enumerate(source.payload['rows']) if (r['customer'], r['service'], r['contract']) == (cov.customer, cov.service, cov.contract)]
        if partition.rows != rows or partition.evidence_id != source.evidence_id or partition.source_sha256 != source.evidence.sha256 or partition.findings or partition.source_context != context(source):
            raise ValidationError('Collective partition lineage differs from immutable accepted source')
        access(partition.actor, source.case, 'finance.billing.capture')
    return {'source': source.pk, 'source_version': source.source_version, 'source_sha256': source.sha256,
            'acceptance': acceptance.pk, 'receipt': acceptance.receipt_id, 'controls_version': source.controls['version'],
            'control_evidence': source.control_evidence_id, 'control_sha256': source.control_evidence.sha256,
            'population': sorted(wanted), 'scope': source.payload['scope'], 'report_ref': source.report_ref, 'period': source.period}


def obligation(usage):
    source = usage.collective_acceptance.source
    cov = usage.coverage
    return digest({'case': str(source.case_id), 'scope': source.payload['scope'], 'report_ref': source.report_ref, 'period': source.period,
                   'customer': cov.customer, 'service': cov.service, 'contract': cov.contract, 'kind': 'collective_usage'})


@transaction.atomic
def withdraw(actor, case_id, source_id, evidence_id, reason, expected=None):
    case = locked(actor, case_id, 'finance.billing.capture'); source = exact(case, source_id)
    evidence = subject(case, evidence_id, 'usage_intake_withdrawal')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000: raise ValidationError('Explicit bounded withdrawal reason required')
    old = UsageIntakeWithdrawal.objects.filter(source=source).first()
    if old:
        if (old.actor_id, old.evidence_id, old.reason) != (actor.pk, evidence.pk, reason): raise ValidationError('Withdrawal already recorded with different intent')
        return old
    revision(case, expected)
    record = UsageIntakeWithdrawal.objects.create(source=source, evidence=evidence, reason=reason, actor=actor)
    event(actor, case, 'usage_intake.withdrawn', source=source.pk, withdrawal=record.pk); bump(case)
    return record


@transaction.atomic
def investigate(actor, case_id, source_id, expected=None):
    case = locked(actor, case_id, 'agent.billing'); revision(case, expected); source = exact(case, source_id)
    result = inspect(source)
    result.update({'capability': 'A01/A05 collective usage discrepancy investigation',
        'citations': list(case.evidence.filter(pk__in=[source.evidence_id, source.control_evidence_id]).values('id', 'kind', 'version', 'sha256')),
        'missing_fields': result['findings'], 'next_work': 'Obtain the listed missing population, quantities, period or control evidence. Submit changed facts as an explicit successor, then reconcile the entire collective before pricing.',
        'invoice_issued': False, 'approval_granted': False, 'policy_changed': False})
    run = AgentRun.objects.create(case=case, actor=actor, evidence=source.evidence, provider='deterministic-usage-intake-v1', process_id='F28', result=result)
    event(actor, case, 'usage_intake.investigated', source=source.pk, run=run.pk)
    return run
