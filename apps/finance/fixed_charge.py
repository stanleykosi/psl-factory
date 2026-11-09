"""Annual/fixed-contract bridge. Explicit amounts, exact periods, no recurrence inference."""
from datetime import date
from decimal import Decimal, localcontext
import hashlib
import json
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from apps.core.services import lock_case, event, bump
from apps.documents.contracts import validate
from apps.identity.services import require
from . import contract_coverage as cc
from .billing import digest, policies
from .billing_math import price
from .rules import decimal, number
from .models import (CoverageFixedCharge, CoverageNativePreparation, CoveragePreparationRequest,
    CoveragePreparationReceipt, CoverageAssessment, BillingPreparation, InvoiceIssue, InvoiceJob)

ID = {'type': 'integer', 'minimum': 1}
NULLID = {'anyOf': [ID, {'type': 'null'}]}
CHARGE = cc.obj({
    'implementation': {'const': 'exact-fixed-charge/v1'},
    'period': cc.PERIOD,
    'currency': {'type': 'string', 'pattern': '^[A-Z]{3}$'},
    'amount': {'anyOf': [{'type': 'string', 'maxLength': 64}, {'type': 'null'}]},
    'amount_basis': {'enum': ['gross_including_tax', 'net_exclusive', 'unknown']},
    'method': {'enum': ['supplied_gross_total', 'configured_net_tax_v1', 'unknown']},
    'decimal_places': {'anyOf': [{'type': 'integer', 'minimum': 0, 'maximum': 8}, {'type': 'null'}]},
    'tax_configuration_id': NULLID,
    'due_date': {'anyOf': [cc.DATE, {'type': 'null'}]},
    'rule_reference': cc.NULLTEXT,
    'tax_treatment_reference': cc.NULLTEXT,
})


def route_for(actor, request, permission='read', current=True, require_due=False, assessment=None):
    route = cc.preparation_route(request)
    from . import preparation_continuation as continuation
    resumed = continuation.latest(request)
    if resumed:
        continuation.access(actor, resumed, current=current)
        if assessment is not None and assessment.pk != resumed.assessment_id:
            raise ValidationError('Exact current continuation assessment required')
        route = dict(route, assessment=resumed.assessment, recipient=resumed.recipient, actor=resumed.actor, continuation=resumed)
    if assessment is not None and assessment.pk != route['assessment'].pk:
        receipt = CoveragePreparationReceipt.objects.filter(request=request).first()
        if not receipt:
            raise ValidationError('Unacknowledged work must use explicit route revalidation first')
        cc.receipt_identity(receipt)
        if assessment.terms.case_id != request.assessment.terms.case_id:
            raise ValidationError('Current preparation assessment must remain in the exact case')
        rows = [r for r in assessment.result['obligations'] if r['key'] == request.obligation_key]
        if len(rows) != 1 or cc.obligation(assessment.terms, {k: rows[0][k] for k in ['start', 'end', 'bill_on']}) != request.obligation_key:
            raise ValidationError('Later binding must preserve the original source-backed obligation')
        # An acknowledgement is never rewritten or rerouted. New pricing can bind a current
        # assessment of the same obligation, with the original recipient and receipt intact.
        route = dict(route, assessment=assessment, recipient=receipt.actor)
    cc.terms_access(actor, route['assessment'].terms, permission, current=current)
    if current:
        if route['state'] != 'ready': raise ValidationError('Exact preparation route is cancelled')
        cc.terms_access(route['actor'], route['assessment'].terms, 'prepare')
        if cc.active_findings(actor, route['assessment'].terms):
            raise ValidationError('Exact active source interpretation requires reconciliation')
        if require_due:
            result = cc.current_assessment(actor, route['assessment'])
            rows = [r for r in result['obligations'] if r['key'] == request.obligation_key and r['status'] == 'missing_invoice']
            if len(rows) != 1: raise ValidationError('Exact uncovered obligation requires revalidation')
    return route


def charge_access(actor, charge, permission='read', current=True):
    terms = charge.assessment.terms
    cc.terms_access(actor, terms, permission, current=current)
    cc.request_identity(charge.request)
    validate(CHARGE, charge.payload)
    if digest(charge.payload) != charge.sha256: raise ValidationError('Fixed-charge source changed')
    proof = cc.evidence(terms.case, charge.evidence_id, 'coverage_fixed_charge',
        [terms.register.reference, terms.contract.reference], 'configure')
    if cc.supplied_json(proof) != {'request_id': charge.request_id, 'assessment_id': charge.assessment_id, 'charge': charge.payload}:
        raise ValidationError('Fixed-charge declaration differs from exact private evidence')
    rows = [r for r in charge.assessment.result['obligations'] if r['key'] == charge.request.obligation_key]
    if len(rows) != 1 or charge.payload['period'] != {k: rows[0][k] for k in ['start', 'end', 'bill_on']}:
        raise ValidationError('Fixed charge must bind the exact requested contractual period')
    if cc.obligation(terms, charge.payload['period']) != charge.request.obligation_key:
        raise ValidationError('Fixed charge changes the exact source-backed obligation')
    if terms.case_id != charge.request.assessment.terms.case_id or charge.payload['currency'] != terms.coverage.currency:
        raise ValidationError('Fixed-charge case or currency differs')
    for k in ['start', 'end', 'bill_on']: date.fromisoformat(charge.payload['period'][k])
    if charge.payload['due_date'] is not None: date.fromisoformat(charge.payload['due_date'])
    if charge.payload['amount'] is not None: decimal(charge.payload['amount'], nonnegative=True)
    if current:
        route = route_for(actor, charge.request, assessment=charge.assessment)
        if route['assessment'].pk != charge.assessment_id: raise ValidationError('Fixed charge belongs to an earlier route assessment')
        if CoverageFixedCharge.objects.filter(request=charge.request, version__gt=charge.version).exists():
            raise ValidationError('A newer fixed-charge declaration exists')
        cc.terms_access(charge.actor, terms, 'configure')
    return terms


@transaction.atomic
def supply_charge(actor, case_id, request_id, payload, evidence_id, expected, *, assessment_id=None):
    case = lock_case(actor, case_id, 'coverage.configure', expected)
    request = cc.exact(case, CoveragePreparationRequest, request_id)
    assessment = cc.exact(case, CoverageAssessment, assessment_id) if assessment_id else None
    route = route_for(actor, request, 'configure', require_due=True, assessment=assessment)
    validate(CHARGE, payload)
    prior = CoverageFixedCharge.objects.filter(request=request).order_by('-version').first()
    if prior and prior.payload == payload and prior.assessment_id == route['assessment'].pk:
        try:
            cc.terms_access(prior.actor, prior.assessment.terms, 'configure')
        except PermissionDenied:
            pass  # Explicit intact-source re-attestation, never renewal of the withdrawn actor's grant.
        else:
            charge_access(actor, prior, 'configure'); return prior
    charge = CoverageFixedCharge(request=request, assessment=route['assessment'],
        version=prior.version + 1 if prior else 1, payload=payload, sha256=digest(payload), evidence_id=evidence_id, actor=actor)
    charge_access(actor, charge, 'configure')
    charge.save(force_insert=True)
    event(actor, case, 'coverage.fixed_charge_supplied', charge=charge.pk); bump(case)
    return charge


def identity(charge):
    """Case-scoped source namespace. A free-text system name grants no global authority."""
    terms = charge.assessment.terms
    return {'implementation': 'fixed-service-obligation/v1', 'case': str(terms.case_id),
        'register': {k: terms.register.payload[k] for k in ['system', 'external_id']},
        'contract': {k: terms.contract.payload[k] for k in ['system', 'external_id']},
        'customer': terms.coverage.customer, 'service': terms.coverage.service,
        'contract_reference': terms.coverage.contract}


def identity_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def obligation(charge):
    return identity_hash(dict(identity(charge), period={k: charge.payload['period'][k] for k in ['start', 'end']}))


def conflicting_effect(charge, *, permit_own_issue=False):
    """A revised overlapping period must reconcile its earlier effect, not become new billing."""
    period = charge.payload['period']; service = identity_hash(identity(charge))
    common = {'invoice__case': charge.assessment.terms.case,
        'invoice__preparation__kind': 'fixed_contract',
        'invoice__preparation__snapshot__native_service': service,
        'invoice__payload__contract_period__start__lte': period['end'],
        'invoice__payload__contract_period__end__gte': period['start']}
    issued = InvoiceIssue.objects.filter(**common)
    if permit_own_issue: issued = issued.exclude(obligation_key=obligation(charge))
    if issued.exists():
        raise ValidationError('An issued invoice overlaps this exact source service period; reconcile through the native correction workflow')
    uncertain = InvoiceJob.objects.filter(**common, kind='issue', status__in=['unknown', 'leased', 'held'])
    # The existing job may still recover its own exact receipt. This guard prevents new
    # or changed period work from issuing while another period has an uncertain effect.
    if permit_own_issue: uncertain = uncertain.exclude(invoice__obligation_key=obligation(charge))
    if uncertain.exists():
        raise ValidationError('An overlapping service period has unresolved invoice work; look up its original receipt before another preparation')


def inputs(actor, charge):
    terms = charge_access(actor, charge)
    p = charge.payload; findings = []; states = {}; values = {}
    if p['rule_reference'] is None: findings.append('Exact contractual pricing rule reference is unknown')
    if p['tax_treatment_reference'] is None: findings.append('Explicit contractual tax treatment reference is unknown')
    if p['amount'] is None: findings.append('Exact contractual amount is unknown')
    if p['due_date'] is None: findings.append('Exact contractual payable due date is unknown; bill date is not a due date')
    if p['decimal_places'] is None: findings.append('Explicit monetary precision is unknown')
    if p['amount_basis'] != terms.coverage.amount_basis:
        findings.append('Amount basis differs from exact billing coverage')
    figures = {'net': None, 'tax': None, 'total': None, 'raw_net': None}
    if p['method'] == 'supplied_gross_total' and p['amount_basis'] == 'gross_including_tax':
        if p['tax_configuration_id'] is not None: findings.append('Supplied gross total must not be taxed again')
        if p['amount'] is not None and p['decimal_places'] is not None:
            n = decimal(p['amount'], nonnegative=True)
            with localcontext() as context:
                context.prec = 512
                exact_precision = n == n.quantize(Decimal(1).scaleb(-p['decimal_places']))
            if not exact_precision:
                findings.append('Supplied gross total exceeds declared precision; no rounding inferred')
            else: figures['total'] = number(n)
    elif p['method'] == 'configured_net_tax_v1' and p['amount_basis'] == 'net_exclusive':
        states, values, missing = policies(terms.case, ['D08.tax_tier_rounding_rules']); findings += missing
        state = states['D08.tax_tier_rounding_rules']
        method = values.get('D08.tax_tier_rounding_rules', [None])[0]
        if p['tax_configuration_id'] is None or p['tax_configuration_id'] != state['id']:
            findings.append('Exact supplied current tax configuration is required')
        elif method and p['decimal_places'] != method['decimal_places']:
            findings.append('Supplied precision differs from configured arithmetic')
        elif method and p['amount'] is not None: figures = price('1', p['amount'], method)
    else: findings.append('Explicit supported amount and tax treatment required')
    snapshot = {'implementation': 'fixed-charge-preparation/v1', 'charge': charge.pk, 'charge_hash': charge.sha256,
        'evidence_hash': charge.evidence.sha256, 'assessment': charge.assessment_id,
        'coverage': terms.coverage_id, 'coverage_version': terms.coverage.version,
        'register': cc.source_pin(terms.register), 'contract': cc.source_pin(terms.contract),
        'period': p['period'], 'request': charge.request_id, 'obligation': charge.request.obligation_key,
        'native_obligation': obligation(charge), 'native_service': identity_hash(identity(charge)), 'policies': states}
    line = dict(figures, kind='fixed_contract', period=p['period'], rule=p['rule_reference'],
        tax_treatment=p['tax_treatment_reference'], source_amount=p['amount'], source_basis=p['amount_basis'])
    result = {'status': 'held' if findings else 'prepared', 'findings': findings, 'lines': [line],
        'total': None if findings else figures['total'], 'currency': p['currency'],
        'amount_basis': 'gross_including_tax', 'due_date': p['due_date'],
        'coverage_completeness': terms.coverage.completeness, 'usage_completeness': None,
        'invoice_issued': False, 'ledger_posted': False, 'cash_received': False, 'release_authorized': False}
    return snapshot, result


def preparation_access(actor, prep):
    if prep.kind == 'fixed_contract':
        require(actor, prep.case, 'case.read')
        if not prep.fixed_charge_id: raise ValidationError('Exact fixed-charge lineage required')
        charge_access(actor, prep.fixed_charge, current=False)


def ensure_current(prep):
    if not prep.fixed_charge_id or prep.usage_id or prep.handoff_id:
        raise ValidationError('Exact fixed charge, without usage or stage substitution, required')
    from . import preparation_continuation as continuation
    resumed = continuation.latest(prep.fixed_charge.request)
    authority = resumed.recipient if resumed else prep.actor
    require(authority, prep.case, 'finance.billing.prepare'); require(authority, prep.case, 'finance.read')
    route = route_for(authority, prep.fixed_charge.request, 'receive', assessment=prep.fixed_charge.assessment)
    if route['recipient'].pk != authority.pk: raise PermissionDenied('Exact routed Finance recipient required')
    conflicting_effect(prep.fixed_charge, permit_own_issue=True)
    snapshot, result = inputs(authority, prep.fixed_charge)
    if prep.coverage_id != prep.fixed_charge.assessment.terms.coverage_id or prep.snapshot != snapshot or prep.result != result:
        raise ValidationError('Fixed-charge preparation changed or is stale; rebuild exact current evidence')
    if result['status'] != 'prepared': raise ValidationError(result['findings'])
    _, coverage = cc.projection(authority, prep.fixed_charge.assessment.terms, route['assessment'].as_of)
    rows = [r for r in coverage['obligations'] if r['key'] == prep.fixed_charge.request.obligation_key]
    if coverage['status'] != 'assessed' or len(rows) != 1:
        raise ValidationError('Current invoice coverage requires reconciliation before another effect')
    if rows[0]['status'] == 'covered':
        from .models import CoverageInvoiceReference
        refs = list(CoverageInvoiceReference.objects.filter(pk__in=rows[0]['invoice_refs']))
        if len(refs) != 1 or not refs[0].native_issue_id or refs[0].native_issue.obligation_key != obligation(prep.fixed_charge):
            raise ValidationError('Another verified invoice already covers this period')
    elif rows[0]['status'] != 'missing_invoice':
        raise ValidationError('Current period is not an uncovered or exactly issued obligation')
    return prep


@transaction.atomic
def prepare(actor, case_id, charge_id, expected):
    case = lock_case(actor, case_id, 'finance.billing.prepare', expected); require(actor, case, 'finance.read')
    charge = CoverageFixedCharge.objects.filter(pk=charge_id, assessment__terms__case=case).first()
    if not charge: raise ValidationError('Exact same-case fixed charge required')
    from . import preparation_continuation as continuation
    resumed = continuation.latest(charge.request)
    route = route_for(actor, charge.request, 'receive', require_due=not resumed, assessment=charge.assessment)
    if route['recipient'].pk != actor.pk: raise PermissionDenied('Only the routed Finance recipient can prepare')
    snapshot, result = inputs(actor, charge)
    if resumed:
        continuation.unresolved(charge.request)
        matches = list(BillingPreparation.objects.filter(case=case, fixed_charge=charge, snapshot=snapshot, result=result))
        if len(matches) > 1: raise ValidationError('Multiple exact preparations require reconciliation')
        if matches:
            recovered(actor, matches[0])
            if result['status'] == 'prepared': ensure_current(matches[0])
            return matches[0]
        route_for(actor, charge.request, 'receive', require_due=True, assessment=charge.assessment)
    conflicting_effect(charge)
    key = digest({'case': str(case.pk), 'kind': 'fixed_contract', 'snapshot': snapshot, 'actor': actor.pk})
    old = BillingPreparation.objects.filter(operation_key=key).first()
    if old: return old
    prep = BillingPreparation.objects.create(case=case, coverage=charge.assessment.terms.coverage,
        fixed_charge=charge, kind='fixed_contract', snapshot=snapshot, result=result, operation_key=key, actor=actor)
    receipt = CoveragePreparationReceipt.objects.filter(request=charge.request).first()
    if receipt is None:
        receipt = cc.receive_preparation(actor, case.pk, charge.request_id, None, case.revision)
        case.refresh_from_db()
    cc.receipt_identity(receipt)
    if receipt.actor_id != actor.pk and not resumed: raise PermissionDenied('Only the acknowledged recipient can bind native preparation')
    binding_payload = {'receipt': receipt.pk, 'request': charge.request_id, 'charge': charge.pk,
        'preparation': prep.pk, 'operation_key': prep.operation_key, 'period': charge.payload['period'], 'invoice_issued': False}
    if resumed: binding_payload['continuation_id'] = resumed.pk
    CoverageNativePreparation.objects.create(receipt=receipt, preparation=prep, actor=actor, payload=binding_payload)
    event(actor, case, 'coverage.native_preparation_created', preparation=prep.pk); bump(case)
    return prep


def recovered(actor, preparation):
    """Read committed identity without relabelling historical state current or issuing."""
    preparation_access(actor, preparation); require(actor, preparation.case, 'finance.read')
    binding = CoverageNativePreparation.objects.filter(preparation=preparation).first()
    if not binding: raise ValidationError('No committed native preparation binding exists')
    cc.receipt_identity(binding.receipt)
    expected = {'receipt': binding.receipt_id, 'request': preparation.fixed_charge.request_id,
        'charge': preparation.fixed_charge_id, 'preparation': preparation.pk, 'operation_key': preparation.operation_key,
        'period': preparation.fixed_charge.payload['period'], 'invoice_issued': False}
    if 'continuation_id' in binding.payload:
        from .models import CoveragePreparationContinuation
        from .preparation_continuation import access
        resumed = CoveragePreparationContinuation.objects.filter(pk=binding.payload['continuation_id'], receipt=binding.receipt,
            assessment=preparation.fixed_charge.assessment, recipient=binding.actor).first()
        if not resumed: raise ValidationError('Exact historical continuation binding required')
        access(actor, resumed, current=False); expected['continuation_id'] = resumed.pk
    if binding.payload != expected: raise ValidationError('Native preparation receipt identity differs')
    return binding


def case_access(actor, case):
    for prep in BillingPreparation.objects.filter(case=case, kind='fixed_contract'):
        preparation_access(actor, prep)
