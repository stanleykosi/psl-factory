"""Human recovery of an exact file-agent attempt; never a business approval."""
from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.services import event, lock_case
from apps.documents.contracts import digest
from .models import AgentJob, FileDraftReview

# Engineering lease retained from the existing upload worker, not an owner rule.
LEASE = timedelta(minutes=10)


def pin(job):
    return digest({'job': job.pk, 'status': job.status, 'attempt': job.attempt,
                   'claim': str(job.claim_token), 'started': str(job.started_at)})


class RecoveryForm(forms.Form):
    attempt_pin = forms.CharField(min_length=64, max_length=64, widget=forms.HiddenInput)
    reason = forms.CharField(max_length=500, label='Why another file review is needed',
                            widget=forms.Textarea(attrs={'rows': 2}))
    confirm = forms.BooleanField(label='The earlier request may have reached the model provider. Start another review.')


def available(job):
    from .file_draft_reviews import reviewable
    if job.status == 'draft':
        return not reviewable(job)
    return job.status in {'held', 'interrupted'} or (
        job.status == 'running' and job.started_at is not None
        and job.started_at < timezone.now() - LEASE)


def describe(job):
    """Closed metadata for UI/agent investigation; no model text or recovery effect."""
    labels = {'queued': 'Waiting for the agent', 'running': 'Reading the file',
              'draft': 'Draft ready for human review', 'reviewed': 'Human review saved',
              'held': 'File review needs attention', 'interrupted': 'File review was interrupted'}
    return {'label': labels.get(job.status, 'File review needs attention'),
            'attempt': job.attempt, 'can_request_recovery': available(job)}


def histories(actor, case, jobs):
    from apps.core.models import Audit
    from .upload_jobs import authorize

    if not jobs:
        return {}
    authorize(actor, jobs[0].upload)
    ids = [job.pk for job in jobs if job.actor_id == actor.pk and job.upload.case_id == case.pk]
    labels = {'queued': 'File review requested', 'claimed': 'Agent started reading',
              'interrupted': 'Review interrupted; provider result unknown',
              'held': 'No usable draft saved', 'draft': 'Draft saved for human review',
              'recovery_requested': 'Another review requested'}
    result = {key: [] for key in ids}
    # Read selected metadata only; never transfer unrelated audit bodies or file text.
    rows = (Audit.objects.filter(case=case, actor=actor, action__in=['file_agent.' + key for key in labels],
                                 data__job__in=ids).order_by('-pk')
            .values('created_at', 'action', 'data__job', 'data__attempt', 'data__reason')[:200])
    for row in rows:
        result[row['data__job']].append({'at': row['created_at'], 'label': labels[row['action'].split('.')[1]],
                                        'attempt': row['data__attempt'], 'reason': row['data__reason']})
    return result


def audit(job, action, **data):
    event(job.actor, job.upload.case, 'file_agent.' + action, job=job.pk, role=job.role,
          attempt=job.attempt, claim=str(job.claim_token) if job.claim_token else None, **data)


@transaction.atomic
def retry(actor, case, job_id, data):
    from .upload_jobs import authorize

    case = lock_case(actor, case.pk, 'agent.extract')
    if not str(job_id).isascii() or not str(job_id).isdigit() or len(str(job_id)) > 18:
        raise ValidationError('Open the file review you want to recover.')
    job = AgentJob.objects.select_for_update().select_related('upload__case', 'actor').filter(
        pk=job_id, upload__case=case, actor=actor).first()
    if job is None:
        raise ValidationError('This file review is unavailable.')
    authorize(actor, job.upload)
    form = RecoveryForm(data)
    if not form.is_valid():
        raise ValidationError(next(iter(form.errors.values()))[0])
    if form.cleaned_data['attempt_pin'] != pin(job):
        raise ValidationError('This file review changed. Reload before trying again.')
    if FileDraftReview.objects.filter(job=job).exists() or not available(job):
        raise ValidationError('Only a stopped, expired or unusable file draft can be tried again. Keep the existing reviewed evidence.')
    if job.status == 'running':
        job.status, job.settled_token = 'interrupted', job.claim_token
        job.save(update_fields=['status', 'settled_token'])
        audit(job, 'interrupted', provider_result='unknown')
    prior = job.status
    # Preserve the last result and attempt identity. A worker mints a fresh claim.
    job.status = 'queued'
    job.save(update_fields=['status'])
    audit(job, 'recovery_requested', previous_status=prior, reason=form.cleaned_data['reason'],
          provider_result='unknown', previous_result_sha256=digest(job.result),
          repeated_provider_request_acknowledged=True)
    return job
