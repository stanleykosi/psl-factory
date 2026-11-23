"""Audience preview, native review and bounded text rework for standalone reports."""
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.core.evidence_access import public_evidence
from apps.core.services import lock_case
from apps.identity.services import active_case_grants, require, visible_cases
from apps.policy.services import decision_authority
from apps.workflows.models import HumanTask

from . import controlled
from .contracts import digest
from .delivery import operate_publication
from .models import PublicationJob, PublicationReceipt, Version


def visible_reports(case):
    return Version.objects.filter(document__case=case, template__definition__document_type='status_report',
                                  minutesreportbinding__isnull=True, forecastbinding__isnull=True,
                                  financedocumentbinding__isnull=True).exclude(audience='group')


def sources_for(case, version):
    ids = {entry['id'] for entry in version.source_manifest}
    evidence = list(public_evidence(case.evidence.filter(pk__in=ids)).only('kind', 'version', 'source').order_by('pk'))
    if {row.pk for row in evidence} != ids:
        raise Http404
    return evidence


class ReviewForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    note = forms.CharField(label='Reason for your decision', max_length=4000, widget=forms.Textarea(attrs={'rows': 4}))
    verdict = forms.ChoiceField(label='Decision')


class ReworkForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, version, data, revision):
        super().__init__(data, initial={'revision': revision})
        audience_fields = version.template.definition['audience_fields'].get(version.audience, [])
        for field, section in version.fields.items():
            if field in audience_fields:
                self.fields[field] = forms.CharField(label=field.replace('_', ' ').capitalize(), max_length=12000,
                                                     required=False, widget=forms.Textarea(attrs={'rows': 4}), initial=section['text'])


class RecoveryForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    reason = forms.CharField(label='Reason for this recovery action', max_length=4000, widget=forms.Textarea(attrs={'rows': 3}))


def possible_verdicts(actor, case, task):
    choices = []
    for delegated in (False, True):
        for verdict in ('approve', 'return', 'reject'):
            try:
                decision_authority(actor, case, task.required_role, verdict, delegated)
            except (ValidationError, PermissionDenied):
                continue
            label = {'approve': 'Approve this version', 'return': 'Return for changes', 'reject': 'Reject this version'}[verdict]
            choices.append((f'{verdict}:{int(delegated)}', label + (' using delegation' if delegated else '')))
    return choices


@transaction.atomic
def revise_report(actor, case, version, revision, changes):
    locked = lock_case(actor, case.pk, 'document.draft', revision)
    version = get_object_or_404(visible_reports(locked).select_related('template', 'document'), pk=version.pk)
    sources_for(locked, version)
    task = HumanTask.objects.filter(version=version).first()
    if version.document.current_id != version.pk:
        raise ValidationError('STALE_VERSION: Open the current report before revising it.')
    if PublicationJob.objects.filter(publication__version=version).exists() or (
        task and task.status not in {'returned', 'rejected', 'withdrawn'}
    ):
        raise ValidationError('Only a report with no outstanding review or delivery can be revised here.')
    allowed = version.fields.keys() & set(version.template.definition['audience_fields'].get(version.audience, []))
    if not changes or set(changes) - allowed:
        raise ValidationError('Choose editable sections from the current report audience.')
    fields = {key: {**section, 'text': changes.get(key, section['text'])} for key, section in version.fields.items()}
    return controlled.create_version(actor, case.pk, version.template_id, version.document.title,
        version.audience, fields, revision, version.document_id,
        template_scope_id=version.template_current_manifest.get('scope_id'))


@transaction.atomic
def publish_report(actor, case, version, revision, token):
    locked = lock_case(actor, case.pk, 'document.publish', revision)
    sources_for(locked, version)
    checked, packet, _ = controlled.guard_reserve_publication(actor, locked, version.pk)
    if checked.document.current_id != version.pk or digest(packet) != token:
        raise ValidationError('STALE_VERSION: Publication details changed. Review the current version and recipients.')
    return controlled.reserve_publication(actor, case.pk, version.pk, revision)


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def show(request, case_id, version_id):
    actor = request.user
    case = get_object_or_404(visible_cases(actor), pk=case_id)
    require(actor, case, 'document.read')
    version = get_object_or_404(visible_reports(case).select_related('document', 'template'), pk=version_id)
    sources = sources_for(case, version)
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    current = version.document.current_id == version.pk
    task = HumanTask.objects.filter(version=version).first()
    latest_review = version.reviews.select_related('actor').order_by('-pk').first()
    job = PublicationJob.objects.filter(publication__version=version).first()
    receipts = list(PublicationReceipt.objects.filter(publication_id=job.publication_id).only('created_at')) if job else []
    operation = request.POST.get('action') if request.method == 'POST' else None
    can_request = current and task is None and 'document.request_review' in grants
    audience_fields = version.template.definition['audience_fields'].get(version.audience, [])
    can_edit = current and bool(version.fields.keys() & set(audience_fields)) and 'document.draft' in grants and not job and (
        not task or task.status in {'returned', 'rejected', 'withdrawn'})
    verdicts = possible_verdicts(actor, case, task) if current and task and task.status == 'open' and 'document.review_controlled' in grants else []
    review = ReviewForm(request.POST if operation == 'review' else None, initial={'revision': case.revision}) if verdicts else None
    if review:
        review.fields['verdict'].choices = verdicts
    rework = ReworkForm(version, request.POST if operation == 'revise' else None, case.revision) if can_edit else None
    recovery_actions = []
    if job and not receipts and 'document.operate' in grants and job.status in {'held', 'pending'}:
        if current and job.status == 'held':
            recovery_actions.append(('retry', 'Retry this delivery'))
        recovery_actions.append(('cancel', 'Cancel this delivery'))
    recovery = RecoveryForm(request.POST if operation in {'retry', 'cancel'} else None,
                            initial={'revision': case.revision}) if recovery_actions else None
    findings = controlled.preflight(version)
    publication = None
    if current and not job and not findings and 'document.publish' in grants:
        try:
            _, packet, _ = controlled.guard_reserve_publication(actor, case, version.pk)
        except (ValidationError, PermissionDenied):
            pass
        else:
            people = get_user_model().objects.in_bulk(packet['recipients'])
            publication = {'token': digest(packet), 'recipients': [people[pk].get_full_name() or people[pk].username
                            for pk in packet['recipients'] if pk in people]}
    if operation:
        try:
            # The case row pin also serializes a concurrent edit or decision on this exact document.
            if operation == 'review' and review and review.is_valid():
                values = review.cleaned_data
                verdict, delegated = values['verdict'].split(':')
                controlled.review_version(actor, case.pk, version.pk, verdict, values['note'], values['revision'], delegated == '1')
            elif operation == 'request' and can_request:
                controlled.request_review(actor, case.pk, version.pk, int(request.POST.get('revision', '0')))
            elif operation == 'publish':
                revision = int(request.POST.get('revision', '0'))
                publish_report(actor, case, version, revision, request.POST.get('packet'))
            elif operation in dict(recovery_actions) and recovery.is_valid():
                values = recovery.cleaned_data
                operate_publication(actor, case.pk, job.pk, operation, values['reason'], values['revision'])
            elif operation == 'revise' and rework and rework.is_valid():
                successor = revise_report(actor, case, version, rework.cleaned_data['revision'],
                    {key: value for key, value in rework.cleaned_data.items() if key != 'revision'})
                return redirect('design_document_review', case.pk, successor.pk)
            else:
                raise ValidationError('Choose an action available for this version.')
        except (ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, 'Review status recorded for this version.')
            return redirect('design_document_review', case.pk, version.pk)
    return render(request, 'design/document_review.html', {'case': case, 'version': version, 'current': current,
        'findings': findings, 'sources': sources, 'task': task, 'latest_review': latest_review,
        'can_request': can_request and not findings, 'review_form': review if not findings else None,
        'rework': rework, 'publication': publication, 'job': job, 'receipts': receipts,
        'recovery_form': recovery, 'recovery_actions': recovery_actions})
