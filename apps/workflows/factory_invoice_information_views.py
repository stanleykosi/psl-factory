"""Supply and review private proof on the invoice's exact milestone request."""

from io import BytesIO
from uuid import uuid4

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from adapters import case_uploads
from apps.core.evidence_access import INVOICE_MILESTONE_PROOF

from . import factory_invoice_information as service
from .models import FactoryWork


class ProofForm(forms.Form):
    task = forms.IntegerField(min_value=1)
    task_revision = forms.IntegerField(min_value=1)
    case_revision = forms.IntegerField(min_value=1)
    upload = forms.IntegerField(min_value=1)
    previous = forms.IntegerField(min_value=1, required=False)
    proof_operation = forms.UUIDField()
    proof_note = forms.CharField(max_length=2000, required=False)


def supply(request, work):
    form = ProofForm(request.POST)
    if not form.is_valid():
        raise ValidationError('Choose the original private PDF and use a note of up to 2,000 characters.')
    data = form.cleaned_data
    return service.attach(request.user, work.pk, data['task'], data['task_revision'], data['case_revision'],
                          data['upload'], data['proof_operation'], data['previous'], data['proof_note'])


def decorate(actor, row):
    tasks = [task for task in row['tasks'] if task.kind == 'factory_information'
             and INVOICE_MILESTONE_PROOF in task.context.get('missing', [])]
    if not tasks:
        return
    work = row['work']
    try:
        proof = service.readable_proof(actor, work)
    except (PermissionDenied, ValidationError):
        proof = None
    row['invoice_milestone_proof'] = proof
    for task in tasks:
        task.private_milestone_request = True
        if not task.can_supply:
            continue
        try:
            task.milestone = service.authorize(actor, work, task).milestone
        except (PermissionDenied, ValidationError):
            continue
        task.proof_files = list(service.available_files(actor, work).values('pk', 'name')[:50])
        task.proof_operation = uuid4()
        task.prior_proof = proof if proof is not None and proof.task_id == task.pk else None
        task.other_source_kinds = [kind for kind in task.context['missing'] if kind != INVOICE_MILESTONE_PROOF]


@login_required
@never_cache
@require_safe
def download(request, work_id, proof_id):
    work = get_object_or_404(FactoryWork.objects.select_related('case', 'invoice'), pk=work_id)
    try:
        proof = service.readable_proof(request.user, work)
        if proof is None or proof.pk != proof_id:
            raise Http404
        data = case_uploads.read(proof.upload)
    except (PermissionDenied, ValidationError, OSError) as exc:
        raise Http404 from exc
    response = FileResponse(BytesIO(data), as_attachment=True, filename=proof.upload.name,
                            content_type='application/octet-stream')
    response['X-Content-Type-Options'] = 'nosniff'
    return response
