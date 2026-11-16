"""Review close inputs and recorded receivables at each permitted workspace."""
from calendar import monthrange
from datetime import date
from decimal import Decimal, localcontext

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe

from apps.core.read_budget import ReadBudget, ReadLimit, limit_queries
from apps.core.services import lock_case
from apps.core.workbench import granted
from apps.identity.services import active_case_grants, require
from apps.workflows.factory_definitions import DEFINITIONS
from apps.workflows.factory_views import visible

from .cash import lot_payload
from .fixed_charge import case_access
from .models import BillingPreparation, CashVerification, FinancePeriod, ReceivableSnapshot
from .performance import period_acceptance
from .statement_ppe import recipient_access
from . import receivables


CLOSE_STATIONS = (
    ('finance_performance', 'Monthly figures and restatements', ()),
    ('finance_analysis', 'Accounting preparation and financial reports', ()),
    ('finance_corrections', 'Invoice and cash corrections', ()),
    ('finance_forecast', 'Cash forecasts and actuals', ()),
    ('finance_schedules', 'Income adjustments and schedules', ('schedules.read',)),
    ('ppe', 'Assets and depreciation', ('ppe.read',)),
    ('recognition', 'Project revenue recognition', ('recognition.read',)),
    ('ledger', 'Transaction evidence', ('ledger.read', 'ledger.private.read')),
    ('payroll', 'Restricted payroll and staff costs', ('payroll.read',)),
    ('bu', 'Business unit attribution', ('bu.read',)),
)


class MonthForm(forms.Form):
    month = forms.RegexField(r'\A[1-9][0-9]{3}-(?:0[1-9]|1[0-2])\Z', label='Reporting month', max_length=7,
                             widget=forms.DateInput(attrs={'type': 'month'}))


def selection(request):
    today = timezone.localdate()
    form = MonthForm({'month': request.GET.get('month')} if 'month' in request.GET else None,
                     initial={'month': today.strftime('%Y-%m')})
    month = form.initial['month']
    if form.is_bound:
        month = form.cleaned_data['month'] if form.is_valid() else None
    return form, month


def reviewed_periods(actor, case, month):
    periods = []
    current = FinancePeriod.objects.filter(case=case, manifest__period=month, replacement__isnull=True).select_related(
        'case', 'actor', 'run__actor', 'run__source', 'restatement',
    ).order_by('-pk')[:12]
    for period in current:
        try:
            recipient_access(period.run, [actor.pk])
        except (PermissionDenied, ValidationError):
            continue
        values = []
        try:
            period_acceptance(period)
        except (PermissionDenied, ValidationError):
            status = 'Needs a fresh review'
        else:
            status = 'Reviewed figures'
            company = period.manifest['result']['company']
            contracts = period.manifest['metric_contracts']
            values = [{'label': contracts.get(key, {}).get('label') or key, 'value': row['value'], 'unit': row['unit']}
                      for key, row in company.items()]
        periods.append({'entity': period.manifest['entity'], 'currency': period.manifest['currency'],
                        'at': period.created_at, 'status': status, 'values': values})
    return periods


def show(request, case, tabs):
    require(request.user, case, 'finance.read')
    form, month = selection(request)
    close = workspace_close(request.user, case, month) if month else None
    return render(request, 'design/month_end.html', {
        'case': case, 'tab': 'month-end', 'tabs': tabs, 'periods': close['periods'] if close else [],
        'close': close,
        'form': form, 'month': month,
    })


def cash_received(actor, case, month):
    require(actor, case, 'finance.read')
    budget = ReadBudget()
    with limit_queries(100):
        budget.take(BillingPreparation.objects.filter(case=case, kind='fixed_contract').only('pk'), 50)
        case_access(actor, case)
        verified = CashVerification.objects.filter(receipt__case=case, cashreversal__isnull=True).select_related('receipt', 'successor')
        lots = budget.take(verified.only('amount', 'receipt__payload', 'successor__payload').order_by('pk'), 300)
    groups = {}
    with localcontext() as context:
        context.prec = 512
        for lot in lots:
            fact = lot_payload(lot)
            received = parse_datetime(fact['received_at'])
            if received and timezone.is_aware(received) and timezone.localtime(received).strftime('%Y-%m') == month:
                key = (fact['currency'], fact['amount_basis'])
                groups[key] = groups.get(key, Decimal(0)) + lot.amount
    return [(currency, basis, groups[currency, basis]) for currency, basis in sorted(groups)]


def receivable_cutoff(month, today):
    start = date.fromisoformat(month + '-01')
    if start > today:
        return None
    last = start.replace(day=monthrange(start.year, start.month)[1])
    return min(last, today)


def captured_receivables(actor, case, cutoff):
    """Use an actual capture on the requested date, with a separately labelled earlier fallback."""
    require(actor, case, 'finance.read')
    budget = ReadBudget()
    with limit_queries(120):
        budget.take(BillingPreparation.objects.filter(case=case, kind='fixed_contract').only('pk'), 50)
        case_access(actor, case)
        if cutoff is None:
            return {'status': 'Future month'}
        start = cutoff.replace(day=1)
        row = ReceivableSnapshot.objects.filter(case=case, as_of__range=(start, cutoff)).defer(
            'manifest', 'result').order_by('-as_of', '-pk').first()
        if not row:
            return {'status': 'No receivables capture in this month', 'cutoff': cutoff}
        manifest = budget.load(row, 'manifest')
        result = budget.load(row, 'result')
        if manifest.get('as_of') != row.as_of.isoformat() or receivables.digest({'manifest': manifest, 'result': result}) != row.sha256:
            raise ValidationError('The recorded snapshot could not be verified.')
    scope = ('customer', 'contract', 'currency', 'amount_basis', 'receivable', 'unallocated_cash', 'overdue')
    groups = [{field: group.get(field) for field in scope} for group in result['groups'][:12]]
    categories = {
        'Reported cash awaiting verification': 'reported_unverified',
        'Verified cash awaiting matching': 'unmatched_cash',
        'Draft invoices awaiting issuance': 'unbilled_drafts',
        'Uncertain invoice issuance': 'uncertain_issuance',
        'Pending invoice corrections': 'pending_corrections',
        'Uncertain correction deliveries': 'uncertain_corrections',
        'Pending replacement cash records': 'pending_cash_successors',
        'Reconciliation findings': 'findings',
    }
    exceptions = []
    for label, key in categories.items():
        rows = result.get(key)
        if rows is None:
            continue
        count = sum(not entry.get('reversed') for entry in rows) if key == 'unmatched_cash' else len(rows)
        if count:
            exceptions.append((label, count))
    return {'status': 'Captured on the selected date' if row.as_of == cutoff else 'Earlier capture in this month',
            'cutoff': cutoff, 'date': row.as_of, 'recorded': row.created_at, 'pk': row.pk,
            'groups': groups, 'total_groups': len(result['groups']), 'exceptions': exceptions}


def workspace_close(actor, case, month):
    today = timezone.localdate()
    cutoff = receivable_cutoff(month, today)
    grants = {action for _, action in active_case_grants(actor, [case.pk], actions={
        'finance.receivables', *(action for _, _, actions in CLOSE_STATIONS for action in actions),
    })}
    sections = {'case': case, 'periods': reviewed_periods(actor, case, month), 'cash': [],
                'stations': [(reverse(route, args=[case.pk]), label) for route, label, actions in CLOSE_STATIONS
                             if grants.issuperset(actions)]}
    try:
        sections['cash'] = cash_received(actor, case, month)
    except (PermissionDenied, ValidationError, ReadLimit):
        sections['cash_unavailable'] = True
    try:
        sections['receivables'] = captured_receivables(actor, case, cutoff)
    except (PermissionDenied, ValidationError, ReadLimit):
        sections['receivables'] = {'status': 'Receivables coverage is unavailable in this view'}
    else:
        sections['can_capture'] = cutoff == today and 'finance.receivables' in grants
    return sections


@login_required
@require_POST
@transaction.atomic
def capture(request, case_id):
    case = get_object_or_404(granted(request.user, ['finance.read']), pk=case_id)
    form = MonthForm(request.POST)
    today = timezone.localdate()
    destination = (reverse('design_project_tab', args=[case.pk, 'month-end'])
                   if request.POST.get('return_to') == 'workspace' else reverse('design_company_month_end'))
    if not form.is_valid() or form.cleaned_data['month'] != today.strftime('%Y-%m'):
        messages.error(request, 'Choose the current month to capture today’s receivables.')
        return redirect(destination)
    try:
        case = lock_case(request.user, case.pk, 'finance.receivables', int(request.POST.get('revision', '')))
        case_access(request.user, case)
        receivables.snapshot(request.user, case.pk, today, case.revision)
    except (ValidationError, ValueError) as exc:
        messages.error(request, exc.messages[0] if isinstance(exc, ValidationError) else 'Reload the close view before capturing.')
    else:
        messages.success(request, 'Today’s receivables were captured.')
    return redirect(destination + '?month=' + today.strftime('%Y-%m'))


@login_required
@require_safe
@never_cache
def company(request):
    form, month = selection(request)
    cases = granted(request.user, ['finance.read']).order_by('title', 'pk')
    page = Paginator(cases, 12).get_page(request.GET.get('page'))
    report = []
    coverage = None
    work = []
    if month:
        start = date.fromisoformat(month + '-01')
        report = [workspace_close(request.user, case, month) for case in page]
        coverage = {
            'workspaces': len(report),
            'reviewed': sum(any(period['status'] == 'Reviewed figures' for period in entry['periods']) for entry in report),
            'captured': sum(entry['receivables'].get('date') is not None and
                            entry['receivables']['date'] == entry['receivables']['cutoff'] for entry in report),
            'cash': sum(bool(entry['cash']) for entry in report),
        }
        line_keys = [key for key in DEFINITIONS if key.startswith(('finance-', 'pmo-finance/'))
                     and key not in {'finance-bu/v1', 'finance-payroll/v1'}]
        window = visible(request.user).filter(case_id__in=Subquery(cases.values('pk')), updated_at__year=start.year,
                                              updated_at__month=start.month, definition__in=line_keys)
        for item in window.select_related(None).select_related('case').only(
            'case__title', 'definition', 'status', 'updated_at',
        ).order_by('-updated_at', '-pk')[:26]:
            work.append({'id': item.pk, 'case': item.case, 'title': DEFINITIONS[item.definition]['title'],
                         'state': item.status, 'at': item.updated_at})
    return render(request, 'design/company_month_end.html', {'form': form, 'month': month, 'page': page, 'report': report,
                                                             'coverage': coverage,
                                                             'work': work[:25], 'work_limited': len(work) > 25,
                                                             'as_of': timezone.now()})
