"""Explicit policy publication, application and independent impact review."""

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from adapters import policy_impact as adapter
from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.views import accessible_case
from apps.identity.services import active_case_grants
from apps.policy import impact, scopes
from apps.policy.models import Configuration, ImpactAssessment, ScopeApplication, ScopeVersion

from .delivery import PROOF, proof_rows
from .http import BOOLEAN, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj
from .work import PAGE, page_number


KIND = choice('organization', 'project', 'contract', 'service')
STATES = choice('draft', 'validated', 'active', 'superseded', 'revoked')
PATH = {'type': 'string', 'maxLength': 300, 'pattern': '^/'}
PATHS = {**array(PATH, limit=100), 'uniqueItems': True}
SCALAR = {'type': ['string', 'number', 'boolean', 'null']}
BINDINGS = array(obj({'path': PATH, 'value': SCALAR}), limit=100)
ADAPTER = choice(*adapter.REGISTRY)
REASON = {**TEXT, 'maxLength': 2000}
VERDICT = choice('accept', 'reject', 'defer')
SOURCE = obj({'id': ID, 'configuration_id': ID, 'component': TEXT, 'kind': KIND, 'ref': TEXT,
              'revision': REVISION, 'state': STATES, 'health': TEXT, 'binding_paths': PATHS})
COMMANDS = {'oneOf': [
    obj({'action': {'const': 'create'}, 'configuration_id': ID, 'kind': KIND,
         'ref': {**TEXT, 'maxLength': 150}, 'binding_paths': PATHS}),
    obj({'action': {'const': 'transition'}, 'source_id': ID, 'state': choice('validated', 'active', 'revoked')}),
    obj({'action': {'const': 'apply'}, 'source_id': ID, 'evidence_id': ID, 'bindings': BINDINGS}),
]}


def scope(actor, case_id):
    case = accessible_case(actor, case_id)
    scopes.authorized(actor, case, 'policy.read')
    return case


def source_summary(row):
    return {'id': row.pk, 'configuration_id': row.configuration_id, 'component': row.configuration.component,
            'kind': row.kind, 'ref': row.ref, 'revision': row.revision, 'state': scopes.state(row),
            'health': scopes.source_health(row), 'binding_paths': row.binding_paths}


def readable_application(actor, application):
    try:
        scopes.authorized(actor, application.source.configuration.case, 'policy.read')
    except PermissionDenied:
        return {'configuration_id': application.configuration_id, 'source_id': None, 'status': 'source_access_needed'}
    return {'configuration_id': application.configuration_id, 'source_id': application.source_id,
            'status': scopes.application_health(application.configuration)}


@endpoint(response=obj({'sources': array(SOURCE, limit=15), 'applications': array(obj({
    'configuration_id': ID, 'source_id': nullable(ID), 'status': TEXT}), limit=15),
    'can_configure': BOOLEAN, 'can_activate': BOOLEAN, 'decisions': array(PROOF, limit=30), 'next_page': nullable(PAGE)}),
    query={'page': PAGE}, summary='List bounded scope versions and current contextual policy applications')
def catalogue(request, case_id):
    actor = request.user
    case = scope(actor, case_id)
    page = page_number(request)
    offset = (page - 1) * 15
    window = slice(offset, offset + 16)
    with limit_queries(950):
        versions = list(ScopeVersion.objects.filter(configuration__case=case).select_related('configuration__case')
                        .order_by('-pk')[window])
        applications = list(ScopeApplication.objects.filter(configuration__case=case).select_related(
            'configuration__case', 'source__configuration__case').order_by('-pk')[window])
        grants = {action for _, action in active_case_grants(actor, [case.pk])}
        configure = 'policy.configure' in grants
        evidence = public_evidence(case.evidence.filter(kind='policy_decision')).only('id', 'kind', 'version').order_by('-pk')
        return {'sources': [source_summary(row) for row in versions[:15]],
                'applications': [readable_application(actor, row) for row in applications[:15]],
                'can_configure': configure, 'can_activate': 'policy.activate' in grants,
                'decisions': proof_rows(evidence[:30]) if configure else [],
                'next_page': page + 1 if max(len(versions), len(applications)) > 15 and page < PAGE['maximum'] else None}


@endpoint(method='POST', request=COMMANDS, response=obj({'id': ID, 'state': STATES}), status=201,
          summary='Create, validate, activate, revoke or apply an exact scoped policy version')
def command(request, case_id, *, body):
    actor = request.user
    case = scope(actor, case_id)
    action = body['action']
    if action == 'create':
        config = get_object_or_404(Configuration, case=case, pk=body['configuration_id'])
        version = scopes.create(actor, config.pk, body['kind'], body['ref'], body['binding_paths'])
        return {'id': version.pk, 'state': scopes.state(version)}
    if action == 'transition':
        source = get_object_or_404(ScopeVersion, configuration__case=case, pk=body['source_id'])
        version = scopes.transition(actor, source.pk, body['state'])
        return {'id': version.pk, 'state': scopes.state(version)}
    policy = scopes.apply(actor, body['source_id'], case.pk, body['evidence_id'], body['bindings'])
    return {'id': policy.pk, 'state': 'draft'}


ASSESSMENT = obj({'id': ID, 'previous_id': ID, 'successor_id': ID, 'adapters': array(ADAPTER)})
METADATA = obj({'id': ID, 'domain': ADAPTER, 'state': TEXT, 'native_url_name': TEXT})


def metadata(records, key):
    return [{'id': row['id'], 'domain': key, 'state': row.get('state') or 'Recorded',
             'native_url_name': row.get('domain_route') or adapter.ROUTES[key]} for row in records]


@endpoint(response=obj({'available_adapters': array(ADAPTER), 'assessments': array(ASSESSMENT, limit=20),
    'can_capture': BOOLEAN, 'can_review': BOOLEAN, 'next_page': nullable(PAGE)}), query={'page': PAGE},
    summary='Read assessable policy impact domains and existing reassessments')
def impacts(request, case_id):
    actor = request.user
    case = impact.context(actor, case_id)
    page = page_number(request)
    offset = (page - 1) * 20
    rows = list(ImpactAssessment.objects.filter(previous__case=case).order_by('-pk')
                .values('id', 'previous_id', 'successor_id', 'adapters')[offset:offset + 21])
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    available = []
    for key in adapter.REGISTRY:
        try:
            adapter.authorize(actor, case, key)
        except PermissionDenied:
            continue
        available.append(key)
    return {'available_adapters': available, 'assessments': rows[:20], 'can_capture': 'policy.configure' in grants,
            'can_review': 'policy.activate' in grants, 'next_page': page + 1 if len(rows) > 20 and page < PAGE['maximum'] else None}


@endpoint(method='POST', request=obj({'previous_id': ID, 'successor_id': ID,
    'adapters': {**array(ADAPTER, limit=len(adapter.REGISTRY)), 'minItems': 1, 'uniqueItems': True},
    'evidence_id': ID, 'reason': REASON}), response=obj({'assessment_id': ID}), status=201,
    summary='Capture exact dependent records for a reviewed current policy successor')
def capture(request, case_id, *, body):
    row = impact.capture(request.user, case_id, body['previous_id'], body['successor_id'], body['adapters'],
                         body['evidence_id'], body['reason'])
    return {'assessment_id': row.pk}


@endpoint(response=obj({'id': ID, 'previous_id': ID, 'successor_id': ID, 'current': BOOLEAN, 'verdict': choice('unreviewed', 'accept', 'reject', 'defer'),
    'review_id': nullable(ID), 'review_authority_current': nullable(BOOLEAN), 'coverage': TEXT, 'uncovered': array(TEXT),
    'records': array(METADATA)}), summary='Read the exact reassessment and independently recheck domain and review authority')
def assessment(request, case_id, assessment_id):
    facts = impact.inspect(request.user, case_id, assessment_id)
    return {'id': facts['assessment'], 'previous_id': facts['previous'], 'successor_id': facts['successor'], 'current': facts['current'],
            'verdict': facts['verdict'], 'review_id': facts['review'], 'review_authority_current': facts['review_authority_current'],
            'coverage': facts['coverage'], 'uncovered': facts['uncovered'],
            'records': [item for key, rows in facts['domains'].items() for item in metadata(rows, key)]}


@endpoint(method='POST', request=obj({'verdict': VERDICT, 'evidence_id': ID, 'reason': REASON}),
          response=obj({'review_id': ID}), status=201, summary='Record the independent engineering reassessment review')
def review(request, case_id, assessment_id, *, body):
    row = impact.review(request.user, case_id, assessment_id, body['verdict'], body['evidence_id'], body['reason'])
    return {'review_id': row.pk}


@endpoint(response=obj({'configuration_id': ID, 'domain': ADAPTER, 'records': array(METADATA, limit=25),
    'next_cursor': nullable(TEXT), 'coverage': TEXT, 'uncovered': array(TEXT)}),
    query={'cursor': {**TEXT, 'maxLength': 4096}}, path_parameters={'domain': ADAPTER},
    summary='Read one actor-scoped page of current affected records and its stated coverage')
def impact_records(request, case_id, configuration_id, domain):
    facts = impact.page(request.user, case_id, configuration_id, domain, request.GET.get('cursor'))
    return {'configuration_id': facts['configuration'], 'domain': domain, 'records': metadata(facts['records'], domain),
            'next_cursor': facts['next_cursor'], 'coverage': facts['coverage'], 'uncovered': facts['uncovered']}
