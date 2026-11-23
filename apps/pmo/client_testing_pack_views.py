from io import BytesIO
from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from adapters import case_uploads, client_uat as contract
from apps.agents.models import CaseUpload
from apps.core.views import accessible_case

from . import client_testing_pack as pack, client_uat
from .clocks import aware
from .models import DeliveryDossier


class TargetCommand(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    target = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class RecordPack(TargetCommand):
    key = forms.UUIDField(widget=forms.HiddenInput)
    pack_file = forms.ModelChoiceField(queryset=None, label='Test pack sent to the client')
    receipt_file = forms.ModelChoiceField(queryset=None, label='Separate proof of delivery')
    reference = forms.CharField(max_length=160, label='Original delivery receipt reference')
    received_at = forms.DateTimeField(label='Actual delivery time',
                                     widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}))

    def __init__(self, actor, case, *args, **kwargs):
        super().__init__(*args, **kwargs)
        files = CaseUpload.objects.filter(case=case, actor=actor).order_by('-pk')
        available = files.filter(pk__in=files.values('pk')[:50]).order_by('-pk')
        for field in (self.fields['pack_file'], self.fields['receipt_file']):
            field.queryset = available
            field.label_from_instance = lambda file: file.name


class VerifyPack(TargetCommand):
    row = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    checked = forms.BooleanField(label='I checked the pack, client, version and original delivery proof')
    note = forms.CharField(max_length=2000, label='What confirmed delivery?', widget=forms.Textarea(attrs={'rows': 2}))


class ReminderDates(TargetCommand):
    row = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    previous = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)
    key = forms.UUIDField(widget=forms.HiddenInput)
    reply_due_at = forms.DateTimeField(label='Client response due',
                                     widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}))
    remind_at = forms.DateTimeField(label='Remind me to follow up', required=False,
                                  widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}))
    reason = forms.CharField(max_length=2000, label='Reason for these dates', widget=forms.Textarea(attrs={'rows': 2}))


def visible_dossier(request, case_id, dossier_id):
    case = accessible_case(request.user, case_id)
    client_uat.readable(request.user, case)
    dossier = get_object_or_404(DeliveryDossier.objects.select_related('candidate__requirements', 'case'),
                               case=case, pk=dossier_id)
    return case, dossier, client_uat.head(dossier, contract.TARGET)


@login_required
@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def desk(request, case_id, dossier_id):
    case, dossier, target = visible_dossier(request, case_id, dossier_id)
    state = pack.projection(request.user, dossier, target)
    row = state.get('pack')
    action = request.POST.get('action') if request.method == 'POST' else None
    initial = {'revision': case.revision, 'target': target.pk if target else None, 'key': uuid4()}
    try:
        client_uat.witness(request.user, case)
        can_record = bool(target and not state.get('client_replied'))
    except (PermissionDenied, ValidationError):
        can_record = False
    try:
        can_review = bool(row and pack.review_context(request.user, row))
    except (PermissionDenied, ValidationError):
        can_review = False
    timing = state.get('timing')
    record_form = RecordPack(request.user, case, request.POST if action == 'record' else None, initial=initial) if can_record else None
    review_form = (VerifyPack(request.POST if action == 'verify' else None, initial={**initial, 'row': row.pk})
                   if can_review and not state.get('review') else None)
    schedule_form = None
    if row and state.get('review') and can_record:
        schedule_initial = {**initial, 'row': row.pk, 'previous': state.get('previous')}
        if timing:
            schedule_initial.update(reply_due_at=aware(timing.payload['reply_due_at']),
                                    remind_at=aware(timing.payload['remind_at']) if timing.payload['remind_at'] else None)
        schedule_form = ReminderDates(request.POST if action == 'schedule' else None, initial=schedule_initial)
    if action:
        form = {'record': record_form, 'verify': review_form, 'schedule': schedule_form}.get(action)
        if form is None:
            raise PermissionDenied
        if form.is_valid():
            values = form.cleaned_data
            common = (request.user, case.pk, dossier.pk, values['revision'], values['target'])
            try:
                if action == 'record':
                    pack.record_pack(*common, values['key'], values['pack_file'].pk, values['receipt_file'].pk,
                                     values['reference'], values['received_at'])
                elif action == 'verify':
                    pack.confirm_pack(*common, values['row'], values['note'])
                else:
                    pack.schedule(*common, values['row'], values['previous'], values['key'], values['reply_due_at'],
                                  values['remind_at'], values['reason'])
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'The testing delivery record was updated.')
                return redirect('client_uat_pack', case_id=case.pk, dossier_id=dossier.pk)
    return render(request, 'pmo/client_testing_pack.html', {'case': case, 'dossier': dossier, 'target': target, 'state': state,
                                                         'record_form': record_form, 'review_form': review_form,
                                                         'schedule_form': schedule_form})


@login_required
@never_cache
@require_safe
def proof(request, case_id, dossier_id, row_id, side):
    case, dossier, target = visible_dossier(request, case_id, dossier_id)
    if target is None or side not in ('pack', 'receipt'):
        raise Http404
    try:
        row = pack.current_pack(request.user, dossier, target)
        if row is None or row.pk != row_id:
            raise Http404
        if row.actor_id != request.user.pk:
            pack.review_context(request.user, row)
        else:
            client_uat.witness(request.user, case)
        upload = pack.files_for(row)[0 if side == 'pack' else 1]
        data = case_uploads.read(upload)
    except (OSError, ValidationError):
        return HttpResponse('The original file is unavailable. Check the recorded evidence before continuing.', status=503)
    return FileResponse(BytesIO(data), as_attachment=True, filename=upload.name)
