import os
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from adapters import case_uploads, openrouter, upload_text
from apps.identity.services import require
from .models import AgentJob

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
    require(actor, upload.case, 'case.read')
    require(actor, upload.case, 'agent.extract')
    if not upload.case.synthetic or upload.actor_id != actor.pk:
        raise PermissionDenied('Only your own files in synthetic cases can be sent to the test provider.')


def run_once():
    model = os.getenv('OPENROUTER_MODEL')
    if not model or not os.getenv('OPENROUTER_API_KEY'):
        return False
    with transaction.atomic():
        AgentJob.objects.filter(status='running', started_at__lt=timezone.now() - timedelta(minutes=10)).update(
            status='interrupted')
        job = AgentJob.objects.select_for_update(skip_locked=True).filter(status='queued').order_by('pk').first()
        if job is None:
            return False
        job.status, job.started_at = 'running', timezone.now()
        job.save(update_fields=['status', 'started_at'])
    try:
        authorize(job.actor, job.upload)
        source = upload_text.extract(job.upload.name, case_uploads.read(job.upload))
        result = openrouter.review(model, ROLES[job.role][1], source)
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
        AgentJob.objects.filter(pk=job.pk, status='running').update(status='draft', result=result)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning('Agent job %s held: %s', job.pk, type(exc).__name__)
        AgentJob.objects.filter(pk=job.pk, status='running').update(status='held')
    return True
