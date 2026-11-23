from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse

from apps.core.read_budget import ReadBudget, ReadLimit, limit_queries
from apps.documents import controlled, design_review, template_catalog, template_uploads
from apps.documents.contracts import FIELDS, PMO_DOCUMENT_TYPES, digest
from apps.documents.delivery import operate_publication
from apps.documents.models import PublicationJob, PublicationReceipt, Template, TemplateFile
from apps.documents.template_access import visible_templates
from apps.documents.template_lists import LIST_PAGE, LIST_QUERY_LIMIT, template_page
from apps.identity.services import active_case_grants, require, visible_cases
from apps.workflows.models import HumanTask
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj


def report(actor, case_id, version_id):
    case = get_object_or_404(visible_cases(actor), pk=case_id)
    require(actor, case, 'document.read')
    version = get_object_or_404(design_review.visible_reports(case).select_related('template', 'document'), pk=version_id)
    design_review.sources_for(case, version)
    return case, version


@endpoint(response=obj({'title': TEXT, 'version': REVISION, 'revision': REVISION, 'audience': TEXT,
    'current': BOOLEAN, 'decisions': array(TEXT), 'django_url': TEXT, 'preview': array(obj({'field': TEXT, 'text': {'type':'string'}})),
    'template_name': TEXT, 'template_version': REVISION, 'sample': BOOLEAN}),
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
            'template_name': version.template.name, 'template_version': version.template.version, 'sample': case.synthetic,
            'preview': [{'field': section['heading'], 'text': section['text']} for section in version.payload['sections']],
            'django_url': reverse('design_document_review', args=[case.pk, version.pk])}


@endpoint(response=obj({'from_version': ID, 'to_version': ID, 'sections': array(obj({
    'key': choice(*FIELDS), 'before': nullable({'type': 'string'}), 'after': nullable({'type': 'string'}),
    'before_evidence_ids': array(ID, limit=20), 'after_evidence_ids': array(ID, limit=20),
    'change': choice('added', 'removed', 'changed', 'unchanged'),
}))}), query={'from_version': ID}, required_query=('from_version',),
          summary='Compare sections in two authorised versions of the same report and audience')
def compare(request, case_id, version_id):
    from .intake_sources import positive_id

    actor = request.user
    previous_id = positive_id(request, 'from_version')
    if previous_id is None:
        raise Problem(422, 'invalid_filter', 'Choose an earlier report version to compare.')
    _, current = report(actor, case_id, version_id)
    _, previous = report(actor, case_id, previous_id)
    if (previous.document_id != current.document_id or previous.audience != current.audience
            or previous.number >= current.number):
        raise Http404
    previous_fields = {part['heading']: part['text'] for part in previous.payload['sections']}
    current_fields = {part['heading']: part['text'] for part in current.payload['sections']}
    sections = []
    for key in FIELDS:
        before = previous_fields.get(key)
        after = current_fields.get(key)
        if before is None and after is None:
            continue
        change = 'unchanged'
        if before is None:
            change = 'added'
        elif after is None:
            change = 'removed'
        elif before != after:
            change = 'changed'
        sections.append({'key': key, 'before': before, 'after': after, 'change': change,
                         'before_evidence_ids': previous.fields[key]['evidence_ids'] if before is not None else [],
                         'after_evidence_ids': current.fields[key]['evidence_ids'] if after is not None else []})
    return {'from_version': previous.pk, 'to_version': current.pk, 'sections': sections}


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


FINGERPRINT = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
REPORT_COMMAND = {'oneOf': [
    obj({'action': {'const': 'request_review'}, 'revision': REVISION}),
    obj({'action': {'const': 'revise'}, 'revision': REVISION, 'sections': obj(
        {key: {'type': 'string', 'maxLength': 12000} for key in FIELDS}, optional=FIELDS)}),
    obj({'action': {'const': 'publish'}, 'revision': REVISION, 'packet': FINGERPRINT}),
    obj({'action': choice('retry', 'cancel'), 'revision': REVISION, 'job_id': ID,
         'reason': {**TEXT, 'maxLength': 4000}}),
]}


@endpoint(response=obj({
    'revision': REVISION, 'version_id': ID, 'current': BOOLEAN, 'can_request_review': BOOLEAN,
    'editable': array(obj({'key': choice(*FIELDS), 'text': {'type': 'string'}})),
    'findings': array(TEXT), 'review_status': nullable(TEXT),
    'publication': nullable(obj({'packet': FINGERPRINT, 'recipients': array(TEXT)})),
    'delivery': nullable(obj({'job_id': ID, 'state': TEXT, 'recovery_actions': array(choice('retry', 'cancel')),
        'receipts': array(obj({'id': ID, 'recorded_at': DATETIME}), limit=50), 'has_more_receipts': BOOLEAN})),
}), summary='Read exact report authoring, reviewed publication and original delivery controls')
def report_controls(http, case_id, version_id):
    actor = http.user
    case, version = report(actor, case_id, version_id)
    current = version.document.current_id == version.pk
    task = HumanTask.objects.filter(version=version).first()
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    job = PublicationJob.objects.filter(publication__version=version).first()
    findings = controlled.preflight(version)
    editable = []
    if current and 'document.draft' in grants and not job and (not task or task.status in {'returned', 'rejected', 'withdrawn'}):
        permitted = version.template.definition['audience_fields'].get(version.audience, [])
        editable = [{'key': key, 'text': section['text']} for key, section in version.fields.items() if key in permitted]
    packet = None
    if current and not job and not findings and 'document.publish' in grants:
        try:
            _, pins, _ = controlled.guard_reserve_publication(actor, case, version.pk)
        except (ValidationError, PermissionDenied):
            pass
        else:
            recipients = get_user_model().objects.in_bulk(pins['recipients'])
            packet = {'packet': digest(pins), 'recipients': [person.get_full_name() or person.username
                      for pk in pins['recipients'] if (person := recipients.get(pk))]}
    delivery = None
    if job:
        receipts = list(PublicationReceipt.objects.filter(publication_id=job.publication_id)
                        .only('created_at').order_by('pk')[:51])
        actions = []
        if not receipts and 'document.operate' in grants and job.status in {'held', 'pending'}:
            actions.append('cancel')
            if current and job.status == 'held':
                actions.append('retry')
        delivery = {'job_id': job.pk, 'state': job.status, 'recovery_actions': actions,
                    'receipts': [{'id': row.pk, 'recorded_at': row.created_at} for row in receipts[:50]],
                    'has_more_receipts': len(receipts) > 50}
    return {'revision': case.revision, 'version_id': version.pk, 'current': current, 'findings': findings,
            'can_request_review': current and not task and not findings and 'document.request_review' in grants,
            'review_status': task.status if task else None, 'editable': editable, 'publication': packet,
            'delivery': delivery}


@endpoint(method='POST', request=REPORT_COMMAND, response=obj({'id': ID, 'version_id': ID, 'revision': REVISION}),
          summary='Request review, revise, publish or recover the exact standalone report')
def report_command(http, case_id, version_id, *, body):
    actor = http.user
    case, version = report(actor, case_id, version_id)
    action, revision = body['action'], body['revision']
    if action == 'request_review':
        row = controlled.request_review(actor, case.pk, version.pk, revision)
    elif action == 'revise':
        row = version = design_review.revise_report(actor, case, version, revision, body['sections'])
    elif action == 'publish':
        row = design_review.publish_report(actor, case, version, revision, body['packet'])
    else:
        require(actor, case, 'document.operate')
        job = get_object_or_404(PublicationJob, pk=body['job_id'], publication__version=version)
        if job.status not in {'held', 'pending'} or action == 'retry' and version.document.current_id != version.pk:
            raise Problem(409, 'conflict', 'Check the original delivery before retrying or cancelling it.')
        operate_publication(actor, case.pk, job.pk, action, body['reason'], revision)
        row = job
    case.refresh_from_db(fields=['revision'])
    return {'id': row.pk, 'version_id': version.pk, 'revision': case.revision}


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


UPLOAD_GRANTS = ('document.read', 'document.template', 'evidence.add')
BINARY = {'type': 'string', 'format': 'binary'}
TEMPLATE_RESULT = obj({'template_id': ID, 'version': ID, 'django_url': TEXT})
SECTIONS = array(choice(*sorted(FIELDS)), limit=len(FIELDS))
CURSOR = {**TEXT, 'maxLength': 512}


@endpoint(response=obj({'items': array(obj({'id': ID, 'title': TEXT, 'version': REVISION, 'audience': TEXT,
    'api_url': TEXT, 'created_at': DATETIME, 'current': BOOLEAN}), limit=25), 'next_before': nullable(ID)}),
    query={'before': ID}, summary='List standalone report versions with currently readable source records')
def version_list(request, case_id):
    from .intake_sources import positive_id

    actor = request.user
    case = get_object_or_404(visible_cases(actor), pk=case_id)
    require(actor, case, 'document.read')
    before = positive_id(request, 'before')
    query = design_review.visible_reports(case).select_related('document', 'template').order_by('-pk')
    if before:
        query = query.filter(pk__lt=before)
    items = []
    with limit_queries(750):
        versions = list(query[:26])
        for version in versions[:25]:
            try:
                design_review.sources_for(case, version)
            except (PermissionDenied, ValidationError):
                continue
            items.append({'id': version.pk, 'title': version.document.title, 'version': version.number,
                          'audience': version.audience, 'created_at': version.created_at,
                          'current': version.document.current_id == version.pk,
                          'api_url': f'/api/v1/projects/{case.pk}/document-reviews/{version.pk}'})
    return {'items': items, 'next_before': versions[24].pk if len(versions) > 25 else None}


@endpoint(response=obj({
    'revision': REVISION, 'can_upload': BOOLEAN, 'cursor': nullable(CURSOR),
    'items': array(obj({'id': ID, 'name': TEXT, 'version': ID, 'download_url': nullable(TEXT),
        'document_type': TEXT, 'registered_by': TEXT, 'registered_at': nullable(DATETIME), 'sample': BOOLEAN}), limit=LIST_PAGE),
    'proofs': array(obj({'id': ID, 'kind': TEXT, 'version': ID}), limit=25),
}), query={'templates': CURSOR}, summary='Browse the visible template catalogue and first-version upload evidence')
def catalogue(request, case_id):
    actor = request.user
    case = get_object_or_404(visible_cases(actor), kind='project', pk=case_id)
    require(actor, case, 'document.read')
    with limit_queries(LIST_QUERY_LIMIT):
        versions, link = template_page(request, case)
        ids = [row.pk for row in versions]
        details = Template.objects.filter(case=case, pk__in=ids).select_related('created_by').in_bulk()
        registered = {value['template']: at for value, at in case.audit.filter(
            action='document.template_registered', data__template__in=ids).values_list('data', 'created_at')}
        attached = set(TemplateFile.objects.filter(case=case, template_id__in=ids)
                       .values_list('template_id', flat=True))
        grants = {action for _, action in active_case_grants(actor, [case.pk], actions=UPLOAD_GRANTS)}
        can_upload = grants.issuperset(UPLOAD_GRANTS)
        proofs = ([{'id': row.pk, 'kind': row.kind, 'version': row.version}
                   for row in template_catalog.recent_proofs(case)] if can_upload else [])
    return {'revision': case.revision, 'can_upload': can_upload,
            'cursor': parse_qs(urlsplit(link).query)['templates'][0] if link else None, 'proofs': proofs,
            'items': [{'id': row.pk, 'name': row.name, 'version': row.version,
                       'document_type': details[row.pk].definition['document_type'], 'sample': case.synthetic,
                       'registered_by': details[row.pk].created_by.get_full_name() or details[row.pk].created_by.get_username(),
                       'registered_at': registered.get(row.pk),
                       'download_url': reverse('design_template_download', args=[case.pk, row.pk]) if row.pk in attached else None}
                      for row in versions]}


@endpoint(method='POST', multipart=True, request=obj({
    'name': {**TEXT, 'maxLength': 160}, 'document_type': choice(*sorted(PMO_DOCUMENT_TYPES)),
    'required': {**SECTIONS, 'minItems': 1}, 'internal': SECTIONS, 'client': SECTIONS, 'management': SECTIONS,
    'proof': ID, 'revision': REVISION, 'request_key': UUID, 'file': BINARY,
}, optional=('internal', 'client', 'management')), response=TEMPLATE_RESULT, status=201,
          summary='Register the first version of a private project template with owner evidence')
def first_template(request, case_id):
    actor = request.user
    case = get_object_or_404(visible_cases(actor), kind='project', pk=case_id)
    for action in UPLOAD_GRANTS:
        require(actor, case, action)
    form = template_catalog.NewTemplateForm(request.POST, request.FILES)
    form.fields['proof'].queryset = template_catalog.recent_proofs(case)
    if not form.is_valid():
        raise Problem(422, 'invalid_input', 'Check the template fields, file and owner evidence.',
                      fields=[{'name': key, 'message': messages[0]} for key, messages in form.errors.items()])
    try:
        version = template_uploads.submit(actor, case, **form.cleaned_data)
    except OSError as exc:
        raise Problem(503, 'storage_unavailable', 'Check the upload with the same request key before retrying.') from exc
    return {'template_id': version.pk, 'version': version.version,
            'django_url': reverse('design_project_tab', args=[case.pk, 'templates'])}
