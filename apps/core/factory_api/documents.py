from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse

from apps.core.read_budget import ReadBudget, ReadLimit
from apps.documents import controlled, design_review, template_catalog, template_uploads
from apps.documents.template_access import visible_templates
from apps.identity.services import active_case_grants, require, visible_cases
from apps.workflows.models import HumanTask
from .http import BOOLEAN, ID, REVISION, TEXT, UUID, Problem, array, choice, endpoint, obj


def report(actor, case_id, version_id):
    case = get_object_or_404(visible_cases(actor), pk=case_id)
    require(actor, case, 'document.read')
    version = get_object_or_404(design_review.visible_reports(case).select_related('template', 'document'), pk=version_id)
    design_review.sources_for(case, version)
    return case, version


@endpoint(response=obj({'title': TEXT, 'version': REVISION, 'revision': REVISION, 'audience': TEXT,
    'current': BOOLEAN, 'decisions': array(TEXT), 'django_url': TEXT, 'preview': array(obj({'field': TEXT, 'text': {'type':'string'}}))}),
    summary='Read the current audience preview and available decisions for an exact standalone report')
def preview(request, case_id, version_id):
    actor = request.user
    case, version = report(actor, case_id, version_id)
    task = HumanTask.objects.filter(version=version, status='open').first()
    current = version.document.current_id == version.pk
    decisions = []
    if current and task and (case.pk, 'document.review_controlled') in active_case_grants(actor, [case.pk]) and not controlled.preflight(version):
        decisions = [key for key, _ in design_review.possible_verdicts(actor, case, task)]
    return {'title': version.document.title, 'version': version.number, 'revision': case.revision,
            'current': current, 'audience': version.audience, 'decisions': decisions,
            'preview': [{'field': section['heading'], 'text': section['text']} for section in version.payload['sections']],
            'django_url': reverse('design_document_review', args=[case.pk, version.pk])}


@endpoint(method='POST', request=obj({'expected_revision': REVISION, 'verdict': choice('approve','return','reject'),
    'delegated': BOOLEAN, 'note': {**TEXT, 'maxLength': 4000}}), response=obj({'review_id': ID, 'verdict': TEXT}),
    summary='Approve or return the exact standalone report version through its native review')
@transaction.atomic
def decide(request, case_id, version_id, *, body):
    case, version = report(request.user, case_id, version_id)
    if controlled.preflight(version):
        raise Problem(422, 'action_unavailable', 'Resolve the document checks before recording a decision.')
    result = controlled.review_version(request.user, case.pk, version.pk, body['verdict'], body['note'],
                                       body['expected_revision'], body['delegated'])
    return {'review_id': result.pk, 'verdict': result.verdict}


@endpoint(method='POST', multipart=True, request=obj({'previous': ID, 'proof': ID, 'revision': REVISION,
    'request_key': UUID, 'file': {'type':'string','format':'binary'}}),
    response=obj({'template_id': ID, 'version': ID, 'django_url': TEXT}), summary='Upload a replacement template and keep its original version')
def replace_template(request, case_id):
    case = get_object_or_404(visible_cases(request.user), pk=case_id, kind='project')
    for action in ('document.read','document.template','evidence.add'):
        require(request.user, case, action)
    if request.content_type != 'multipart/form-data':
        raise Problem(415, 'unsupported_media_type', 'Send the file with its template version and owner evidence.')
    if set(request.FILES) != {'file'} or len(request.FILES.getlist('file')) != 1:
        raise Problem(422, 'invalid_input', 'Choose one replacement file.')
    previous = request.POST.get('previous', '')
    form = template_catalog.UploadForm(request.POST, request.FILES)
    form.fields['proof'].queryset = template_catalog.recent_proofs(case)
    try:
        if previous.isascii() and previous.isdecimal() and len(previous) < 19:
            form.fields['previous'].queryset = visible_templates(request.user, case, candidate_ids=[int(previous)], budget=ReadBudget())
        if not form.is_valid():
            raise Problem(422, 'invalid_input', 'Check the selected template, file and owner evidence.')
        version = template_uploads.submit(request.user, case, **form.cleaned_data)
    except ReadLimit:
        raise Problem(503, 'read_limited', 'Open the template catalogue and try again.') from None
    except OSError:
        raise Problem(503, 'storage_unavailable', 'Check the upload with the same request key before retrying.') from None
    return {'template_id': version.pk, 'version': version.version, 'django_url': reverse('design_project_tab', args=[case.pk,'templates'])}
