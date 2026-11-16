import hashlib
import os

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from adapters import case_uploads
from apps.core.views import accessible_case
from apps.core.services import add_evidence, lock_case
from apps.documents.services import review_document
from apps.identity.services import active_case_grants, require
from .models import AgentJob, CaseUpload
from .upload_jobs import FOLLOW_UP, ROLES, authorize
from . import workflow_handoffs


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


def queue_draft(actor, upload, role):
    authorize(actor, upload)
    if role not in ROLES or not os.getenv('OPENROUTER_MODEL'):
        raise ValidationError('Choose an available agent. A model must be configured to start a draft.')
    job, _ = AgentJob.objects.get_or_create(upload=upload, actor=actor, role=role)
    AgentJob.objects.filter(pk=job.pk, status='held').update(status='queued')
    return job


@transaction.atomic
def retain_review(actor, case, job_id, note):
    case = lock_case(actor, case.pk, 'document.review')
    job = get_object_or_404(AgentJob.objects.select_for_update(), upload__case=case,
                            actor=actor, pk=job_id, status='draft')
    authorize(actor, job.upload)
    if not note.strip() or len(note) > 1000:
        raise ValidationError('Enter a review note of up to 1,000 characters.')
    body = '\n'.join([job.result['summary'], '', 'Source excerpts:', *job.result['quotes'],
                      '', 'Open questions:', *job.result['gaps']])
    evidence = add_evidence(actor, case.pk, 'agent_review_note', body,
                            f'agent-draft:{job.pk}:sha256:{job.upload.sha256}')
    case.refresh_from_db()
    review_document(actor, case.pk, evidence.pk, 'accepted', note, case.revision)
    job.status = 'reviewed'
    job.result = {**job.result, 'reviewed_evidence': evidence.pk}
    job.save(update_fields=['status', 'result'])


@login_required
@require_http_methods(['GET', 'POST'])
def workbench(request, case_id):
    case = accessible_case(request.user, case_id)
    uploads = CaseUpload.objects.filter(case=case, actor=request.user)
    error = None
    if request.method == 'POST':
        try:
            if request.POST.get('action') == 'upload':
                upload_file(request.user, case, request.FILES.get('file'))
            elif request.POST.get('action') == 'queue':
                upload = get_object_or_404(uploads, pk=request.POST.get('upload'))
                queue_draft(request.user, upload, request.POST.get('role'))
            elif request.POST.get('action') == 'review':
                retain_review(request.user, case, request.POST.get('job'), request.POST.get('note', ''))
            elif request.POST.get('action') == 'handoff':
                workflow_handoffs.consume(request.user, case, request.POST.get('job'), request.POST)
            else:
                raise ValidationError('Choose a file or agent task.')
            return redirect('case_uploads', case_id=case.pk)
        except ValidationError as exc:
            error = exc.messages[0]
        except (OSError, ValueError):
            error = 'The request could not be completed.'
    can_use_agent = case.synthetic and (case.pk, 'agent.extract') in active_case_grants(
        request.user, [case.pk], actions=['agent.extract'],
    )
    jobs = list(AgentJob.objects.filter(upload__in=uploads, actor=request.user)
                .select_related('upload').order_by('-pk')[:50]) if can_use_agent else []
    for job in jobs:
        job.role_label = ROLES[job.role][0]
        job.follow_up = FOLLOW_UP.get(job.role)
        if job.status == 'reviewed' and not job.result.get('workflow_record'):
            job.handoff_form = workflow_handoffs.form_for(job)
            job.handoff_label = workflow_handoffs.LABELS[job.role]
    response = render(request, 'agents/uploads.html', {
        'case': case, 'uploads': uploads.order_by('-pk')[:50], 'roles': ROLES,
        'jobs': jobs,
        'can_queue': can_use_agent and bool(os.getenv('OPENROUTER_MODEL')),
        'error': error,
    })
    response['Cache-Control'] = 'no-store'
    return response


@login_required
@require_safe
def download(request, case_id, upload_id):
    from io import BytesIO

    case = accessible_case(request.user, case_id)
    upload = get_object_or_404(CaseUpload, case=case, actor=request.user, pk=upload_id)
    response = FileResponse(BytesIO(case_uploads.read(upload)), as_attachment=True,
                            filename=upload.name, content_type='application/octet-stream')
    response['Cache-Control'] = 'no-store'
    return response
