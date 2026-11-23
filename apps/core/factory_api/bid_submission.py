"""Exact private client PDF and controlled submission progress."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.documents import controlled
from apps.documents.models import PublicationJob
from apps.identity.services import require
from apps.pmo import rfp_submission_artifacts as artifacts
from apps.pmo.models import RFPDocumentBinding, RFPSubmission
from apps.workflows import factory, factory_rfp, factory_progress

from .commands import require_line
from .http import BOOLEAN, DATETIME, ID, TEXT, array, endpoint, nullable, obj
from .reviews import VERSIONS
from .work import WORK_RESULT, result


FILE = obj({'id': ID, 'version_id': ID, 'sha256': TEXT, 'size': ID, 'findings': array(TEXT)})
RECEIPT = obj({'id': ID, 'submitted_at': DATETIME, 'receipt_ids': array(ID), 'late': BOOLEAN})


def scope(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, factory_rfp.DEFINITION)
    require(actor, work.case, 'rfp.read')
    require(actor, work.case, 'document.read')
    version = factory_rfp.review_document(work)
    if version is None:
        raise Http404
    binding = get_object_or_404(RFPDocumentBinding, version=version, response__rfp=factory_rfp.subject(work))
    return work, version, binding


@endpoint(response=obj({**VERSIONS, 'version_id': ID, 'file': nullable(FILE), 'route': TEXT,
                        'job_id': nullable(ID), 'job_status': nullable(TEXT), 'submission': nullable(RECEIPT),
                        'approval_recorded': BOOLEAN}),
          summary='Read the exact client PDF checks, recorded approval, outbound job and original submission receipt')
def detail(request, work_id):
    work, version, binding = scope(request, work_id)
    job = PublicationJob.objects.filter(publication__version=version, publication__factory_work=work).first()
    submission = RFPSubmission.objects.filter(response=binding.response, version=version).first()
    file = artifacts.panel(request.user, work.case, version)
    try:
        approval = controlled.validate_review(work.case, version)
    except ValidationError:
        approval = None
    return {'expected_revision': work.revision, 'case_revision': work.case.revision,
            'version_id': version.pk, 'file': {'id': file['file'].pk, 'version_id': version.pk,
                'sha256': file['file'].sha256, 'size': file['file'].size, 'findings': file['findings']} if file else None,
            'route': binding.snapshot['route']['method'], 'job_id': job.pk if job else None,
            'job_status': job.status if job else None, 'approval_recorded': approval is not None,
            'submission': {'id': submission.pk, 'submitted_at': submission.submitted_at,
                           'receipt_ids': submission.receipt_ids, 'late': submission.late} if submission else None}


@endpoint(response={'type': 'string', 'format': 'binary'}, media_type='application/pdf',
          summary='Download the exact private PDF for the current client bid pack')
def pdf(request, work_id, version_id):
    work, version, _ = scope(request, work_id)
    if version.pk != version_id:
        raise Http404
    return artifacts.pdf_response(request.user, work.case, version.pk, as_attachment=True)


@endpoint(method='POST', request=obj({**VERSIONS, 'version_id': ID}), response=WORK_RESULT, status=202,
          summary='Continue the exact approved client submission through its current native destination')
def queue(request, work_id, *, body):
    actor = request.user
    work, version, binding = scope(request, work_id)
    require(actor, work.case, 'rfp.submit')
    if (work.revision, work.case.revision, version.pk) != (body['expected_revision'], body['case_revision'], body['version_id']):
        raise ValidationError('STALE_VERSION: Refresh the exact client pack before continuing.')
    if binding.snapshot['route']['method'] == 'manual_client_portal':
        raise ValidationError('Record the original client portal receipt for this submission.')
    controlled.current_version(work.case, version.pk)
    if controlled.validate_review(work.case, version) is None:
        raise ValidationError('The exact pack requires recorded independent approval.')
    _, config = factory.profile(work)
    publisher = get_user_model().objects.filter(pk=config['executor_id'], is_active=True).first()
    if publisher is None:
        raise ValidationError('Configure the current bid publisher before submission.')
    factory.access(publisher, work.case, 'factory.execute', factory_rfp.DEFINITION)
    if not PublicationJob.objects.filter(publication__version=version, publication__factory_work=work).exists():
        controlled.guard_reserve_publication(publisher, work.case, version.pk)
    factory_progress.set_progress(actor, work.pk, work.revision, True)
    work.refresh_from_db()
    return result(work)
