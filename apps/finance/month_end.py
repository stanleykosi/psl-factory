"""Read the current reviewed monthly output without recomputing Finance rules."""
from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import render
from django.utils import timezone

from apps.identity.services import require

from .models import FinancePeriod
from .performance import period_acceptance
from .statement_ppe import recipient_access


class MonthForm(forms.Form):
    month = forms.RegexField(r'\A[0-9]{4}-(?:0[1-9]|1[0-2])\Z', label='Reporting month', max_length=7,
                             widget=forms.DateInput(attrs={'type': 'month'}))


def show(request, case, tabs):
    require(request.user, case, 'finance.read')
    today = timezone.localdate()
    form = MonthForm(request.GET or None, initial={'month': today.strftime('%Y-%m')})
    month = form.initial['month']
    if form.is_bound:
        month = form.cleaned_data['month'] if form.is_valid() else None
    periods = []
    if month:
        current = FinancePeriod.objects.filter(case=case, manifest__period=month, replacement__isnull=True).select_related(
            'case', 'actor', 'run__actor', 'run__source', 'restatement',
        ).order_by('-pk')[:12]
        for period in current:
            try:
                recipient_access(period.run, [request.user.pk])
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
    return render(request, 'design/month_end.html', {
        'case': case, 'tab': 'month-end', 'tabs': tabs, 'periods': periods, 'form': form, 'month': month,
    })
