from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from . import rfp_fresh_intake, rfp_intake_upload, rfp_staged_uploads
from .rfp_upload_models import RFPStagedUpload


def records(actor):
    return RFPStagedUpload.objects.filter(actor=actor).select_related('case', 'intake__rfp__case')


def inspect(actor, row, *, check=False):
    receipt = None
    if row.intake_id:
        case = row.intake.rfp.case
        attachment = rfp_intake_upload.attachment_for(actor, case, row.intake)
        if attachment is None or (attachment.pk, attachment.key, attachment.sha256, attachment.size) != (
                row.upload_id, row.key, row.sha256, row.size):
            raise ValidationError('The original private receipt needs review.')
        receipt = reverse('rfp_intake_attachment', args=[case.pk, row.intake_id])
        status = 'Attached to the recorded bid.'
    elif row.case_id:
        rfp_intake_upload.authorize_write(actor, row.case)
        status = ('The workspace has changed. Review the current bid before uploading.'
                  if row.case.revision != row.case_revision else None)
    else:
        rfp_fresh_intake.current_authority(actor, row.authority_id)
        status = None

    if status is None:
        rfp_staged_uploads.ensure_storage(row)
        if check:
            status = ('Original file verified. Resubmit the same request to finish recording it.'
                     if rfp_staged_uploads.verified(row) else 'The original file could not be verified. The upload remains unresolved.')
        else:
            status = 'Upload has no confirmed attachment.'
    return {'id': row.pk, 'recorded_at': row.created_at, 'size': row.size, 'status': status,
            'receipt': receipt, 'can_check': not row.intake_id and status == 'Upload has no confirmed attachment.'}


@login_required
@require_safe
@never_cache
def workbench(request):
    actor = request.user
    selected = request.GET.get('check')
    result = None
    if selected:
        try:
            intent_id = UUID(selected)
        except (ValueError, TypeError):
            raise Http404 from None
        row = get_object_or_404(records(actor), pk=intent_id)
        try:
            result = inspect(actor, row)
            if result['can_check']:
                with rfp_staged_uploads.serialized(row.operation, wait=False) as available:
                    if available:
                        current = get_object_or_404(records(actor), pk=row.pk)
                        result = inspect(actor, current, check=True)
                    else:
                        result['status'] = 'The original upload is still being recorded.'
        except PermissionDenied:
            raise Http404 from None
        except ValidationError as exc:
            result = {'status': exc.messages[0]}

    recent = []
    for row in records(actor).order_by('-created_at', '-pk')[:20]:
        try:
            recent.append(inspect(actor, row))
        except (PermissionDenied, ValidationError):
            continue
    return render(request, 'pmo/rfp_staged_uploads.html', {'selected_upload': result, 'recent_uploads': recent})
