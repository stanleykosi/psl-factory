"""Exact bank receipt capture, independent verification and allocation."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.core.views import accessible_case
from apps.finance import bank_receipt_capture as domain, bank_receipt_views as forms, cash, cash_reported_amount
from apps.finance.models import CashReceipt, CashReversal, CashVerification
from apps.identity.services import require

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, Problem, array, choice, endpoint, nullable, obj


FILE = {'type': 'string', 'format': 'binary'}
DECIMAL = {'type': 'string', 'pattern': r'^[0-9]{1,32}(\.[0-9]{1,8})?$'}
BASIS = choice('gross_including_tax', 'net_excluding_tax', 'unknown')
REF = {**TEXT, 'maxLength': 100}
FACTS = obj({'customer': TEXT, 'source': TEXT, 'transaction_ref': TEXT, 'amount': nullable(TEXT),
             'currency': TEXT, 'amount_basis': BASIS, 'received_at': DATETIME})
RESULT = obj({'id': ID, 'revision': REVISION, 'receipt_id': ID})
ITEM = obj({'id': ID, 'facts': FACTS})


def scope(actor, case_id, issue_id):
    case = accessible_case(actor, case_id)
    return case, domain.issue_for(actor, case, issue_id)


def validated(form):
    if not form.is_valid():
        raise Problem(422, 'invalid_input', 'Check the payment fields and supporting proof.',
                      fields=[{'name': key, 'message': messages[0]} for key, messages in form.errors.items()])
    return form.cleaned_data


def outcome(case, receipt_id, record):
    case.refresh_from_db(fields=['revision'])
    return {'id': record.pk, 'receipt_id': receipt_id, 'revision': case.revision}


def facts(record):
    return {name: record.payload[name] for name in FACTS['properties']}


@endpoint(response=obj({
    'revision': REVISION, 'issue_id': ID, 'customer': TEXT, 'currency': TEXT, 'basis': BASIS,
    'bank_source': nullable(TEXT), 'can_report': BOOLEAN, 'recent': array(ITEM, limit=12),
}), summary='Read payment reporting controls for an exact invoice')
def options(http, case_id, issue_id):
    case, issue = scope(http.user, case_id, issue_id)
    actions = forms.case_actions(http.user, case)
    customer = issue.invoice.preparation.coverage.customer
    may_report = {'evidence.add', 'finance.cash.record'}.issubset(actions)
    source = None
    if may_report:
        try:
            source = domain.proof_policy(case).get('source')
        except ValidationError:
            pass
    latest = (CashReceipt.objects.filter(case=case, payload__customer=customer).order_by('-pk')[:12]
              if actions.intersection({'finance.cash.record', 'finance.cash.verify', 'finance.cash.allocate'}) else [])
    return {'revision': case.revision, 'issue_id': issue.pk, 'customer': customer, 'currency': issue.invoice.currency,
            'basis': issue.invoice.amount_basis, 'bank_source': source, 'can_report': may_report,
            'recent': [{'id': row.pk, 'facts': facts(row)} for row in latest]}


@endpoint(method='POST', multipart=True, status=201, response=RESULT, request=obj({
    'revision': REVISION, 'customer': REF, 'amount': DECIMAL, 'currency': {'type': 'string', 'pattern': '^[A-Z]{3}$'},
    'amount_basis': BASIS, 'received_at': DATETIME, 'source': REF, 'transaction_ref': REF, 'locator': REF, 'file': FILE,
}), summary='Report a bank payment with a known amount and its original private statement')
def report(http, case_id, issue_id):
    actor = http.user
    case, issue = scope(actor, case_id, issue_id)
    require(actor, case, 'finance.cash.record')
    form = forms.ReportForm(http.POST, http.FILES)
    values = validated(form)
    record = domain.report(actor, case.pk, issue.pk, values['revision'], form.facts(), values['locator'], values['file'])
    return outcome(case, record.pk, record)


def readback(actor, case_id, issue_id, receipt_id):
    case, issue = scope(actor, case_id, issue_id)
    receipt = domain.read_receipt(case, issue, receipt_id)
    return case, issue, receipt


def verified_roles(actor, case, receipt):
    roles = forms.permitted_roles(actor, case, domain.VERIFIER_POLICY, 'finance.cash.verify')
    if roles:
        rule = domain.reference_values(domain.active_component(domain.VERIFIER_POLICY, case))[0]
        if receipt.actor_id == actor.pk and not rule['allow_reporter_verify']:
            return []
    return roles


def allocations(actor, case, receipt, lot):
    roles = forms.permitted_roles(actor, case, domain.ALLOCATION_POLICY, 'finance.cash.allocate')
    assignment = cash.assigned(receipt)
    if not assignment or not assignment.coverage_id:
        assign = forms.permitted_roles(actor, case, domain.ALLOCATION_POLICY, 'finance.cash.assign')
        roles = [role for role in roles if role in assign]
    if roles and actor.pk == lot.actor_id:
        rule = domain.reference_values(domain.active_component(domain.ALLOCATION_POLICY, case))[0]
        if not rule['allow_verifier_allocation']:
            return []
    return roles


@endpoint(response=obj({
    'revision': REVISION, 'id': ID, 'reported': FACTS, 'amount_update_id': nullable(ID),
    'verified_lot_id': nullable(ID), 'remaining_cash': nullable(TEXT), 'reversed': BOOLEAN,
    'can_supply_amount': BOOLEAN, 'verification_roles': array(TEXT), 'independent_file_required': BOOLEAN,
    'allocation_roles': array(TEXT), 'report_url': nullable(TEXT), 'verification_url': nullable(TEXT),
}), summary='Read receipt facts, current verification, restricted proof links and permitted roles')
def detail(http, case_id, issue_id, receipt_id):
    actor = http.user
    case, issue, receipt = readback(actor, case_id, issue_id, receipt_id)
    supplement = cash_reported_amount.latest(receipt)
    lot = CashVerification.objects.filter(receipt=receipt).order_by('-pk').first()
    actions = forms.case_actions(actor, case)
    report = supplement or receipt
    independent = False
    report_url = verification_url = None
    roles = []
    args = [case.pk, issue.pk, receipt.pk]
    try:
        forms.proof_access(actor, case, receipt, supplement=supplement)
        if domain.exact_proof(receipt, supplement=supplement):
            report_url = reverse('finance_bank_proof', args=[*args, 'reported-amount' if supplement else 'report'])
            if not lot and report.payload['amount'] is not None and report.payload['amount_basis'] != 'unknown':
                roles = verified_roles(actor, case, receipt)
                independent = bool(roles and domain.proof_policy(case)['require_independent_evidence'])
    except (PermissionDenied, ValidationError):
        roles = []
    if lot:
        try:
            forms.proof_access(actor, case, receipt, lot)
            if domain.exact_proof(receipt, lot):
                verification_url = reverse('finance_bank_proof', args=[*args, 'verification'])
        except PermissionDenied:
            pass
    return {'revision': case.revision, 'id': receipt.pk, 'reported': facts(report),
            'amount_update_id': supplement.pk if supplement else None, 'verified_lot_id': lot.pk if lot else None,
            'remaining_cash': format(cash.cash_remaining(lot), 'f') if lot else None,
            'reversed': bool(lot and CashReversal.objects.filter(lot=lot).exists()),
            'can_supply_amount': (not lot and not supplement and receipt.payload['amount'] is None and
                                  receipt.actor_id == actor.pk and {'evidence.add', 'finance.cash.record'} <= actions),
            'verification_roles': roles, 'independent_file_required': independent,
            'allocation_roles': allocations(actor, case, receipt, lot) if lot else [],
            'report_url': report_url, 'verification_url': verification_url}


@endpoint(method='POST', multipart=True, status=201, response=RESULT, request=obj({
    'revision': REVISION, 'amount': DECIMAL, 'locator': REF, 'reason': {**TEXT, 'maxLength': 2000}, 'file': FILE,
}), summary='Supply a previously unknown bank amount with successor proof')
def supply_amount(http, case_id, issue_id, receipt_id):
    case, issue, receipt = readback(http.user, case_id, issue_id, receipt_id)
    values = validated(forms.SupplyAmountForm(http.POST, http.FILES))
    record = domain.supply_amount(http.user, case.pk, issue.pk, receipt.pk, values['revision'],
                                  format(values['amount'], 'f'), values['locator'], values['reason'], values['file'])
    return outcome(case, receipt.pk, record)


@endpoint(method='POST', multipart=True, status=201, response=RESULT, request=obj({
    'revision': REVISION, 'role': TEXT, 'confirmed': BOOLEAN, 'reported_amount_id': ID, 'locator': REF, 'file': FILE,
}, optional=('reported_amount_id', 'locator', 'file')), summary='Verify an exact receipt independently of allocation')
def verify(http, case_id, issue_id, receipt_id):
    actor = http.user
    case, issue, receipt = readback(actor, case_id, issue_id, receipt_id)
    roles = verified_roles(actor, case, receipt)
    if not roles:
        raise PermissionDenied
    forms.proof_access(actor, case, receipt, supplement=cash_reported_amount.latest(receipt))
    form = forms.VerifyForm(http.POST, http.FILES)
    form.fields['role'].choices = [(role, role) for role in roles]
    needed = domain.proof_policy(case)['require_independent_evidence']
    form.fields['locator'].required = form.fields['file'].required = needed
    values = validated(form)
    record = domain.verify(actor, case.pk, issue.pk, receipt.pk, values['revision'], values['role'],
                           values['locator'], values['file'], reported_amount_id=values['reported_amount_id'])
    return outcome(case, receipt.pk, record)


@endpoint(method='POST', status=201, response=RESULT, request=obj({
    'revision': REVISION, 'role': TEXT, 'amount': DECIMAL, 'key': REF, 'reason': {**TEXT, 'maxLength': 2000},
}), summary='Apply a verified cash lot to the exact issued invoice')
def allocate(http, case_id, issue_id, receipt_id, *, body):
    actor = http.user
    case, issue, receipt = readback(actor, case_id, issue_id, receipt_id)
    lot = CashVerification.objects.filter(receipt=receipt).order_by('-pk').first()
    roles = allocations(actor, case, receipt, lot) if lot else []
    if not roles:
        raise PermissionDenied
    form = forms.AllocationForm(body)
    form.fields['role'].choices = [(role, role) for role in roles]
    values = validated(form)
    record = domain.allocate(actor, case.pk, issue.pk, receipt.pk, values['revision'], values['role'],
                             format(values['amount'], 'f'), values['key'], values['reason'])
    return outcome(case, receipt.pk, record)
