"""Exact project action ownership and completion through the native meeting service."""
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.core.evidence_access import public_evidence
from apps.core.models import Evidence
from apps.identity.services import active_case_grants, require, visible_cases

from .meetings import action_timing, change_action
from .models import ActionItem


class ActionForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    action_revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    operation = forms.ChoiceField(label='Action')
    owner = forms.ModelChoiceField(queryset=get_user_model().objects.none(), required=False, label='Assigned owner')
    due_at = forms.DateTimeField(required=False, label='Deadline', widget=forms.DateTimeInput(
                                 format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}))
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Supporting record')
    reason = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 4}))

    def __init__(self, case, state, choices, data=None):
        super().__init__(data, initial={'revision': case.revision, 'action_revision': state.number,
                                       'owner': state.owner_id, 'due_at': state.due_at})
        self.fields['operation'].choices = choices
        self.fields['evidence'].queryset = public_evidence(case.evidence.all()).order_by('-pk').defer('body')
        if any(value == 'assign' for value, _ in choices):
            self.fields['owner'].queryset = get_user_model().objects.filter(is_active=True, grant__case=case,
                grant__action='action.own', grant__active=True).distinct().order_by('username')
        else:
            self.fields.pop('owner')
            self.fields.pop('due_at')

    def clean(self):
        values = super().clean()
        if values.get('operation') == 'assign' and not values.get('owner'):
            self.add_error('owner', 'Choose the person who will own this action.')
        return values


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def show(request, case_id, item_id):
    actor = request.user
    case = get_object_or_404(visible_cases(actor), pk=case_id, kind='project')
    require(actor, case, 'meeting.read')
    item = get_object_or_404(ActionItem.objects.select_related('current__owner'), case=case, pk=item_id, current__isnull=False)
    state = item.current
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    choices = []
    closed = state.status in {'completed', 'cancelled'}
    if 'action.manage' in grants:
        choices += [('reopen', 'Reopen action')] if closed else [('assign', 'Assign owner and deadline'), ('cancel', 'Cancel action')]
    if state.owner_id == actor.pk and {'action.own', 'action.work'} <= grants:
        if state.status == 'open':
            choices.append(('start', 'Start action'))
        if state.status in {'open', 'in_progress'}:
            choices.append(('complete', 'Complete action'))
    form = ActionForm(case, state, choices, request.POST if request.method == 'POST' else None) if choices else None
    if request.method == 'POST' and form and form.is_valid():
        values = form.cleaned_data
        owner = values.get('owner')
        try:
            change_action(actor, case.pk, item.pk, values['operation'], values['evidence'].pk, values['reason'],
                          values['revision'], values['action_revision'], owner.pk if owner else None, values.get('due_at'))
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Project action updated.')
            return redirect('design_project_action', case.pk, item.pk)
    history = item.states.select_related('owner').order_by('-number')[:20]
    return render(request, 'design/project_action.html', {'case': case, 'item': item, 'state': state, 'form': form,
                                                         'timing': action_timing(state), 'history': history})
