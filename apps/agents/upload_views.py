import hashlib
import os

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.views.decorators.http import require_http_methods, require_safe

from adapters import case_uploads
from apps.core.workbench import granted
from apps.identity.factory_access import project_actions
from apps.identity.services import require, visible_cases
from .models import AgentJob, CaseUpload
from .upload_jobs import FOLLOW_UP, ROLES, authorize
from . import file_draft_reviews, workflow_handoffs
from . import upload_recovery


def file_workspaces(actor):
    return visible_cases(actor) | granted(actor, ['agent.extract', 'evidence.add']).filter(synthetic=True)


def upload_file(actor, case, file):
    require(actor, case, 'evidence.add')
    if file is None or not 0 < file.size <= case_uploads.LIMIT:
        raise ValidationError('Choose a file up to 5 MiB.')
    data = file.read()
    sha = hashlib.sha256(data).hexdigest()
    key = hashlib.sha256(f'{case.pk}:{actor.pk}:{sha}'.encode()).hexdigest()
    # Repeat uploads reuse a key only for the same case and uploader.
    case_uploads.put(key, data)
    upload, _ = CaseUpload.objects.get_or_create(key=key, defaults={
        'case': case, 'actor': actor, 'sha256': sha, 'size': len(data), 'name': file.name[:160],
    })
    return upload


@transaction.atomic
def queue_draft(actor, upload, role):
    from apps.core.services import lock_case
    lock_case(actor, upload.case_id, 'agent.extract')
    authorize(actor, upload)
    if role not in ROLES or not os.getenv('OPENROUTER_MODEL'):
        raise ValidationError('Choose an available agent. A model must be configured to start a draft.')
    job, created = AgentJob.objects.get_or_create(upload=upload, actor=actor, role=role)
    if created:
        upload_recovery.audit(job, 'queued')
    if job.status in {'held', 'interrupted'}:
        raise ValidationError('Open the stopped file review below and record why another review is needed.')
    if job.status == 'draft' and not file_draft_reviews.reviewable(job):
        raise ValidationError('The earlier draft needs a new review. Record the reason in its recovery form below.')
    return job


@login_required
@require_http_methods(['GET', 'POST'])
def workbench(request, case_id):
    case = get_object_or_404(file_workspaces(request.user), pk=case_id)
    uploads = CaseUpload.objects.filter(case=case, actor=request.user)
    error = None
    attempted_review = None
    attempted_recovery = None
    if request.method == 'POST':
        try:
            if request.POST.get('action') == 'upload':
                upload_file(request.user, case, request.FILES.get('file'))
            elif request.POST.get('action') == 'review':
                attempted_review = request.POST.get('job')
                file_draft_reviews.retain(request.user, case, request.POST.get('job'), request.POST)
            elif request.POST.get('action') == 'retry':
                attempted_recovery = request.POST.get('job')
                upload_recovery.retry(request.user, case, request.POST.get('job'), request.POST)
            elif request.POST.get('action') == 'handoff':
                workflow_handoffs.consume(request.user, case, request.POST.get('job'), request.POST)
            else:
                raise ValidationError('Choose a file or agent task.')
            return redirect('case_uploads', case_id=case.pk)
        except ValidationError as exc:
            error = exc.messages[0]
        except (OSError, ValueError):
            error = 'The request could not be completed.'
    permissions = project_actions(request.user, case)
    can_use_agent = case.synthetic and 'agent.extract' in permissions
    can_review = file_draft_reviews.can_retain(request.user, case)
    jobs = list(AgentJob.objects.filter(upload__in=uploads, actor=request.user)
                .select_related('upload', 'file_review').order_by('-pk')[:50]) if can_use_agent else []
    histories = upload_recovery.histories(request.user, case, jobs)
    for job in jobs:
        job.role_label = ROLES[job.role][0]
        job.progress = upload_recovery.describe(job)
        if job.progress['can_request_recovery']:
            initial = {'attempt_pin': upload_recovery.pin(job)}
            if str(job.pk) == attempted_recovery:
                initial.update(reason=request.POST.get('reason', ''), confirm=bool(request.POST.get('confirm')))
            job.recovery_form = upload_recovery.RecoveryForm(initial=initial, auto_id=f'file-recovery-{job.pk}-%s')
        job.history = histories.get(job.pk, [])
        job.follow_up = FOLLOW_UP.get(job.role)
        if job.status == 'draft' and can_review:
            if file_draft_reviews.reviewable(job):
                job.review_form = file_draft_reviews.review_form(job, request.POST if str(job.pk) == attempted_review else None)
            else:
                job.needs_fresh_draft = True
        if job.status == 'reviewed' and not job.result.get('workflow_record'):
            job.handoff_form = workflow_handoffs.form_for(job)
            job.handoff_label = workflow_handoffs.LABELS[job.role]
    response = render(request, 'agents/uploads.html', {
        'case': case, 'uploads': uploads.order_by('-pk')[:50],
        'jobs': jobs,
        'watch_jobs': any(job.status in {'queued', 'running'} for job in jobs),
        'error': error,
    })
    response['Cache-Control'] = 'no-store'
    return response


@login_required
@require_safe
def download(request, case_id, upload_id):
    from io import BytesIO

    case = get_object_or_404(file_workspaces(request.user), pk=case_id)
    upload = get_object_or_404(CaseUpload, case=case, actor=request.user, pk=upload_id)
    response = FileResponse(BytesIO(case_uploads.read(upload)), as_attachment=True,
                            filename=upload.name, content_type='application/octet-stream')
    response['Cache-Control'] = 'no-store'
    return response
