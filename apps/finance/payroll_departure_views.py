"""Restricted source holder and review screens for payroll timing."""

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods

from apps.core.models import Audit, Evidence
from apps.core.views import accessible_case
from apps.identity.models import Grant
from apps.policy.payroll_validators import DEPARTURE_CHECK, DEPARTURE_SOURCES

from . import payroll_departure as service


class VersionForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class SourceForm(VersionForm):
    episode = forms.CharField(max_length=100, strip=False, label='Employment record reference')
    status = forms.ChoiceField(label='Source status')
    instant = forms.CharField(max_length=40, required=False, label='Recorded date and time',
        help_text='Enter the year, month, day and time with the time-zone offset recorded by the source. Leave blank if unknown.')
    source_reference = forms.CharField(max_length=100, strip=False, label='Exact source reference')
    source_version = forms.CharField(max_length=100, strip=False, label='Source version')


class EmploymentForm(SourceForm):
    employee = forms.CharField(max_length=100, strip=False, label='Staff ID in the HR source')
    status = forms.ChoiceField(label='Employment status', choices=[('ended', 'Ended'), ('unknown', 'Unknown')])


class SettlementForm(SourceForm):
    input_id = forms.IntegerField(min_value=1, max_value=2**63-1, label='Original payroll input')
    row = forms.CharField(max_length=100, strip=False, label='Exact payroll row reference')
    status = forms.ChoiceField(label='Payment status', choices=[(value, value.capitalize())
        for value in service.STATUSES['settlement']])


class CheckForm(VersionForm):
    settlement_id = forms.IntegerField(min_value=1, max_value=2**63-1, label='Settlement evidence number')


class ReviewForm(VersionForm):
    check_id = forms.IntegerField(min_value=1, max_value=2**63-1, widget=forms.HiddenInput)


class SourceContractForm(VersionForm):
    side = forms.ChoiceField(label='Source', choices=[('employment', 'Employment records'),
                                                      ('settlement', 'Confirmed payments')])
    document_ref = forms.CharField(max_length=100, strip=False, label='Approved source document reference')


class EvidenceChoice(forms.ModelChoiceField):
    def label_from_instance(self, evidence):
        return f'Evidence {evidence.pk}, version {evidence.version}'


class RuleForm(VersionForm):
    mode = forms.ChoiceField(label='Payment timing rule', choices=[('', 'Choose a rule'),
        ('check', 'Compare settlement with the exact departure time'), ('off', 'Leave this check off')])
    entity = forms.CharField(max_length=100, strip=False, required=False, label='Employer reference')
    employment_holder_id = forms.ModelChoiceField(queryset=None, required=False, label='Person who confirms departures')
    settlement_holder_id = forms.ModelChoiceField(queryset=None, required=False, label='Person who confirms payments')
    reviewer_id = forms.ModelChoiceField(queryset=None, required=False, label='HR reviewer')
    reader_ids = forms.ModelMultipleChoiceField(queryset=None, required=False, label='People who can compare the sources')
    employment_contract_id = EvidenceChoice(queryset=None, required=False, label='Approved employment source')
    settlement_contract_id = EvidenceChoice(queryset=None, required=False, label='Approved payment source')
    proof_hours = forms.IntegerField(required=False, min_value=1, label='Hours source evidence remains current')
    decision = EvidenceChoice(queryset=None, label='Recorded owner decision')
    effective_from = forms.DateTimeField(label='Effective from')

    def __init__(self, case, *args, **kwargs):
        super().__init__(*args, **kwargs)
        people = get_user_model().objects.filter(is_active=True, grant__case=case, grant__action='case.read',
                                                 grant__active=True).order_by('username')
        for key in ('employment_holder_id', 'settlement_holder_id', 'reviewer_id', 'reader_ids'):
            self.fields[key].queryset = people
        for side, kind in DEPARTURE_SOURCES.items():
            latest = case.evidence.filter(kind=kind).order_by('-version').values('pk')[:1]
            self.fields[side + '_contract_id'].queryset = Evidence.objects.filter(pk__in=latest).only('version')
        self.fields['decision'].queryset = case.evidence.filter(kind='policy_decision').only('version').order_by('-pk')

    def content(self):
        values = self.cleaned_data
        if values['mode'] == 'off':
            return {'check': None}
        chosen = ('employment_holder_id', 'settlement_holder_id', 'reviewer_id',
                  'employment_contract_id', 'settlement_contract_id')
        if not values['entity'] or not values['proof_hours'] or not values['reader_ids'] or not all(values[key] for key in chosen):
            raise ValidationError('Choose the employer, both approved sources, the responsible people and an evidence lifetime.')
        return {'check': {**{field: values[field].pk for field in chosen}, 'entity': values['entity'],
                          'comparison': 'settlement_after_effective_instant',
                          'reader_ids': sorted(user.pk for user in values['reader_ids']),
                          'proof_max_age_seconds': values['proof_hours'] * 3600}}


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
    path = reverse('payroll_departure_check', args=[case.pk])
    try:
        policy, scope = service.rule(case)
    except ValidationError:
        policy, scope = None, None
    forms_by_action = {}
    initial = {'revision': case.revision}
    can_configure = {'policy.read', 'policy.configure'} <= grants
    if can_configure:
        forms_by_action['policy'] = RuleForm(case, initial=initial, auto_id='rule_%s')
        if 'evidence.add' in grants:
            forms_by_action['source'] = SourceContractForm(initial=initial, auto_id='source_%s')
    compare = review = False
    if scope:
        compare = actor.pk in scope['reader_ids'] and set(service.CHECK_GRANTS) <= grants
        review = actor.pk == scope['reviewer_id'] and set(service.REVIEW_GRANTS) <= grants
        for side, form_type in (('employment', EmploymentForm), ('settlement', SettlementForm)):
            if actor.pk == scope[side + '_holder_id'] and set(service.HOLDER_GRANTS[side]) <= grants:
                forms_by_action[side] = form_type(initial=initial, auto_id=side + '_%s')
        if compare:
            forms_by_action['check'] = CheckForm(initial=initial, auto_id='check_%s')
        if review:
            forms_by_action['review'] = ReviewForm(initial=initial)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action not in forms_by_action:
            raise PermissionDenied
        form = RuleForm(case, request.POST) if action == 'policy' else type(forms_by_action[action])(request.POST)
        if set(request.POST) - set(form.fields) - {'action', 'csrfmiddlewaretoken'} or not form.is_valid():
            messages.error(request, 'Check the required values and open the current work again.')
            return redirect(path)
        values = form.cleaned_data
        expected = values.pop('revision')
        try:
            if action == 'source':
                record = service.record_source_contract(actor, case.pk, expected=expected, **values)
                messages.success(request, f'Approved source reference {record.pk} recorded.')
                return redirect(path)
            if action == 'policy':
                service.draft_rule(actor, case.pk, form.content(), values['decision'].pk, values['effective_from'], expected)
                messages.success(request, 'Rule draft saved. Review and activate it before using it.')
                return redirect(path)
            if action == 'check':
                record = service.check(actor, case.pk, values['settlement_id'], expected)
                return redirect(f'{path}?check={record.pk}')
            if action == 'review':
                service.acknowledge(actor, case.pk, values['check_id'], expected)
                return redirect(f'{path}?check={values["check_id"]}')
            values['instant'] = values['instant'] or None
            record = service.capture(actor, case.pk, action, expected=expected, **values)
            messages.success(request, f'Private source evidence {record.pk} recorded.')
        except ValidationError:
            messages.error(request, 'Check the selected sources, exact date and current work version.')
        return redirect(path)

    comparison, recent, settlements = None, (), ()
    if compare or review:
        recent = Audit.objects.filter(case=case, action=service.CHECK, data__policy=policy).order_by('-pk') \
            .values_list('pk', flat=True)[:15]
        if 'check' in request.GET:
            try:
                check_id = forms.IntegerField(min_value=1, max_value=2**63-1).clean(request.GET['check'])
                comparison = service.readback(actor, case.pk, check_id)
            except ValidationError:
                messages.error(request, 'The selected finding needs a current check before it can be opened.')
            else:
                if review:
                    forms_by_action['review'].initial['check_id'] = comparison['id']
        if compare:
            settlements = service.facts(case, policy, 'settlement').order_by('-pk').values_list('pk', flat=True)[:15]
    return render(request, 'finance/payroll_departure.html', {'case': case, 'commands': forms_by_action,
        'configured': scope is not None, 'comparison': comparison, 'recent': recent, 'settlements': settlements})
