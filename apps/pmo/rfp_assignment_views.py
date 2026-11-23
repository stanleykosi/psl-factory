"""Assign the accountable PM using the currently approved nomination choices."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from apps.core.views import accessible_case

from . import rfp_assignment_queue as queue


class AssignmentForm(forms.Form):
    intake = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    candidate = forms.TypedChoiceField(label='Project manager', coerce=int)
    role = forms.ChoiceField(label='Assignment role')
    evidence = forms.TypedChoiceField(label='Assignment evidence', coerce=int)
    reason = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, bid, roles, people, data=None):
        super().__init__(data, initial={'intake': bid.current_intake_id, 'revision': bid.case.revision,
            'evidence': bid.current_intake.evidence_id})
        self.fields['candidate'].choices = [('', 'Choose a project manager'),
            *((person.pk, person.get_full_name() or person.username) for person in people)]
        self.fields['role'].choices = [(role, role) for role in roles]
        self.fields['evidence'].choices = [(item.pk, f'{item.kind.replace("_", " ").capitalize()} · version {item.version}')
                                          for item in queue.source_choices(bid)]


@login_required
@never_cache
@require_safe
def index(request):
    try:
        data = queue.page(request.user, request.GET.get('cursor'))
    except ValidationError as exc:
        return render(request, 'pmo/rfp_assignment_queue.html', {'page_error': exc.messages[0]}, status=400)
    return render(request, 'pmo/rfp_assignment_queue.html', data)


@login_required
@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def assign(request, case_id):
    case = accessible_case(request.user, case_id)
    try:
        roles, records = queue.assignment_scope(request.user, case)
    except ValidationError:
        return render(request, 'pmo/rfp_assignment.html', {'rules_needed': True, 'case': case})
    bid = get_object_or_404(queue.bids(), case=case)
    current, owner_access_required = queue.assignment_state(bid)
    if current:
        if request.method == 'POST':
            messages.error(request, 'The received bid or its current assignment changed. Open it again.')
        return render(request, 'pmo/rfp_assignment.html', {'bid': bid, 'current': current, 'case': case},
                      status=409 if request.method == 'POST' else 200)
    people = queue.nominees(case, records)
    form = AssignmentForm(bid, roles, people, request.POST if request.method == 'POST' else None)
    status = 422 if request.method == 'POST' else 200
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        candidate = next(person for person in people if person.pk == data['candidate'])
        try:
            queue.assign(request.user, case.pk, data['intake'], candidate, data['role'], data['evidence'],
                         data['reason'], data['revision'])
        except ValidationError as exc:
            form.add_error(None, exc)
            if isinstance(exc, queue.StaleAssignment):
                status = 409
        else:
            messages.success(request, 'Project manager assigned.')
            return redirect('rfp_assignment', case_id=case.pk)
    return render(request, 'pmo/rfp_assignment.html', {'bid': bid, 'form': form, 'has_nominees': bool(people),
                  'owner_access_required': owner_access_required, 'case': case},
                  status=status)
