from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.identity.services import visible_cases

from . import primary_roles as roles


class DefinitionForm(forms.Form):
    name = forms.CharField(max_length=80, label='Role name')
    functions = forms.MultipleChoiceField(label='Workspace access', widget=forms.CheckboxSelectMultiple)
    reason = forms.CharField(max_length=1000, label='Reason for adding this role', widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, configuration, data=None):
        super().__init__(data)
        allowed = set(configuration.value['allowed_actions'])
        self.fields['functions'].choices = [(key, label) for key, (label, actions) in roles.FUNCTIONS.items()
                                             if actions <= allowed]


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def catalogue(request, case_id):
    case = get_object_or_404(visible_cases(request.user), pk=case_id, kind='project')
    form = None
    if request.method == 'POST' or roles.is_admin(request.user, case):
        config = roles.administrator(request.user, case)
        form = DefinitionForm(config, request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            role = roles.create_definition(request.user, case.pk, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, f'{role.name} is available in this workspace.')
            return redirect('staff_primary_roles', case_id=case.pk)
    entries = roles.catalogue(case)
    for item in entries:
        item['access_labels'] = [roles.FUNCTIONS[key][0] for key in item['functions']]
    return render(request, 'identity/primary_roles.html', {'case': case, 'roles': entries, 'form': form})


class AssignmentForm(forms.Form):
    role = forms.CharField(widget=forms.HiddenInput, max_length=50, required=False)
    fingerprint = forms.RegexField(r'\A[a-f0-9]{64}\Z', widget=forms.HiddenInput)
    operation = forms.UUIDField(widget=forms.HiddenInput)
    reason = forms.CharField(max_length=1000, label='Reason for this change', widget=forms.Textarea(attrs={'rows': 3}))
    confirmed = forms.BooleanField(label='I reviewed the access this change adds and removes.')


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def assignment(request, case_id, person_id):
    case = get_object_or_404(visible_cases(request.user), pk=case_id, kind='project')
    reviewed = roles.review(request.user, case, person_id)
    selection = request.POST.get('role') if request.method == 'POST' else request.GET.get('role')
    plan, finding, form = None, None, None
    if selection is not None:
        try:
            plan = roles.proposal(reviewed, selection or None)
        except (ValidationError, PermissionDenied) as error:
            finding = 'This role is unavailable under your current access delegation.' if isinstance(error, PermissionDenied) else error.messages[0]
        else:
            plan['added_labels'] = [roles.ACTION_LABELS[action] for action in plan['added']]
            plan['removed_labels'] = [roles.ACTION_LABELS[action] for action in plan['removed']]
            form = AssignmentForm(initial={'role': selection, 'fingerprint': plan['fingerprint'], 'operation': uuid4()})
            if request.method == 'POST':
                submitted = AssignmentForm(request.POST)
                if submitted.is_valid():
                    values = submitted.cleaned_data
                    try:
                        roles.apply(request.user, case.pk, person_id, values['role'] or None, values['fingerprint'],
                                    values['reason'], values['operation'])
                    except (ValidationError, PermissionDenied) as error:
                        finding = ('Your access delegation changed. Review the role again.'
                                   if isinstance(error, PermissionDenied) else error.messages[0])
                    else:
                        messages.success(request, 'Primary role updated.')
                        return redirect('staff_primary_role', case_id=case.pk, person_id=person_id)
                else:
                    finding = 'Review the access changes, enter a reason and confirm.'
                form.initial['reason'] = request.POST.get('reason', '')[:1000]
    return render(request, 'identity/primary_role_assignment.html', {
        'case': case, 'person': reviewed['person'], 'current': reviewed['current'],
        'roles': reviewed['roles'], 'selection': selection, 'plan': plan, 'finding': finding, 'form': form,
    })
