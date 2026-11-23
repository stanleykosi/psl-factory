"""Project Money and Milestones, from exact contract and settlement records."""
from decimal import Decimal, localcontext
from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Exists, OuterRef, Sum
from django.http import Http404
from django.urls import reverse
from django.utils.dateparse import parse_datetime

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import ReadBudget, ReadLimit, limit_queries
from apps.identity.services import require
from apps.pmo.models import Baseline, Milestone
from apps.policy.services import reference_values, resolve

from . import cash, corrections
from .fixed_charge import preparation_access
from .models import BillingCoverage, Invoice, InvoiceIssue


STAGES = {'signed_sow': 'Signed agreement', 'uat': 'User acceptance testing', 'completion': 'Completion'}


def expected_milestone(case, coverage, stage):
    if stage == 'signed_sow':
        return None
    predicate = resolve(f'D12.{stage}_billing_predicate_ref', case)
    if predicate.status == 'ACTIVE':
        rule = reference_values(predicate.configuration)[0]
        if rule['coverage_id'] == coverage.pk:
            return rule['milestone_name']
    return None


def terms(case):
    contract = resolve('D12.contract_version_ref', case)
    if contract.status != 'ACTIVE':
        return {}, None, None, None
    contract_binding = reference_values(contract.configuration)[0]
    baseline = Baseline.objects.filter(case=case, signed_id=contract_binding['signed_evidence_id'],
        signed__sha256=contract_binding['signed_sha256'], signed__in=public_evidence(case.evidence.all())
    ).select_related('signed').first()
    if not baseline:
        return {}, None, None, None
    coverage_id = contract_binding['coverage_id']
    stage_policy = resolve('D12.stage_terms', case)
    configuration = stage_policy.configuration if stage_policy.status == 'ACTIVE' else None
    values = reference_values(configuration) if configuration else []
    rows = {item['stage']: item for item in values if item['coverage_id'] == coverage_id}
    return rows, baseline, coverage_id, configuration


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


def balance(invoice, budget, *, include_sources=True):
    issue = getattr(invoice, 'invoiceissue', None)
    if not issue:
        return None, None, [], []
    accepted = corrections.accepted(issue)
    recorded = cash.allocations(issue=issue)
    entries = budget.take(accepted if include_sources else accepted.only('payload', 'correction__kind'), 75)
    allocations = budget.take(recorded.select_related('lot__receipt').order_by('pk'), 150) if include_sources else []
    with localcontext() as context:
        context.prec = 512
        face = invoice.amount + sum((Decimal(item.payload['signed_delta']) for item in entries), Decimal(0))
        paid = (sum((item.amount for item in allocations), Decimal(0)) if include_sources
                else recorded.aggregate(total=Sum('amount'))['total'] or Decimal(0))
        return paid, face - paid if face >= paid else None, entries, allocations


def projection(actor, case, figure=None, *, include_change_links=False):
    require(actor, case, 'finance.read')
    budget = ReadBudget()
    try:
        with limit_queries(400):
            records, baseline, scope, configuration = terms(case)
            cover = BillingCoverage.objects.filter(case=case, pk=scope).first() if scope else None
            invoices = invoice_rows(actor, case, budget)
            result = build(case, records, baseline, cover, invoices, figure, budget, configuration)
    except ReadLimit:
        return {'rows': [], 'limited': True}
    if include_change_links:
        from apps.pmo.change_stage_links import READ_ACTIONS, decorate, require_access

        require_access(actor, case, READ_ACTIONS)
        decorate(case, result, baseline, cover, configuration)
    return result


def build(case, records, baseline, cover, invoices, figure, budget, configuration):
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

    def add(key, label, amount, currency, completion, attached, sources, *, due_date=None, contract_stage=False,
            missing_reason=None, expected_name=None):
        nonlocal selected
        lines = []
        for invoice in attached:
            paid, owed, corrections_used, allocations = balance(invoice, budget)
            lines.append({'reference': invoice.reference, 'version': invoice.version, 'at': invoice.created_at,
                          'currency': invoice.currency, 'paid': paid, 'owed': owed, 'invoice': invoice,
                          'status': 'Delivered' if hasattr(invoice, 'invoicedelivery') else 'Issued' if paid is not None else 'Draft'})
            if key == figure:
                sources = sources + [{'label': f'Invoice {invoice.reference} · version {invoice.version}', 'url': finance_url,
                                      'record_kind': 'invoice', 'record_id': invoice.pk,
                                      'issue_id': invoice.invoiceissue.pk if hasattr(invoice, 'invoiceissue') else None}]
                sources += [{'label': f'Accepted {item.correction.kind} · {item.correction.reference}',
                             'url': reverse('finance_corrections', args=[case.pk]), 'record_kind': 'correction',
                             'record_id': item.correction_id} for item in corrections_used]
                sources += [{'label': f'Applied receipt {item.lot.receipt.transaction_ref} · {invoice.currency} {item.amount:f}',
                             'url': finance_url, 'record_kind': 'cash-lot', 'record_id': item.lot_id} for item in allocations]
        has_figure = amount is not None or bool(sources)
        item = {'key': key, 'label': label, 'amount': amount, 'currency': currency, 'completion': completion, 'invoices': lines,
                'due_date': due_date, 'contract_stage': contract_stage,
                'url': money_url + '?' + urlencode({'figure': key}) if has_figure else None,
                'sources': sources, 'missing_reason': missing_reason, 'expected_name': expected_name}
        rows.append(item)
        if key == figure and has_figure:
            selected = item

    if cover:
        for stage, label in STAGES.items():
            attached = grouped.get(stage, [])
            expected_name = expected_milestone(case, cover, stage)
            milestones = Milestone.objects.filter(case=case, evidence__in=public_evidence(case.evidence.all()))
            completion = milestones.filter(name=expected_name).first() if expected_name else None
            if not completion:
                completion = milestones.filter(pk__in=[item.preparation.handoff.milestone_id for item in attached
                                                       if item.preparation.handoff_id]).order_by('-completed_at', '-pk').first()
            record = records.get(stage, {})
            sources = [{'label': f'Signed agreement · recorded signature {baseline.signed_id}', 'url': contract_url,
                        'at': baseline.signed.created_at, 'record_kind': 'agreement', 'record_id': baseline.signed_id}]
            if record:
                sources.append({'label': f'Reviewed contract stage terms · version {configuration.revision}',
                                'url': reverse('finance_billing', args=[case.pk]),
                                'at': parse_datetime(configuration.envelope['effective_from']),
                                'record_kind': 'reviewed-terms', 'record_id': configuration.pk})
            if completion:
                sources.append({'label': f'Completion proof · {completion.name}', 'url': reverse('case', args=[case.pk]),
                                'at': completion.completed_at, 'record_kind': 'milestone', 'record_id': completion.pk})
            amount = record.get('amount')
            reason = None
            if amount is None:
                reason = 'The reviewed stage terms do not state an amount.' if record else 'There are no current reviewed terms for this stage.'
            add(stage, label, amount, cover.currency, completion, attached, sources,
                due_date=record.get('due_date'), contract_stage=True, missing_reason=reason, expected_name=expected_name)

    grouped_ids = {item.pk for values in grouped.values() for item in values}
    for invoice in invoices:
        if invoice.pk not in grouped_ids:
            add(f'invoice-{invoice.pk}', invoice.reference, invoice.amount, invoice.currency, None, [invoice],
                [{'label': 'Recorded billing preparation', 'url': reverse('finance_billing', args=[case.pk]),
                  'record_kind': 'preparation', 'record_id': invoice.preparation_id}])
    if figure and selected is None:
        raise Http404('The selected figure is unavailable for this project.')
    return {'rows': rows, 'selected': selected, 'finance_url': finance_url}
