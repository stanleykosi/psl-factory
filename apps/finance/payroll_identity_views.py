"""Exact payroll name checks and private source-holder forms."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods

from apps.core.views import accessible_case
from apps.identity.models import Grant

from . import payroll_identity as service
from .hrfinance_models import HRReadSnapshot
from .payroll_models import PayrollInput


class SourceNameForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    record = forms.IntegerField(min_value=1, label='Source record')
    row = forms.CharField(max_length=100, label='Source row reference')
    name = forms.CharField(max_length=160, strip=False, label='Name in the source')
    reference = forms.CharField(max_length=160, label='Source record reference')


class CheckForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    run = forms.IntegerField(min_value=1, label='Matched payroll sheet')
    input_record = forms.IntegerField(min_value=1, label='Original payroll input')
    row = forms.CharField(max_length=100, label='Payroll row reference')


class CorrectionForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    comparison = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


@login_required
@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
@sensitive_post_parameters()
@sensitive_variables()
def workbench(request, case_id):
    case = accessible_case(request.user, case_id)
    actor = request.user
    grants = set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True))
    if not grants.intersection({'payroll.read', 'hrfinance.read'}):
        raise PermissionDenied
    form_values = {'revision': case.revision}
    path = reverse('payroll_name_checks', args=[case.pk])
    try:
        _, selection = service.rule(case)
    except ValidationError:
        selection = None
    nominated = selection and actor.pk in selection['reader_ids'] and 'payroll.private.read' in grants
    commands = {}
    if selection and 'evidence.add' in grants:
        if {'payroll.read', 'payroll.capture'} <= grants and PayrollInput.objects.filter(
                request__case=case, actor=actor, metadata__accepted=True).exists():
            commands['payroll'] = SourceNameForm(initial=form_values, auto_id='payroll_name_%s')
        if {'hrfinance.read', 'hrfinance.capture'} <= grants and HRReadSnapshot.objects.filter(
                contract__need__case=case, contract__payload__purpose='payroll_matching', actor=actor,
                status='accepted').exists():
            commands['hr'] = SourceNameForm(initial=form_values, auto_id='hr_name_%s')
            commands['hr'].fields['row'].label = 'Exact staff ID in the HR source'
    if nominated:
        commands['check'] = CheckForm(initial={**form_values, 'run': request.GET.get('run', '')}, auto_id='name_check_%s')
        if 'payroll.hr_correction' in grants:
            commands['route'] = CorrectionForm(initial=form_values)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action not in commands:
            raise PermissionDenied
        form = type(commands[action])(request.POST)
        if set(request.POST) - set(form.fields) - {'action', 'csrfmiddlewaretoken'} or not form.is_valid():
            messages.error(request, 'Check the selected record and supply the required fields.')
            return redirect(path)
        values = form.cleaned_data
        try:
            if action == 'check':
                result = service.check(actor, case.pk, values['run'], values['input_record'], values['row'], values['revision'])
                return redirect(f'{path}?check={result.pk}')
            if action == 'route':
                service.route(actor, case.pk, values['comparison'], values['revision'])
                return redirect(f'{path}?check={values["comparison"]}')
            service.capture(actor, case.pk, action, values['record'], values['row'], values['name'],
                            values['reference'], values['revision'])
            messages.success(request, 'Private source evidence recorded.')
        except ValidationError:
            messages.error(request, 'Check the current source, required authority and work version.')
        return redirect(path)

    comparison = None
    if nominated and 'check' in request.GET:
        try:
            comparison_id = forms.IntegerField(min_value=1).clean(request.GET['check'])
            comparison = service.readback(actor, case.pk, comparison_id)
        except ValidationError:
            messages.error(request, 'The checked sources changed or are unavailable.')
        else:
            if 'route' in commands:
                commands['route'].initial['comparison'] = comparison['id']
    return render(request, 'finance/payroll_name_checks.html', {
        'case': case, 'commands': commands, 'enabled': bool(selection), 'comparison': comparison,
        'can_configure': {'policy.read', 'policy.configure'} <= grants,
    })
