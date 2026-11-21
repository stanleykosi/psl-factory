from decimal import Decimal
from urllib.parse import urlencode
from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.core.views import accessible_case
from apps.identity.services import active_case_grants, require
from apps.policy.services import decision_authority
from . import forecast, forecast_actuals
from .models import ForecastScenario


class ActualCommand(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


def choices(rows, label):
    return forms.TypedChoiceField(coerce=int, choices=rows, label=label)


def proof_field(case, kind):
    records = case.evidence.filter(kind=kind).order_by('-pk').values_list('pk', 'version', 'source')[:50]
    return choices([(pk, f'{source} · version {version}') for pk, version, source in records], 'Exact source evidence')


def actual_label(actual):
    return f'{actual.transaction} · {actual.payload["account"]} · {actual.payload["occurred_on"]}'


def current_roles(actor, case, policy):
    roles = []
    for role in policy.get('actual_roles', ()):
        try:
            decision_authority(actor, case, role)
        except (PermissionDenied, ValidationError):
            continue
        roles.append((role, role))
    return roles


def commands(actor, case, projection, submitted, selected):
    actions = {action for _, action in active_case_grants(actor, [case.pk], actions={
        'finance.forecast.actual', 'finance.forecast.actual_verify', 'finance.forecast.match',
    })}
    definitions = {}
    policy = {}
    controlled = actions.intersection({'finance.forecast.match', 'finance.forecast.actual_verify'})
    if controlled:
        try:
            _, policy = forecast.method(case)
        except ValidationError:
            pass
    item_choices = [(row['item']['key'], row['item']['source_ref']) for row in projection['rows']]
    actuals = projection['actuals']
    if 'finance.forecast.match' in actions and item_choices and actuals:
        definitions['note'] = ('Leave unmatched with a note', {
            'item': forms.ChoiceField(choices=item_choices, label='Forecast item'),
            'actual': choices([(a.pk, actual_label(a)) for a in actuals], 'Recorded actual'),
            'reason': forms.CharField(max_length=4000, label='Why leave this actual unmatched?',
                                      widget=forms.Textarea(attrs={'rows': 2})),
        })
        verified = [(a.pk, actual_label(a)) for a in actuals if a.lot_id or a.independently_verified]
        if policy and verified:
            definitions['match'] = ('Match actual', {
                'item': forms.ChoiceField(choices=item_choices, label='Forecast item'),
                'actual': choices(verified, 'Verified actual'),
                'amount': forms.DecimalField(min_value=Decimal('0.00000001'), max_digits=32, decimal_places=8,
                                             label='Amount to match'),
                'evidence': proof_field(case, 'forecast_match'),
                'operation': forms.RegexField(r'^forecast-match-[a-f0-9]{32}$', widget=forms.HiddenInput),
            })
    if policy and 'finance.forecast.match' in actions:
        links = [(m.pk, f'{m.item_key} · {actual_label(m.actual)}') for m in projection['history'] if not hasattr(m, 'reversal')]
        if links:
            definitions['unmatch'] = ('Reverse a match', {
                'match': choices(links, 'Recorded match'),
                'evidence': proof_field(case, 'forecast_match'),
                'reason': forms.CharField(max_length=4000, label='Why reverse this match?',
                                          widget=forms.Textarea(attrs={'rows': 2})),
            })
    if policy and 'finance.forecast.actual_verify' in actions:
        pending = [(a.pk, actual_label(a)) for a in actuals
                   if not a.lot_id and not a.independently_verified and a.payload['amount'] is not None
                   and (not policy['distinct_actual_reporter'] or a.actor_id != actor.pk)]
        roles = current_roles(actor, case, policy)
        if pending and roles:
            definitions['verify'] = ('Verify reported actual', {
                'actual': choices(pending, 'Reported actual'),
                'role': forms.ChoiceField(choices=roles, label='Your verification role'),
                'evidence': proof_field(case, 'forecast_actual_verification'),
            })
    result = {}
    for action, (label, fields) in definitions.items():
        initial = {'revision': case.revision}
        if action == 'match':
            initial['operation'] = 'forecast-match-' + uuid4().hex
        form = ActualCommand(submitted if selected == action else None, initial=initial, auto_id=f'{action}_%s')
        form.fields.update(fields)
        result[action] = {'action': action, 'label': label, 'form': form}
    return result, 'finance.forecast.actual' in actions, bool(controlled and not policy)


def apply(actor, case, scenario, month, action, values):
    expected = values['revision']
    if action == 'note':
        forecast_actuals.leave_unmatched(actor, case.pk, scenario.pk, month, values['item'], values['actual'],
                                         values['reason'], expected)
        return 'Unmatched note recorded on the exact forecast item and actual.'
    if action == 'match':
        forecast.match(actor, case.pk, scenario.pk, values['item'], values['actual'], format(values['amount'], 'f'),
                       values['operation'], values['evidence'], expected)
        return 'Actual matched to the selected forecast item.'
    if action == 'unmatch':
        forecast.unmatch(actor, case.pk, values['match'], values['evidence'], values['reason'], expected)
        return 'Match reversed. The original stays in history.'
    forecast.verify_actual(actor, case.pk, values['actual'], values['role'], values['evidence'], expected)
    return 'The reported actual has been verified.'


@login_required
@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def workspace(request, case_id, scenario_id):
    actor = request.user
    case = accessible_case(actor, case_id)
    require(actor, case, 'finance.read')
    scenario = get_object_or_404(ForecastScenario, case=case, pk=scenario_id)
    months = scenario.payload['months']
    current_month = timezone.localdate().isoformat()[:7]
    month = request.GET.get('month', current_month if current_month in months else months[0])
    if month not in months:
        raise Http404('Forecast month unavailable.')

    projection = forecast_actuals.monthly(actor, case, scenario, month)
    selected = request.POST.get('action', '') if request.method == 'POST' else None
    available, can_report, rules_needed = commands(actor, case, projection, request.POST, selected)
    if selected is not None:
        if selected not in available:
            raise PermissionDenied('This forecast action is unavailable to the current account.')
        form = available[selected]['form']
        if form.is_valid():
            try:
                message = apply(actor, case, scenario, month, selected, form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, message)
                path = reverse('finance_forecast_actuals', args=[case.pk, scenario.pk])
                return redirect(f'{path}?{urlencode({"month": month})}')
    return render(request, 'finance/forecast_actuals.html', {
        'case': case, 'scenario': scenario, 'months': months, 'month': month, 'projection': projection,
        'commands': available.values(), 'can_report': can_report, 'rules_needed': rules_needed,
    })
