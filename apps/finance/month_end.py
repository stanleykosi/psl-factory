"""Read the current reviewed monthly output without recomputing Finance rules."""
from datetime import date
from decimal import Decimal, localcontext

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Subquery
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from apps.core.read_budget import ReadBudget, ReadLimit, limit_queries
from apps.core.workbench import granted
from apps.identity.services import require
from apps.workflows.factory_definitions import DEFINITIONS
from apps.workflows.factory_views import visible

from .cash import lot_payload
from .fixed_charge import case_access
from .models import BillingPreparation, CashVerification, FinancePeriod
from .performance import period_acceptance
from .statement_ppe import recipient_access


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
    return render(request, 'design/month_end.html', {
        'case': case, 'tab': 'month-end', 'tabs': tabs, 'periods': reviewed_periods(request.user, case, month) if month else [],
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


@login_required
@require_safe
@never_cache
def company(request):
    form, month = selection(request)
    cases = granted(request.user, ['finance.read']).order_by('title', 'pk')
    page = Paginator(cases, 12).get_page(request.GET.get('page'))
    report = []
    work = []
    if month:
        start = date.fromisoformat(month + '-01')
        for case in page:
            figures = {'case': case, 'periods': reviewed_periods(request.user, case, month), 'cash': []}
            try:
                figures['cash'] = cash_received(request.user, case, month)
            except (PermissionDenied, ValidationError, ReadLimit):
                figures['cash_unavailable'] = True
            report.append(figures)
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
                                                             'work': work[:25], 'work_limited': len(work) > 25,
                                                             'as_of': timezone.now()})
