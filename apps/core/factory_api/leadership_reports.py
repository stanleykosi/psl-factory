"""Leadership narrative, reviewed project coverage and exact internal publication."""

import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404

from apps.core.evidence_access import CONFIRMED_CHANGE_SOURCE, forecast_private_query, other_private_query, public_evidence
from apps.core.read_budget import ReadBudget, limit_queries
from apps.core.services import add_evidence, lock_case
from apps.documents.delivery_readback import recipient_rows
from apps.documents.models import Template
from apps.documents.template_access import visible_templates
from apps.identity.services import active_case_grants, require
from apps.pmo import leadership_project_scope as scope_policy, leadership_reporting as native
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import active_component, reference_values
from apps.workflows import factory_leadership as workflow

from .commands import require_line
from .delivery import NOTE, PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, array, choice, endpoint, nullable, obj
from .intake import KEY, REF, START_RESULT, progress_result, start_projects
from .intake_sources import positive_id
from .reviews import VERDICT, VERSIONS
from .weekly_reports import RECIPIENT, TEMPLATE
from .work import WORK_RESULT, result


SECTION = obj({'text': {**TEXT, 'maxLength': 10000}, 'evidence_ids': {**array(ID, limit=18), 'minItems': 1, 'uniqueItems': True},
               'coverage': choice('supported', 'partial', 'unknown', 'not_applicable')})
NARRATIVE = {kind: obj({theme: SECTION for theme in themes}) for kind, themes in native.THEMES.items()}
DOMAINS = tuple(native.DOMAINS)
DOMAIN = choice(*DOMAINS)
SOURCE_COUNTS = obj({'scope': choice('selected_records', 'approved_project_scope', 'all_psl_projects'), 'captured_at': DATETIME,
    'projects': {'type': 'integer', 'minimum': 1},
    'counts': array(obj({'domain': DOMAIN, 'count': {'type': 'integer', 'minimum': 0}}), limit=len(DOMAINS)),
    'project_register': array(obj({'id': UUID, 'name': TEXT, 'unavailable_domains': array(DOMAIN, limit=len(DOMAINS))}))})
PARTICIPANTS = {**array(ID, limit=100), 'uniqueItems': True}
WINDOW = {'start_at': DATETIME, 'end_at': DATETIME}
KINDS = choice(*native.THEMES)
AUDIENCES = choice('internal', 'management')
SETUP = {
    'draft_scope': ({'enabled': BOOLEAN}, scope_policy.COMPONENT),
    'draft_reviewer': ({'role': nullable(choice('PMO Lead', 'Head of PMO'))}, native.REVIEW_COMPONENT),
    'draft_audience': ({'purpose': choice(*native.AUDIENCE_PURPOSES), 'participants': PARTICIPANTS}, native.AUDIENCE_COMPONENT),
}
SETUP_INPUT = [obj({'action': {'const': action}, 'case_revision': REVISION, 'evidence_id': ID,
                    'effective_from': DATETIME, **fields}) for action, (fields, _) in SETUP.items()]


def input_schema(kind):
    properties = {**workflow.INPUT['properties'], **WINDOW, 'kind': {'const': kind}}
    return obj({**properties, 'scope': obj({'domains': {**array(DOMAIN, limit=len(DOMAINS)), 'minItems': 1,
                                                       'uniqueItems': True}})}, optional=('scope', 'content_id', 'selections'))


INPUT = {kind: input_schema(kind) for kind in native.THEMES}


def work_schema(fields):
    return [obj({**fields, 'selection': INPUT[kind], 'sections': nullable(NARRATIVE[kind])}) for kind in native.THEMES]


def intake_case(actor, case_id, action):
    case = get_object_or_404(start_projects(actor, workflow.DEFINITION), pk=case_id)
    if action == 'report.read':
        scope_policy.require_report(actor, case)
    else:
        require(actor, case, action)
    return case


def picker(actor, case, domain, before):
    if domain is None:
        return [], None
    require(actor, case, native.DOMAINS[domain])
    model, path, evidence = next((model, path, evidence) for (domain_key, (_, model, path, evidence)) in
                                 zip(DOMAINS, native.SOURCE_OVERLAPS, strict=True) if domain_key == domain)
    safe = public_evidence(case.evidence.all())
    if domain == 'changes':
        confirmed = case.evidence.filter(source=CONFIRMED_CHANGE_SOURCE).exclude(forecast_private_query() | other_private_query())
        safe = safe | confirmed
    rows = model.objects.filter(**{path: case.pk, f'{evidence}__in': safe.values('pk')})
    if domain == 'escalations':
        rows = rows.filter(profile__state_id=F('profile__state__issue__current_id'))
    if before:
        rows = rows.filter(pk__lt=before)
    matches = list(rows.order_by('-pk').values_list('pk', evidence)[:31])
    return [{'id': pk, 'evidence_id': proof_id} for pk, proof_id in matches[:30]], matches[29][0] if len(matches) > 30 else None


@endpoint(response=obj({'revision': REVISION, 'source_domain': nullable(DOMAIN), 'sources': array(obj({'id': ID, 'evidence_id': ID}), limit=30),
    'next_before': nullable(ID), 'templates': array(TEMPLATE, limit=30), 'all_projects_available': BOOLEAN,
    'automatic_project_scope': BOOLEAN,
    'setup_actions': array(choice(*SETUP)), 'owner_evidence': array(PROOF, limit=30)}),
    query={'kind': KINDS, 'domain': DOMAIN, 'before': ID}, required_query=('kind',),
    summary='List permitted leadership source rows, owned templates and reviewed coverage options')
def options(request, case_id):
    actor = request.user
    case = intake_case(actor, case_id, 'report.read')
    kind, domain = request.GET.get('kind'), request.GET.get('domain')
    if kind not in native.THEMES or domain is not None and domain not in native.DOMAINS:
        raise ValidationError('Choose a leadership report purpose and available source type.')
    with limit_queries(600):
        rows, cursor = picker(actor, case, domain, positive_id(request, 'before'))
        automatic = scope_policy.department_lead(actor, case)
        grants = {action for _, action in active_case_grants(actor, [case.pk])}
        templates = []
        if automatic:
            required = sorted({'executive_summary', *native.THEMES[kind]})
            templates = list(Template.objects.filter(case=case, definition__document_type='status_report',
                definition__internal_review_required=kind == 'monthly_executive',
                definition__required_fields__contains=required, definition__required_fields__contained_by=required
            ).order_by('-pk').values('id', 'name', 'version')[:30])
        elif 'document.read' in grants:
            candidates = list(Template.objects.filter(case=case, definition__document_type='status_report',
                definition__internal_review_required=kind == 'monthly_executive').order_by('-pk').values_list('pk', flat=True)[:30])
            templates = list(visible_templates(actor, case, candidate_ids=candidates, budget=ReadBudget()).order_by('-pk').values(
                'id', 'name', 'version'))
        try:
            scope_policy.current_rule(case)
        except ValidationError:
            allowed = False
        else:
            allowed = True
        configure = 'policy.configure' in grants
        proof = public_evidence(case.evidence.filter(kind='policy_decision')).only('id', 'kind', 'version').order_by('-pk')[:30]
        return {'revision': case.revision, 'source_domain': domain, 'sources': rows, 'next_before': cursor,
                'templates': templates, 'all_projects_available': allowed or automatic, 'automatic_project_scope': automatic,
                'setup_actions': list(SETUP) if configure else [],
                'owner_evidence': proof_rows(proof) if configure else []}


def compose(actor, case, selection, narrative):
    inputs = {'content_id': None, 'selections': {domain: [] for domain in DOMAINS}, **selection}
    if narrative is not None:
        if inputs['content_id'] is not None or 'scope' in inputs:
            raise ValidationError('Choose one existing narrative, new cited narrative or reviewed project coverage.')
        require(actor, case, 'evidence.add')
        payload = json.dumps({'protocol': native.MODE, 'kind': inputs['kind'], 'sections': narrative}, sort_keys=True)
        source = 'Human-supplied leadership narrative'
        evidence = case.evidence.filter(kind=native.CONTENT, body=payload, created_by=actor, source=source).order_by('-pk').first()
        if evidence is None:
            evidence = add_evidence(actor, case.pk, native.CONTENT, payload, source)
        inputs['content_id'] = evidence.pk
    return inputs


@endpoint(method='POST', request={'oneOf': work_schema({'action': {'const': 'start'}, 'case_revision': REVISION,
    'key': KEY, 'reference': REF, 'background': BOOLEAN}) + SETUP_INPUT},
    response={'oneOf': [START_RESULT, obj({'configuration_id': ID, 'case_revision': REVISION})]}, status=201,
    summary='Start a cited leadership report or draft separately reviewed report settings')
@transaction.atomic
def submit(request, case_id, *, body):
    actor = request.user
    action = body['action']
    grant = 'factory.start' if action == 'start' else 'policy.configure'
    case = intake_case(actor, case_id, grant)
    case = lock_case(actor, case.pk, grant, body['case_revision'])
    if action == 'start':
        inputs = compose(actor, case, body['selection'], body['sections'])
        case.refresh_from_db(fields=['revision'])
        work = workflow.start(actor, case.pk, body['key'], inputs, body['reference'], case.revision)
        return progress_result(actor, work, body['background'])
    evidence = get_object_or_404(public_evidence(case.evidence.filter(kind='policy_decision')), pk=body['evidence_id'])
    fields, component = SETUP[action]
    value = {key: body[key] for key in fields}
    if action == 'draft_audience':
        try:
            current = dict(reference_values(active_component(component, case))[0])
        except ValidationError:
            current = dict.fromkeys(native.AUDIENCE_PURPOSES)
        current[value['purpose']] = sorted(value['participants']) or None
        value = current
    draft = draft_operator_policy(actor, case.pk, component, value, evidence.pk, body['effective_from'])
    case.refresh_from_db(fields=['revision'])
    return {'configuration_id': draft.pk, 'case_revision': case.revision}


def coverage(data):
    manifest = data['manifest']
    scope = manifest.get('project_scope')
    counts = scope['record_counts'] if scope else {key: len(manifest.get(key, ())) for key in DOMAINS}
    automatic = scope and scope['mode'] == scope_policy.LEAD_MODE
    return {'scope': scope_policy.LEAD_MODE if automatic else 'approved_project_scope' if scope else 'selected_records',
            'captured_at': data['captured_at'], 'projects': len(scope['projects']) if scope else 1,
            'project_register': [{'id': project['case'], 'name': project['name'],
                                  'unavailable_domains': project['unavailable_domains']} for project in scope['projects']]
            if automatic else [],
            'counts': [{'domain': key, 'count': counts[key]} for key in DOMAINS if key in counts]}


@endpoint(response=obj({**VERSIONS, 'kind': KINDS, 'audience': AUDIENCES, 'selection': workflow.INPUT,
    'coverage': SOURCE_COUNTS,
    'editable_sections': nullable({'oneOf': list(NARRATIVE.values())}), 'document_version_id': nullable(ID),
    'review_verdicts': array(VERDICT), 'can_correct': BOOLEAN, 'recipients': array(RECIPIENT), 'next_action': TEXT}),
    summary='Read the exact leadership review, editable narrative and verified recipient receipts')
def detail(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, workflow.DEFINITION)
    with limit_queries(900):
        if work.status == 'verified':
            return delivered(actor, work)
        panel = workflow.projection(actor, work)
        inputs = panel['data']['inputs']
        document = panel['document']
        selected = next((job for job in panel['jobs'] if document and job.publication.version_id == document.pk), None)
        sections = None
        if panel['can_correct'] and 'scope' not in inputs and inputs['content_id']:
            try:
                snapshot = workflow.inventory(actor, work.case, inputs)
                _, sections = native.content(work.case, inputs['kind'], inputs['content_id'], snapshot['sources'])
            except (ValidationError, PermissionDenied):
                pass
        delivery = recipient_rows(selected, document, panel['receipts'])
    return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'kind': inputs['kind'],
            'audience': inputs['audience'], 'selection': inputs, 'editable_sections': sections,
            'coverage': coverage(panel['data']),
            'document_version_id': document.pk if document else None, 'review_verdicts': panel['review_verdicts'],
            'can_correct': panel['can_correct'], 'next_action': panel['next_action'],
            'recipients': [{'name': row['recipient'], 'status': row['status'], 'recorded_at': row['at'],
                            'receipt_id': row['receipt'].pk if row['receipt'] else None} for row in delivery]}


def delivered(actor, work):
    data, document, _, publication, receipts = workflow.published(work, actor)
    inputs = data['inputs']
    rows = recipient_rows(publication.job, document, receipts)
    return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'kind': inputs['kind'],
            'audience': inputs['audience'], 'selection': inputs, 'editable_sections': None,
            'coverage': coverage(data),
            'document_version_id': document.pk, 'review_verdicts': [], 'can_correct': False,
            'next_action': 'Inspect the reviewed leadership report and its original delivery receipts.',
            'recipients': [{'name': row['recipient'], 'status': row['status'], 'recorded_at': row['at'],
                            'receipt_id': row['receipt'].pk if row['receipt'] else None} for row in rows]}


@endpoint(method='POST', request={'oneOf': work_schema({**VERSIONS, 'reason': {**NOTE, 'maxLength': 2000}})},
          response=WORK_RESULT, summary='Replace a selected leadership report with exact current cited sources')
@transaction.atomic
def correct(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, workflow.DEFINITION)
    action = 'evidence.add' if workflow.can_correct_automatic(actor, work) else 'factory.manage'
    case = lock_case(actor, work.case_id, action, body['case_revision'])
    inputs = compose(actor, case, body['selection'], body['sections'])
    case.refresh_from_db(fields=['revision'])
    return result(workflow.correct(actor, work.pk, body['expected_revision'], case.revision, inputs, body['reason']))
