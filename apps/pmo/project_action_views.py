"""Exact project action ownership and completion through the native meeting service."""
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
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

    def __init__(self, case, state, choices, data=None, *, owner_only=False):
        super().__init__(data, auto_id='reassign_%s' if owner_only else 'id_%s',
                         initial={'revision': case.revision, 'action_revision': state.number,
                                  'owner': state.owner_id, 'due_at': state.due_at})
        self.fields['operation'].choices = choices
        self.fields['evidence'].queryset = public_evidence(case.evidence.all()).order_by('-pk').defer('body')
        if owner_only or any(value == 'assign' for value, _ in choices):
            owners = get_user_model().objects.filter(is_active=True, grant__case=case, grant__action='action.own',
                                                     grant__active=True).distinct().order_by('username')
            self.fields['owner'].queryset = owners.exclude(pk=state.owner_id) if owner_only else owners
        else:
            self.fields.pop('owner')
            self.fields.pop('due_at')
        if owner_only:
            self.fields['operation'].widget = forms.HiddenInput()
            self.initial.update(operation='reassign', owner=None)
            self.fields.pop('due_at')
            self.fields['owner'].label = 'New owner'

    def clean(self):
        values = super().clean()
        if values.get('operation') in {'assign', 'reassign'} and not values.get('owner') and not self.has_error('owner'):
            self.add_error('owner', 'Choose the person who will own this action.')
        return values


def load_action(actor, case_id, item_id):
    case = get_object_or_404(visible_cases(actor), pk=case_id, kind='project')
    require(actor, case, 'meeting.read')
    item = get_object_or_404(ActionItem.objects.select_related('current__owner'), case=case, pk=item_id, current__isnull=False)
    return case, item


def action_options(actor, case, state):
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
    return choices, 'action.manage' in grants, not closed and state.owner_id is not None


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def show(request, case_id, item_id):
    actor = request.user
    case, item = load_action(actor, case_id, item_id)
    state = item.current
    choices, manages, has_open_owner = action_options(actor, case, state)
    posted = request.POST if request.method == 'POST' else None
    changing_owner = posted is not None and posted.get('operation') == 'reassign'
    if changing_owner and not manages:
        require(actor, case, 'action.manage')
    form = ActionForm(case, state, choices, posted if not changing_owner else None) if choices else None
    reassign_form = None
    if manages and has_open_owner:
        reassign_form = ActionForm(case, state, [('reassign', 'Change owner')],
                                   posted if changing_owner else None, owner_only=True)
        if not changing_owner and not reassign_form.fields['owner'].queryset.exists():
            reassign_form = None
    submitted = reassign_form if changing_owner else form
    if changing_owner and submitted is None:
        messages.error(request, 'The action changed. Review its current owner and status.')
    if submitted is not None and submitted.is_bound and submitted.is_valid():
        values = submitted.cleaned_data
        owner = values.get('owner')
        try:
            change_action(actor, case.pk, item.pk, values['operation'], values['evidence'].pk, values['reason'],
                          values['revision'], values['action_revision'], owner.pk if owner else None, values.get('due_at'))
        except ValidationError as exc:
            submitted.add_error(None, exc)
        else:
            messages.success(request, 'Project action updated.')
            return redirect('design_project_action', case.pk, item.pk)
    history = Paginator(item.states.select_related('owner','actor').order_by('-number'),20).get_page(request.GET.get('page'))
    return render(request, 'design/project_action.html', {'case': case, 'item': item, 'state': state, 'form': form,
                                                         'reassign_form': reassign_form, 'timing': action_timing(state),
                                                         'history': history})
