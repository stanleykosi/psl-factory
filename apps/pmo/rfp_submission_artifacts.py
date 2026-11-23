"""Private PDF review files. Preparation and viewing produce no submission."""

from hashlib import sha256
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from adapters import rfp_pdf
from apps.core.evidence_access import public_evidence
from apps.core.services import event
from apps.documents.contracts import digest
from apps.identity.services import require, visible_cases

from .models import RFPSubmissionArtifact


METADATA = ('pk', 'binding_id', 'payload_sha256', 'sha256', 'size')


def materialize(binding):
    """Called under the draft's case lock before any final review can start."""
    previous = metadata(binding=binding)
    if previous:
        return previous
    version = binding.version
    if 'submission_pack' not in binding.snapshot or version.audience != 'client' or (
            version.payload_sha256 != digest(version.payload)):
        raise ValidationError('The client PDF requires the exact controlled submission pack.')
    data = rfp_pdf.render(version.payload)
    rfp_pdf.verify_pdf(data)
    artifact = RFPSubmissionArtifact.objects.create(
        binding=binding, payload_sha256=version.payload_sha256, sha256=sha256(data).hexdigest(),
        size=len(data), content=data,
    )
    event(version.created_by, version.document.case, 'rfp.submission_pdf_prepared',
          version=version.pk, artifact=artifact.pk, sha256=artifact.sha256, size=artifact.size)
    return artifact


def metadata(**scope):
    return RFPSubmissionArtifact.objects.filter(**scope).only(*METADATA).first()


def requirement_findings(pack, artifact):
    """Evaluate one verified PDF against the exact stated facts, when present."""
    issues = []
    if pack.file_extension and pack.file_extension != 'pdf':
        issues.append('The client requested a different file format.')
    if pack.file_count is not None and pack.file_count != 1:
        issues.append('The number of PDFs does not match the requested file count.')
    if pack.file_size_bytes is not None:
        oversized = (artifact.size > pack.file_size_bytes or
                     (pack.file_size_rule == 'less_than' and artifact.size == pack.file_size_bytes))
        if oversized:
            issues.append('The PDF exceeds the requested file size limit.')
    return issues


def approved_format(binding, artifact):
    from .rfp_submission_pack import bound_pack

    if artifact.payload_sha256 != binding.version.payload_sha256:
        raise ValidationError('The prepared file no longer matches the exact client pack.')
    issues = requirement_findings(bound_pack(binding), artifact)
    if issues:
        raise ValidationError(issues)


def panel(actor, case, version):
    if version is None or version.audience != 'client' or version.template.definition['document_type'] not in (
            'rfp_response', 'project_artifact'):
        return None
    from .rfp_submission_pack import bound_pack, requirements

    if version.document.case_id != case.pk:
        return None
    artifact = metadata(binding__response__rfp__case=case, binding__version=version)
    if not artifact:
        return None
    try:
        require(actor, case, 'rfp.read')
        require(actor, case, 'document.read')
    except PermissionDenied:
        return None
    pack = bound_pack(artifact.binding)
    return {'file': artifact, 'version': version.pk, 'requirements': bool(requirements(pack)),
            'findings': requirement_findings(pack, artifact)}


@login_required
@require_safe
@never_cache
def open_pdf(request, case_id, version_id):
    case = get_object_or_404(visible_cases(request.user), pk=case_id)
    return pdf_response(request.user, case, version_id)


def pdf_response(actor, case, version_id, *, as_attachment=False):
    require(actor, case, 'rfp.read')
    require(actor, case, 'document.read')
    artifact = get_object_or_404(
        RFPSubmissionArtifact.objects.select_related('binding__version').only(
            *METADATA, 'binding__version__number', 'binding__version__payload_sha256',
            'binding__version__source_manifest'),
        binding__response__rfp__case=case, binding__version__document__case=case, binding__version_id=version_id)
    version = artifact.binding.version
    expected = {(item['id'], item['version'], item['sha256']) for item in version.source_manifest}
    visible = public_evidence(case.evidence.filter(pk__in={item[0] for item in expected}))
    if set(visible.values_list('pk', 'version', 'sha256')) != expected:
        raise PermissionDenied('The exact bid pack sources are outside current reading authority.')
    data = bytes(RFPSubmissionArtifact.objects.values_list('content', flat=True).get(pk=artifact.pk))
    if (artifact.payload_sha256 != version.payload_sha256 or len(data) != artifact.size
            or sha256(data).hexdigest() != artifact.sha256):
        raise Http404('The saved PDF no longer matches the exact pack.')
    response = FileResponse(BytesIO(data), as_attachment=as_attachment, filename=f'bid-pack-v{version.number}.pdf',
                            content_type='application/pdf')
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response
