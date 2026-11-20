"""Scoped screen adapter for native RFP pack preparation."""

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.pmo import rfp_submission_pack as packs

from . import factory as runtime, factory_rfp
from .models import FactoryWork


class SubmissionPackForm(forms.Form):
    target = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    base = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    cover_note = forms.CharField(required=False, max_length=4000, label='Cover note',
                                 widget=forms.Textarea(attrs={'rows': 5}))
    file_extension = forms.CharField(required=False, max_length=16, label='Requested file extension')
    file_count = forms.IntegerField(required=False, min_value=1, max_value=2_147_483_647,
                                    label='Requested number of files')
    file_size_rule = forms.ChoiceField(required=False, label='How the file size limit applies',
                                      choices=[('', 'Unknown'), *packs.SIZE_RULES.items()])
    file_size_bytes = forms.IntegerField(required=False, min_value=1, max_value=9_223_372_036_854_775_807,
                                         label='Size limit per file in bytes')

    def clean(self):
        data = super().clean()
        if not self.errors:
            data.update(packs.normalized({key: data[key] for key in packs.FIELDS}))
        return data


def active(work):
    return (not work.cancel_requested and work.status not in ('verified', 'cancelled', 'followup_needed', 'waiting_effect')
            and not (work.lease_until and work.lease_until > timezone.now()))


def panel(actor, work, response, form=None):
    if response is None:
        return {}
    try:
        pack = packs.read(actor, work.case, response)
    except PermissionDenied:
        return {}
    can_edit = active(work) and packs.can_edit(actor, work.case, response)
    if not pack and not can_edit:
        return {}
    if can_edit and form is None:
        initial = {'target': response.pk, 'base': pack.pk if pack else 0}
        if pack:
            initial.update({key: getattr(pack, key) for key in packs.FIELDS})
        form = SubmissionPackForm(initial=initial, prefix='pack')
    return {
        'submission_pack': pack,
        'submission_pack_response': response,
        'submission_pack_form': form if can_edit else None,
        'submission_pack_requirements': packs.requirements(pack) if pack else [],
    }


@transaction.atomic
def record(actor, work_id, work_revision, case_revision, data):
    work = FactoryWork.objects.select_for_update(of=('self',)).select_related('case').get(
        pk=work_id, definition=factory_rfp.DEFINITION)
    runtime.access(actor, work.case, envelope=factory_rfp.DEFINITION)
    if not active(work):
        raise ValidationError('The current workflow must be available before changing this pack.')
    if work.revision != work_revision:
        raise ValidationError('The current workflow changed. Reload before editing this pack.')
    response = factory_rfp.response_for(work)
    if not response or response.pk != data['target']:
        raise ValidationError('Choose the exact current response for this workflow.')
    pack = packs.record(actor, work.case_id, response.pk, data['base'], case_revision,
                        {key: data[key] for key in packs.FIELDS})
    if pack.pk != data['base']:
        work.status = 'ready'
        work.finding = ''
        work.revision += 1
        work.save(update_fields=['status', 'finding', 'revision', 'updated_at'])
        from .factory_progress import wake_waiting
        wake_waiting(work.pk)
    return pack
