from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.models import Case
from apps.core.presentation import workspace_name
from .factory_progress import set_progress


class StartWithBackground(forms.Form):
    background = forms.BooleanField(required=False, initial=True, disabled=True, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        workspace = self.fields.get('case')
        if isinstance(workspace, forms.ModelChoiceField) and workspace.queryset.model is Case:
            workspace.label = workspace.label or 'Workspace'
            workspace.label_from_instance = workspace_name


def enroll(request, work, background):
    if background:
        try:
            set_progress(request.user, work.pk, work.revision, True, initial=True)
        except (ValidationError, PermissionDenied):
            messages.info(request, 'Work was recorded. Check its current owner or recovery step before continuing in background.')


def started(request, work, background):
    enroll(request, work, background)
    return redirect('factory_detail', work_id=work.pk)


@transaction.atomic
def start_work(request, submit, background):
    return started(request, submit(), background)


class ProgressForm(forms.Form):
    revision = forms.IntegerField(min_value=1)
    action = forms.ChoiceField(choices=[('continue', 'Continue'), ('pause', 'Pause')])


@login_required
@require_POST
def change(request, work_id):
    from .factory_views import visible, work_queue_params

    work = get_object_or_404(visible(request.user, work_id=work_id))
    form = ProgressForm(request.POST)
    if form.is_valid():
        values = form.cleaned_data
        try:
            set_progress(request.user, work_id, values['revision'], values['action'] == 'continue')
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    else:
        messages.error(request, 'Open the current work item and choose a background action.')
    target = reverse('factory_detail', args=[work.pk])
    if {'queue', 'q', 'line'}.intersection(request.GET):
        target += '?' + urlencode(work_queue_params(request.GET, work=work))
    return redirect(target)
