"""Versioned invoice adjustments, bank reversals and verified cash successors."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Exists, OuterRef, Subquery
from django.shortcuts import get_object_or_404

from apps.agents import financial_corrections as investigator
from apps.core.evidence_access import public_evidence
from apps.core.views import accessible_case
from apps.finance import cash, cash_successors, corrections, financial_reviews
from apps.finance.correction_forms import DISPLAY_GRANTS, RESERVATION_GRANTS
from apps.finance.fixed_charge import preparation_access
from apps.finance.models import (
    CashAllocation, CashReversal, CashSuccessor, CashSuccessorAcceptance, CashVerification,
    FinancialCorrectionReview, InvoiceCorrection, InvoiceCorrectionAcceptance, InvoiceCorrectionDelivery, InvoiceIssue, InvoiceJob,
)
from apps.identity.services import active_case_grants, require
from apps.policy.document_validators import ROLES

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj
from .work import PAGE, page_number


REASON = {**TEXT, 'maxLength': 4000}
SUBJECT = choice('invoice', 'cash')
ROLE = choice(*ROLES)
VERDICT = choice('approve', 'return', 'reject')
COMMANDS = {
    'invoice_note': {'issue_id': ID, 'evidence_id': ID, 'allocation_evidence_id': nullable(ID), 'reason': REASON},
    'cash_successor': {'parent_id': ID, 'report_evidence_id': ID, 'verification_evidence_id': ID, 'legal_evidence_id': ID,
                       'reason': REASON},
    'review': {'kind': SUBJECT, 'record_id': ID, 'role': ROLE, 'verdict': VERDICT, 'evidence_id': ID, 'reason': REASON},
    'invoice_effect': {'record_id': ID, 'effect': choice(*RESERVATION_GRANTS), 'role': ROLE},
    'apply_successor': {'record_id': ID, 'role': ROLE},
    'reverse_cash': {'target': choice('lot', 'allocation'), 'record_id': ID, 'role': ROLE, 'evidence_id': ID, 'reason': REASON},
    'investigate': {'kind': SUBJECT, 'record_id': ID},
}
ENTRY = obj({'id': ID, 'created_at': DATETIME, 'source_id': ID, 'accepted_id': nullable(ID),
             'latest_review': nullable(VERDICT)})
EVIDENCE = obj({'id': ID, 'kind': TEXT, 'version': REVISION})
LOT = obj({'id': ID, 'receipt_id': ID, 'amount': TEXT, 'reversed': BOOLEAN})
CASH_READERS = ('finance.cash.record', 'finance.cash.verify', 'finance.cash.allocate', 'finance.cash.reverse',
                'finance.cash.successor.request', 'finance.cash.successor.apply')


def case_for(actor, case_id):
    case = accessible_case(actor, case_id)
    require(actor, case, 'finance.read')
    return case


def visible_invoices(actor, rows):
    for row in rows:
        try:
            preparation_access(actor, row.issue.invoice.preparation)
        except (PermissionDenied, ValidationError):
            continue
        yield row


@endpoint(response=obj({'revision': REVISION, 'actions': array(choice(*COMMANDS)), 'effects': array(choice(*RESERVATION_GRANTS)),
    'invoice_corrections': array(ENTRY, limit=15), 'cash_successors': array(ENTRY, limit=15),
    'evidence': array(EVIDENCE, limit=50), 'lots': array(LOT, limit=15), 'next_page': nullable(PAGE)}), query={'page': PAGE},
    summary='List exact correction and successor requests and their independent review and effect status')
def options(request, case_id):
    actor = request.user
    case = case_for(actor, case_id)
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    permission = {'invoice_note': DISPLAY_GRANTS['note'], 'cash_successor': DISPLAY_GRANTS['successor'],
                  'review': DISPLAY_GRANTS['review'], 'apply_successor': DISPLAY_GRANTS['apply_successor'],
                  'reverse_cash': {'finance.cash.reverse'}, 'investigate': DISPLAY_GRANTS['investigate']}
    actions = [action for action, required in permission.items() if required <= grants]
    effects = [effect for effect, grant in RESERVATION_GRANTS.items() if grant in grants]
    if effects:
        actions.append('invoice_effect')
    number = page_number(request)
    offset = (number - 1) * 15
    invoices = InvoiceCorrection.objects.filter(case=case).select_related('issue__invoice__preparation')
    invoice_reviews = FinancialCorrectionReview.objects.filter(correction_id=OuterRef('pk')).order_by('-pk')
    invoice_applied = InvoiceCorrectionAcceptance.objects.filter(correction_id=OuterRef('pk')).values('pk')[:1]
    invoice_rows = list(invoices.annotate(latest=Subquery(invoice_reviews.values('verdict')[:1]),
        applied=Subquery(invoice_applied)).order_by('-pk')[offset:offset + 16])
    successors = CashSuccessor.objects.filter(case=case).defer('payload')
    cash_reviews = FinancialCorrectionReview.objects.filter(successor_id=OuterRef('pk')).order_by('-pk')
    cash_applied = CashSuccessorAcceptance.objects.filter(request_id=OuterRef('pk')).values('pk')[:1]
    cash_rows = list(successors.annotate(latest=Subquery(cash_reviews.values('verdict')[:1]),
        applied=Subquery(cash_applied)).order_by('-pk')[offset:offset + 16])
    kinds = set()
    if 'invoice_note' in actions:
        kinds.update(['invoice_credit_note', 'invoice_debit_note', 'invoice_void_note', 'cash_correction'])
    if 'cash_successor' in actions:
        kinds.update(['cash_report', 'cash_verification', 'cash_correction'])
    if 'review' in actions:
        kinds.add('financial_correction_review')
    if 'reverse_cash' in actions:
        kinds.add('cash_correction')
    proofs = public_evidence(case.evidence.filter(kind__in=kinds)).only('id', 'kind', 'version').order_by('-pk')[:50]
    lots = []
    if grants.intersection(CASH_READERS):
        reversals = CashReversal.objects.filter(lot_id=OuterRef('pk'))
        lots = list(CashVerification.objects.filter(receipt__case=case).only('receipt_id', 'amount').annotate(
            is_reversed=Exists(reversals)).order_by('-pk')[offset:offset + 16])
    return {'revision': case.revision, 'actions': actions, 'effects': effects,
            'invoice_corrections': [request_payload(row, row.issue_id) for row in visible_invoices(actor, invoice_rows[:15])],
            'cash_successors': [request_payload(row, row.parent_id) for row in cash_rows[:15]],
            'evidence': [{'id': proof.pk, 'kind': proof.kind, 'version': proof.version} for proof in proofs],
            'lots': [{'id': lot.pk, 'receipt_id': lot.receipt_id, 'amount': format(lot.amount, 'f'),
                      'reversed': lot.is_reversed} for lot in lots[:15]],
            'next_page': number + 1 if max(len(invoice_rows), len(cash_rows), len(lots)) > 15 and number < PAGE['maximum'] else None}


def request_payload(row, source_id):
    return {'id': row.pk, 'created_at': row.created_at, 'source_id': source_id, 'accepted_id': row.applied,
            'latest_review': row.latest}


def invoice_for(actor, case, issue_id):
    issue = get_object_or_404(InvoiceIssue.objects.select_related('invoice__preparation'), invoice__case=case, pk=issue_id)
    preparation_access(actor, issue.invoice.preparation)
    return issue


def review_subject(actor, case, kind, pk):
    row = financial_reviews.request_for(case, kind, pk)
    if kind == 'invoice':
        preparation_access(actor, row.issue.invoice.preparation)
    return row


@endpoint(response=obj({'id': ID, 'kind': SUBJECT, 'source_id': ID, 'acceptance_id': nullable(ID),
    'reference': TEXT, 'version': nullable(REVISION), 'proposed_amount': nullable(TEXT), 'currency': TEXT,
    'reason': TEXT, 'evidence_id': ID, 'successor_lot_id': nullable(ID), 'delivery_receipt_id': nullable(ID),
    'reviews': array(obj({'id': ID, 'verdict': VERDICT, 'role': ROLE, 'at': DATETIME}), limit=30),
    'jobs': array(obj({'id': ID, 'kind': choice(*RESERVATION_GRANTS), 'status': TEXT}), limit=20)}),
    path_parameters={'kind': SUBJECT}, summary='Read the exact correction decisions, effects and original receipt')
def detail(request, case_id, kind, record_id):
    case = case_for(request.user, case_id)
    row = review_subject(request.user, case, kind, record_id)
    successor = receipt = None
    jobs = []
    if kind == 'invoice':
        acceptance = InvoiceCorrectionAcceptance.objects.filter(correction=row).values_list('pk', flat=True).first()
        receipt = InvoiceCorrectionDelivery.objects.filter(correction=row).values_list('pk', flat=True).first()
        source_id = row.issue_id
        reference, version, currency = row.reference, row.version, row.issue.invoice.currency
        amount = format(row.amount, 'f') if row.amount is not None else None
        history = FinancialCorrectionReview.objects.filter(correction=row)
        jobs = list(InvoiceJob.objects.filter(invoice_id=row.issue.invoice_id, kind__in=RESERVATION_GRANTS,
                                             intent__correction=row.pk).order_by('-pk').values('id', 'kind', 'status')[:20])
    else:
        accepted = CashSuccessorAcceptance.objects.filter(request=row).values_list('pk', 'lot_id').first()
        acceptance, successor = accepted or (None, None)
        source_id = row.parent_id
        reference, version, currency = row.payload['transaction_ref'], None, row.payload['currency']
        amount = row.payload['amount']
        history = FinancialCorrectionReview.objects.filter(successor=row)
    reviews = [{'id': decision.pk, 'verdict': decision.verdict, 'role': decision.role, 'at': decision.created_at}
               for decision in history.only('verdict', 'role', 'created_at').order_by('-pk')[:30]]
    return {'id': row.pk, 'kind': kind, 'source_id': source_id, 'acceptance_id': acceptance,
            'reference': reference, 'version': version, 'proposed_amount': amount, 'currency': currency,
            'reason': row.reason, 'evidence_id': row.evidence_id,
            'successor_lot_id': successor, 'delivery_receipt_id': receipt, 'reviews': reviews, 'jobs': jobs}


@endpoint(method='POST', request={'oneOf': [obj({'action': {'const': key}, 'revision': REVISION, **schema})
    for key, schema in COMMANDS.items()]}, response=obj({'id': ID, 'revision': REVISION}), status=201,
    summary='Apply the exact typed correction, cash-reversal or successor command with native checks')
def command(request, case_id, *, body):
    actor = request.user
    case = case_for(actor, case_id)
    action, revision = body['action'], body['revision']
    args = (actor, case.pk)
    if action == 'invoice_note':
        issue = invoice_for(actor, case, body['issue_id'])
        result = corrections.capture(*args, issue.pk, body['evidence_id'], body['allocation_evidence_id'], body['reason'], revision)
    elif action == 'cash_successor':
        result = cash_successors.capture(*args, body['parent_id'], body['report_evidence_id'],
            body['verification_evidence_id'], body['legal_evidence_id'], body['reason'], revision)
    elif action in {'review', 'investigate'}:
        kind = body['kind']
        target = review_subject(actor, case, kind, body['record_id'])
        if action == 'review':
            result = financial_reviews.review(*args, kind, target.pk, body['role'], body['verdict'],
                                              body['evidence_id'], body['reason'], revision)
        else:
            result = investigator.investigate(*args, kind, target.pk, revision)
    elif action == 'invoice_effect':
        target = review_subject(actor, case, 'invoice', body['record_id'])
        result = corrections.reserve(*args, target.pk, body['effect'], body['role'], revision)
    elif action == 'apply_successor':
        result = cash_successors.apply(*args, body['record_id'], body['role'], revision)
    else:
        if body['target'] == 'allocation':
            allocation = get_object_or_404(CashAllocation.objects.select_related('issue__invoice__preparation'),
                                           lot__receipt__case=case, pk=body['record_id'])
            preparation_access(actor, allocation.issue.invoice.preparation)
        result = cash.reverse(*args, body['target'], body['record_id'], body['role'], body['evidence_id'], body['reason'], revision)
    case.refresh_from_db(fields=['revision'])
    return {'id': result.pk, 'revision': case.revision}


@endpoint(response=obj({'lot_id': ID, 'receipt_id': ID, 'verified_amount': TEXT, 'remaining': TEXT, 'reversed': BOOLEAN,
    'successor_lot_id': nullable(ID), 'allocations': array(obj({'id': ID, 'invoice_id': ID, 'amount': TEXT,
                                                             'reversed': BOOLEAN}), limit=50)}),
    summary='Read a verified cash lot, its exact allocations and recorded successor')
def lot_details(request, case_id, lot_id):
    actor = request.user
    case = case_for(actor, case_id)
    if not active_case_grants(actor, [case.pk], actions=CASH_READERS):
        raise PermissionDenied
    lot = cash.lot_for(case, lot_id)
    reversal = CashReversal.objects.filter(allocation_id=OuterRef('pk'))
    rows = CashAllocation.objects.filter(lot=lot).select_related('issue__invoice__preparation').annotate(
        is_reversed=Exists(reversal)).order_by('-pk')[:50]
    allocations = []
    for row in rows:
        try:
            preparation_access(actor, row.issue.invoice.preparation)
        except (PermissionDenied, ValidationError):
            continue
        allocations.append({'id': row.pk, 'invoice_id': row.issue_id, 'amount': format(row.amount, 'f'), 'reversed': row.is_reversed})
    successor = CashSuccessorAcceptance.objects.filter(parent=lot).values_list('lot_id', flat=True).first()
    return {'lot_id': lot.pk, 'receipt_id': lot.receipt_id, 'verified_amount': format(lot.amount, 'f'),
            'remaining': format(cash.cash_remaining(lot), 'f'), 'reversed': CashReversal.objects.filter(lot=lot).exists(),
            'successor_lot_id': successor, 'allocations': allocations}
