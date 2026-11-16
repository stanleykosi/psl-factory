"""Project Money and Milestones, from exact contract and settlement records."""
from decimal import Decimal, localcontext
from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Exists, OuterRef
from django.http import Http404
from django.urls import reverse

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import ReadBudget, ReadLimit, limit_queries
from apps.identity.services import require
from apps.pmo.models import Baseline
from apps.policy.services import reference_values, resolve

from . import cash, corrections
from .fixed_charge import preparation_access
from .models import BillingCoverage, Invoice, InvoiceIssue


STAGES = {'signed_sow': 'Signed agreement', 'uat': 'User acceptance testing', 'completion': 'Completion'}


def terms(case):
    contract = resolve('D12.contract_version_ref', case)
    stage_policy = resolve('D12.stage_terms', case)
    if contract.status != 'ACTIVE' or stage_policy.status != 'ACTIVE':
        return {}, None, None
    contract_binding = reference_values(contract.configuration)[0]
    baseline = Baseline.objects.filter(case=case, signed_id=contract_binding['signed_evidence_id'],
                                       signed__sha256=contract_binding['signed_sha256']).first()
    if not baseline:
        return {}, None, None
    coverage_id = contract_binding['coverage_id']
    rows = {item['stage']: item for item in reference_values(stage_policy.configuration) if item['coverage_id'] == coverage_id}
    return rows, baseline, coverage_id


def invoice_rows(actor, case, budget):
    issued = InvoiceIssue.objects.filter(obligation_key=OuterRef('obligation_key'))
    current = Invoice.objects.filter(case=case).select_related(
        'preparation__coverage', 'preparation__handoff__milestone', 'invoiceissue', 'invoicedelivery',
    ).filter(invoiceissue__isnull=False)
    drafts = Invoice.objects.filter(case=case).annotate(known_issue=Exists(issued)).filter(known_issue=False)
    current_draft_ids = drafts.order_by('obligation_key', '-version', '-pk').distinct('obligation_key').values('pk')
    drafts = Invoice.objects.filter(pk__in=current_draft_ids).select_related('preparation__coverage', 'preparation__handoff__milestone')
    result = []
    for invoice in budget.take(current.order_by('-pk'), 35) + budget.take(drafts.order_by('-pk'), 35):
        try:
            preparation_access(actor, invoice.preparation)
        except (PermissionDenied, ValidationError):
            continue
        result.append(invoice)
    return result


def balance(invoice, budget):
    issue = getattr(invoice, 'invoiceissue', None)
    if not issue:
        return None, None, [], []
    entries = budget.take(corrections.accepted(issue), 75)
    allocations = budget.take(cash.allocations(issue=issue).select_related('lot__receipt').order_by('pk'), 150)
    with localcontext() as context:
        context.prec = 512
        face = invoice.amount + sum((Decimal(item.payload['signed_delta']) for item in entries), Decimal(0))
        paid = sum((item.amount for item in allocations), Decimal(0))
        return paid, face - paid if face >= paid else None, entries, allocations


def projection(actor, case, figure=None):
    require(actor, case, 'finance.read')
    budget = ReadBudget()
    try:
        with limit_queries(400):
            records, baseline, scope = terms(case)
            cover = BillingCoverage.objects.filter(case=case, pk=scope).first() if scope else None
            invoices = invoice_rows(actor, case, budget)
            return build(case, records, baseline, cover, invoices, figure, budget)
    except ReadLimit:
        return {'rows': [], 'limited': True}


def build(case, records, baseline, cover, invoices, figure, budget):
    rows = []
    selected = None
    finance_url = reverse('finance_settlement', args=[case.pk])
    money_url = reverse('design_project_tab', args=[case.pk, 'money'])
    contract_url = reverse('commercial', args=[case.pk])
    grouped = {}
    for invoice in invoices:
        prep = invoice.preparation
        if cover and prep.coverage_id == cover.pk and prep.kind in STAGES:
            grouped.setdefault(prep.kind, []).append(invoice)

    def add(key, label, amount, currency, completion, attached, sources):
        nonlocal selected
        lines = []
        for invoice in attached:
            paid, owed, corrections_used, allocations = balance(invoice, budget)
            lines.append({'reference': invoice.reference, 'version': invoice.version, 'at': invoice.created_at,
                          'currency': invoice.currency, 'paid': paid, 'owed': owed, 'invoice': invoice,
                          'status': 'Delivered' if hasattr(invoice, 'invoicedelivery') else 'Issued' if paid is not None else 'Draft'})
            if key == figure:
                sources = sources + [{'label': f'Invoice {invoice.reference} · version {invoice.version}', 'url': finance_url}]
                sources += [{'label': f'Accepted {item.correction.kind} · {item.correction.reference}',
                             'url': reverse('finance_corrections', args=[case.pk])} for item in corrections_used]
                sources += [{'label': f'Applied receipt {item.lot.receipt.transaction_ref} · {invoice.currency} {item.amount:f}',
                             'url': finance_url} for item in allocations]
        item = {'label': label, 'amount': amount, 'currency': currency, 'completion': completion, 'invoices': lines,
                'url': money_url + '?' + urlencode({'figure': key}) if amount is not None else None,
                'sources': sources}
        rows.append(item)
        if key == figure and amount is not None:
            selected = item

    if cover:
        for stage, label in STAGES.items():
            attached = grouped.get(stage, [])
            completion = next((item.preparation.handoff.milestone for item in attached if item.preparation.handoff_id), None)
            if completion and not public_evidence(case.evidence.filter(pk=completion.evidence_id)).exists():
                completion = None
            record = records.get(stage, {})
            add(stage, label, record.get('amount'), cover.currency, completion, attached,
                [{'label': f'Signed agreement · recorded signature {baseline.signed_id}', 'url': contract_url},
                 {'label': 'Reviewed contract stage terms', 'url': reverse('finance_billing', args=[case.pk])}] if record else [])

    grouped_ids = {item.pk for values in grouped.values() for item in values}
    for invoice in invoices:
        if invoice.pk not in grouped_ids:
            add(f'invoice-{invoice.pk}', invoice.reference, invoice.amount, invoice.currency, None, [invoice],
                [{'label': 'Recorded billing preparation', 'url': reverse('finance_billing', args=[case.pk])}])
    if figure and selected is None:
        raise Http404('The selected figure is unavailable for this project.')
    return {'rows': rows, 'selected': selected, 'finance_url': finance_url}
