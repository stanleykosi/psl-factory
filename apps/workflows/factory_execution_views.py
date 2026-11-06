"""Reviewed work-owner recovery, using existing policy and domain authority."""
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from apps.core.models import Evidence
from apps.core.services import lock_case
from apps.identity.services import require, visible_cases
from apps.policy.document_validators import ROLES
from apps.policy.factory_recovery_validators import COMPONENT, METHOD
from apps.policy.models import Configuration
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import reference_values, transition
from . import factory_execution as recovery
from .factory_definitions import DEFINITIONS


def versions(case):
    return Configuration.objects.filter(case=case, component=COMPONENT).order_by('-revision')


class RecoveryRuleForm(forms.Form):
    base = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    definition = forms.ChoiceField(label='Work type', choices=[(k, v['title']) for k, v in DEFINITIONS.items()])
    method = forms.ChoiceField(required=False, label='Recovery method', choices=[('', 'Not decided'), (METHOD, 'Reviewed replacement worker')])
    principal_id = forms.ModelChoiceField(queryset=get_user_model().objects.none(), required=False, label='Replacement worker')
    reviewer_id = forms.ModelChoiceField(queryset=get_user_model().objects.none(), required=False, label='Accountable reviewer')
    review_role = forms.ChoiceField(required=False, label='Reviewer responsibility', choices=[('', 'Not decided'), *[(r, r) for r in ROLES]])
    independent_of_worker = forms.ChoiceField(required=False, label='Must the reviewer be a different person?', choices=[('', 'Not decided'), ('yes', 'Yes'), ('no', 'No')])
    valid_from = forms.CharField(required=False, label='Authority starts', help_text='Include the timezone, for example 2026-11-04T09:00:00+01:00. Leave undecided values blank.')
    valid_until = forms.CharField(required=False, label='Authority ends')
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Recorded configuration decision')

    def __init__(self, case, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Discovery only; the typed validator checks each nominee's exact work-type permissions.
        for field, action in [('principal_id', 'factory.execute'), ('reviewer_id', 'factory.manage')]:
            people = get_user_model().objects.filter(is_active=True)
            for grant in ['case.read', 'factory.read', action]:
                people = people.filter(grant__case=case, grant__active=True, grant__action=grant)
            self.fields[field].queryset = people.distinct().order_by('username')
        self.fields['evidence'].queryset = Evidence.objects.filter(case=case, kind='policy_decision').order_by('-pk')

    def rule(self):
        value = {k: self.cleaned_data[k] or None for k in ['definition', 'method', 'review_role', 'valid_from', 'valid_until']}
        for key in ['principal_id', 'reviewer_id']:
            person = self.cleaned_data[key]
            value[key] = person.pk if person else None
        value['independent_of_worker'] = {'': None, 'yes': True, 'no': False}[self.cleaned_data['independent_of_worker']]
        return value


@transaction.atomic
def save_rule(actor, case, form):
    lock_case(actor, case.pk, 'policy.configure')
    latest = versions(case).first()
    if form.cleaned_data['base'] != (latest.pk if latest else 0):
        raise ValidationError('Settings changed. Reload and review the latest version before saving.')
    rules = []
    if latest:
        recovery.origin_access(actor, latest)
        rules = reference_values(latest)[0]['rules']
    rule = form.rule()
    rules = [r for r in rules if r['definition'] != rule['definition']] + [rule]
    return draft_operator_policy(actor, case.pk, COMPONENT, {'rules': rules}, form.cleaned_data['evidence'].pk, timezone.now())


@login_required
@require_http_methods(['GET', 'POST'])
def configuration(request, case_id):
    case = get_object_or_404(visible_cases(request.user), pk=case_id)
    for action in ['case.read', 'factory.read', 'policy.configure']:
        require(request.user, case, action)
    latest = versions(case).first()
    form = RecoveryRuleForm(case, request.POST if request.method == 'POST' and request.POST.get('action') == 'draft' else None,
                            initial={'base': latest.pk if latest else 0})
    if request.method == 'POST':
        if request.POST.get('action') == 'draft' and form.is_valid():
            try:
                save_rule(request.user, case, form)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'Recovery draft saved. Review and activate it separately.')
                return redirect(request.path)
        elif request.POST.get('action') == 'transition':
            config = get_object_or_404(versions(case), pk=request.POST.get('configuration') if request.POST.get('configuration', '').isdigit() else 0)
            recovery.origin_access(request.user, config)
            try:
                transition(request.user, config.pk, request.POST.get('state'))
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
            return redirect(request.path)
    history = list(versions(case).prefetch_related('states'))
    for config in history:
        recovery.origin_access(request.user, config)
        config.rules = reference_values(config)[0]['rules']
        config.current_state = config.states.order_by('-pk').first().state
    try:
        require(request.user, case, 'policy.activate')
        can_activate = True
    except PermissionDenied:
        can_activate = False
    response = render(request, 'factory/execution_configuration.html', {'case': case, 'form': form, 'versions': history, 'can_activate': can_activate})
    response['Cache-Control'] = 'no-store'
    return response


class ReviewForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Recorded authority decision')
    reason = forms.CharField(max_length=2000, widget=forms.Textarea, label='Why should this worker take over?')


@login_required
@require_http_methods(['GET', 'POST'])
def review(request, work_id):
    from .factory_views import visible
    from .factory import access
    work = get_object_or_404(visible(request.user).select_related('case', 'actor', 'execution_binding'), pk=work_id)
    access(request.user, work.case, 'factory.manage', work.definition)
    form = ReviewForm(request.POST if request.method == 'POST' else None, initial={'revision': work.revision})
    form.fields['evidence'].queryset = Evidence.objects.filter(case=work.case, kind='policy_decision').order_by('-pk')
    proposal = None
    try:
        config, rule, worker, reviewer = recovery.qualified_rule(work)
        recovery.origin_access(request.user, config)
        proposal = {'worker': worker, 'reviewer': reviewer, 'until': rule['valid_until'], 'revision': config.revision}
    except (ValidationError, PermissionDenied):
        pass
    if request.method == 'POST' and form.is_valid():
        try:
            recovery.bind(request.user, work.pk, form.cleaned_data['revision'], form.cleaned_data['evidence'].pk, form.cleaned_data['reason'])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Reviewed worker assigned. Existing decisions, allowance and original operations are preserved.')
            return redirect('factory_detail', work_id=work.pk)
    response = render(request, 'factory/execution_review.html', {'case': work.case, 'work': work, 'form': form, 'proposal': proposal,
                                                               'can_review': proposal is not None and proposal['reviewer'].pk == request.user.pk})
    response['Cache-Control'] = 'no-store'
    return response
