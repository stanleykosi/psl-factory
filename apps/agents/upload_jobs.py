import os
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from adapters import case_uploads, openrouter, upload_text
from apps.identity.services import require
from .models import AgentJob
from .upload_recovery import LEASE, audit

ROLES = {
    'A01': ('Intake and triage', 'Classify the request and identify ambiguities or missing intake details.'),
    'A02': ('Evidence analysis', 'Extract facts from the document and identify missing evidence.'),
    'A03': ('Exception investigation', 'Identify discrepancies and suggest evidence to check next.'),
    'A04': ('Planning and coordination', 'Identify dependencies, blockers and proposed next steps.'),
    'A05': ('Finance analysis', 'Explain the figures shown and flag unclear periods, units or mappings.'),
    'A06': ('Management reporting', 'Draft a management summary and surface decisions needed.'),
    'A07': ('Release readiness', 'Identify controls evidenced by the source and approvals still missing.'),
    'A08': ('Quality review', 'Check the supplied claims against the evidence and identify unsupported conclusions.'),
}

# Native workspaces perform their own case and action checks.
FOLLOW_UP = {
    'A01': ('case', 'Open the case intake'),
    'A02': ('case', 'Open case evidence'),
    'A03': ('issues', 'Open issues'),
    'A04': ('planning', 'Open project planning'),
    'A05': ('finance_analysis', 'Open Finance analysis'),
    'A06': ('meetings', 'Open meetings and reporting'),
    'A07': ('delivery', 'Open delivery readiness'),
    'A08': ('validation', 'Open evidence validation'),
}


def authorize(actor, upload):
    # A saved model instance must not preserve a deactivated account's access.
    from django.contrib.auth import get_user_model
    if not get_user_model().objects.filter(pk=actor.pk, is_active=True).exists():
        raise PermissionDenied('This file review is unavailable for the current account.')
    require(actor, upload.case, 'case.read')
    require(actor, upload.case, 'agent.extract')
    if not upload.case.synthetic or upload.actor_id != actor.pk:
        raise PermissionDenied('Only your own files in synthetic cases can be sent to the test provider.')


@transaction.atomic
def claim_next():
    expired = list(AgentJob.objects.select_for_update(skip_locked=True).select_related('upload__case', 'actor')
                   .filter(status='running', started_at__lt=timezone.now() - LEASE).order_by('pk')[:25])
    for old in expired:
        old.status, old.settled_token = 'interrupted', old.claim_token
        old.save(update_fields=['status', 'settled_token'])
        audit(old, 'interrupted', provider_result='unknown')
    job = (AgentJob.objects.select_for_update(skip_locked=True).select_related('upload__case', 'actor')
           .filter(status='queued').order_by('pk').first())
    if job is not None:
        job.status, job.started_at = 'running', timezone.now()
        job.claim_token, job.settled_token = uuid4(), None
        job.attempt += 1
        job.save(update_fields=['status', 'started_at', 'claim_token', 'settled_token', 'attempt'])
        audit(job, 'claimed')
    return job


@transaction.atomic
def finish(job, result=None, *, failure=''):
    from apps.core.models import Case

    # Same case→job order as human review/recovery, with current authority at commit.
    Case.objects.select_for_update().get(pk=job.upload.case_id)
    current = AgentJob.objects.select_for_update().select_related('upload__case', 'actor').get(pk=job.pk)
    if current.status != 'running' or current.claim_token != job.claim_token:
        return False
    if current.started_at is None or current.started_at < timezone.now() - LEASE:
        current.status, current.settled_token = 'interrupted', current.claim_token
        current.save(update_fields=['status', 'settled_token'])
        audit(current, 'interrupted', provider_result='unknown')
        return False
    if not failure:
        try:
            authorize(current.actor, current.upload)
        except PermissionDenied:
            failure = 'access_changed'
    current.status = 'held' if failure else 'draft'
    current.settled_token = current.claim_token
    fields = ['status', 'settled_token']
    if not failure:
        current.result = result
        fields.append('result')
    current.save(update_fields=fields)
    audit(current, current.status, failure=failure, provider_result='unknown' if failure else 'received')
    return True


def run_once():
    model = os.getenv('OPENROUTER_MODEL')
    if not model or not os.getenv('OPENROUTER_API_KEY'):
        return False
    job = claim_next()
    if job is None:
        return False
    stage = 'source'
    try:
        authorize(job.actor, job.upload)
        source = upload_text.extract(job.upload.name, case_uploads.read(job.upload))
        # Source grants/account can change while private storage is being read.
        authorize(job.actor, job.upload)
        stage = 'provider'
        result = openrouter.review(model, ROLES[job.role][1], source)
        stage = 'output'
        authorize(job.actor, job.upload)
        lines = {str(number): line for number, line in enumerate(source.splitlines(), 1)
                 if line.strip() and len(line) <= 1000}
        if isinstance(result, dict) and isinstance(result.get('quotes'), list):
            result['quotes'] = [str(item) if type(item) is int else item for item in result['quotes']]
        if (not isinstance(result, dict) or set(result) != {'summary', 'quotes', 'gaps'}
                or not isinstance(result['summary'], str) or not 0 < len(result['summary']) <= 4000
                or any(not isinstance(result[field], list) or len(result[field]) > 12
                       or any(not isinstance(item, str) or not 0 < len(item) <= 1000 for item in result[field])
                       for field in ('quotes', 'gaps'))
                or not result['quotes'] or any(quote not in lines for quote in result['quotes'])):
            raise ValidationError('The draft did not contain valid source citations.')
        result['quotes'] = [lines[number] for number in result['quotes']]
        result['model'] = model
        result['source_sha256'] = job.upload.sha256
        finish(job, result)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning('Agent job %s held: %s', job.pk, type(exc).__name__)
        finish(job, failure='access_changed' if isinstance(exc, PermissionDenied) else stage + '_unavailable')
    return True
