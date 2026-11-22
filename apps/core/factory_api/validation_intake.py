"""Source evidence and reviewed validation packages for Start work."""

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime

from adapters.validation_evidence import LocalAcceptanceReportAdapter, pack_sources
from apps.agents.validation import investigate
from apps.core.evidence_access import public_evidence
from apps.core.models import Case
from apps.core.read_budget import limit_queries
from apps.documents import validation as native
from apps.documents.validation_models import DiscoverySource, ValidationExample, ValidationPackage
from apps.finance.acceptance import package_access
from apps.identity.services import require
from apps.policy.validation_validators import PROCESS_IDS

from .delivery import PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj


REFERENCE = {**TEXT, 'maxLength': 100}
NOTE = {**TEXT, 'maxLength': 4000}
PURPOSE = choice('meaning', 'expectations', 'acceptance')
VERDICT = choice('approve', 'return', 'disputed', 'reject', 'revoke')
LEVEL = choice('definition', 'synthetic_implementation', 'operational')
RECORD = obj({'id': ID, 'reference': TEXT, 'version': ID})
POSITION = obj({'level': LEVEL, 'scope': PROCESS_IDS, 'holds': array(TEXT),
    'reviews': obj({name: obj({'latest': nullable(ID), 'verdict': TEXT, 'use_status': TEXT}) for name in PURPOSE['enum']}),
    'production_authorized': {'const': False}, 'policy_activated': {'const': False}})


def case_for(actor, case_id):
    case = get_object_or_404(Case, pk=case_id)
    for action in ('case.read', 'validation.read'):
        require(actor, case, action)
    return case


@endpoint(response=obj({'case_revision': REVISION, 'evidence': array(PROOF, limit=60),
    'sources': array(RECORD, limit=40), 'examples': array(RECORD, limit=40), 'packages': array(RECORD, limit=30),
    'frozen_paths': array(TEXT, limit=100)}), summary='Read current permitted procedure source and validation intake choices')
def options(request, case_id):
    actor = request.user
    case = case_for(actor, case_id)
    evidence = public_evidence(case.evidence.all())
    sources = DiscoverySource.objects.filter(case=case, evidence_id__in=evidence.values('pk'))
    examples = ValidationExample.objects.filter(case=case, evidence_id__in=evidence.values('pk'))
    packages = []
    with limit_queries(1200):
        for package in ValidationPackage.objects.filter(case=case).select_related('case').order_by('-pk')[:30]:
            try:
                package_access(actor, package)
            except PermissionDenied:
                continue
            packages.append({key: getattr(package, key) for key in RECORD['properties']})
    try:
        require(actor, case, 'validation.source.capture')
    except PermissionDenied:
        paths = []
    else:
        paths = sorted(pack_sources())[:100]
    return {'case_revision': case.revision, 'evidence': proof_rows(evidence.only('id', 'kind', 'version').order_by('-pk')[:60]),
            'sources': list(sources.order_by('-pk').values('id', 'reference', 'version')[:40]),
            'examples': list(examples.order_by('-pk').values('id', 'reference', 'version')[:40]),
            'packages': packages, 'frozen_paths': paths}


INTAKE = {
    'source': {'reference': REFERENCE, 'evidence_id': ID, 'metadata': native.SOURCE},
    'frozen_source': {'reference': REFERENCE, 'path': {**TEXT, 'maxLength': 500}, 'metadata': native.SOURCE},
    'example': {'reference': REFERENCE, 'process_ids': PROCESS_IDS, 'scenario': choice('normal', 'exception'),
                'expected': {'type': 'object'}, 'evidence_id': ID},
    'package': {'reference': REFERENCE, 'package': native.PACKAGE, 'evidence_id': ID},
    'investigate': {},
}
REVIEW = {
    'review': {'purpose': PURPOSE, 'verdict': VERDICT, 'operation_key': REFERENCE, 'evidence_id': ID, 'reason': NOTE},
    'replay': {'operation_key': REFERENCE, 'evidence_id': ID},
    'followup': {'gap_key': REFERENCE, 'owner_id': ID, 'due_at': DATETIME, 'evidence_id': ID, 'reason': NOTE},
}
RESULT = obj({'id': ID, 'case_revision': REVISION})


@endpoint(method='POST', request={'oneOf': [obj({'action': {'const': action}, 'case_revision': REVISION, **fields})
    for action, fields in INTAKE.items()]}, response=RESULT, status=201,
    summary='Capture a validation source or example, assemble a scoped package, or investigate evidence gaps')
def capture(request, case_id, *, body):
    actor = request.user
    case = case_for(actor, case_id)
    expected = body['case_revision']
    action = body['action']
    if 'evidence_id' in body:
        get_object_or_404(public_evidence(case.evidence.all()), pk=body['evidence_id'])
    if action == 'source':
        record = native.capture_source(actor, case.pk, body['reference'], body['evidence_id'], body['metadata'], expected)
    elif action == 'frozen_source':
        record = native.import_pack(actor, case.pk, body['path'], body['reference'], body['metadata'], expected)
    elif action == 'example':
        record = native.capture_example(actor, case.pk, body['reference'], body['process_ids'], body['scenario'],
                                        body['expected'], body['evidence_id'], expected)
    elif action == 'package':
        record = native.prepare_package(actor, case.pk, body['reference'], body['package'], body['evidence_id'], expected)
    else:
        record = investigate(actor, case.pk, expected)
    case.refresh_from_db(fields=['revision'])
    return {'id': record.pk, 'case_revision': case.revision}


def package_for(actor, case, package_id):
    row = get_object_or_404(ValidationPackage.objects.select_related('case'), case=case, pk=package_id)
    package_access(actor, row)
    return row


def position(value):
    return {key: value[key] for key in ('level', 'scope', 'holds', 'reviews', 'production_authorized', 'policy_activated')}


@endpoint(response=obj({**RECORD['properties'], 'case_revision': REVISION, 'purpose': choice('B13', 'P13', 'P15'),
    'status': POSITION}), summary='Read the exact validation package, open holds and current human acceptance decisions')
def detail(request, case_id, package_id):
    actor = request.user
    case = case_for(actor, case_id)
    row = package_for(actor, case, package_id)
    with limit_queries(1500):
        value = native.position(row, actor)
    return {'id': row.pk, 'reference': row.reference, 'version': row.version, 'case_revision': case.revision,
            'purpose': row.payload['purpose'], 'status': position(value)}


@endpoint(method='POST', request={'oneOf': [obj({'action': {'const': action}, 'case_revision': REVISION, **fields})
    for action, fields in REVIEW.items()]}, response=RESULT, status=201,
    summary='Record an exact package decision, supplied replay or owner follow-up on a declared gap')
def command(request, case_id, package_id, *, body):
    actor = request.user
    case = case_for(actor, case_id)
    package_for(actor, case, package_id)
    args = (actor, case.pk, package_id)
    action = body['action']
    if action == 'review':
        record = native.review(*args, body['purpose'], body['verdict'], body['operation_key'], body['evidence_id'],
                               body['reason'], body['case_revision'])
    elif action == 'replay':
        record = native.record_replay(*args, body['evidence_id'], body['operation_key'], body['case_revision'])
    else:
        record = native.followup(*args, body['gap_key'], body['owner_id'], parse_datetime(body['due_at']),
                                 body['evidence_id'], body['reason'], body['case_revision'])
    case.refresh_from_db(fields=['revision'])
    return {'id': record.pk, 'case_revision': case.revision}


@endpoint(response=obj({'id': ID, 'verdict': VERDICT, 'package_id': ID, 'sha256': TEXT, 'status': POSITION,
    'requested_record_is_current': BOOLEAN, 'deployment_authorized': {'const': False}}),
    summary='Read the original acceptance report and whether it is current for the exact scoped evidence')
def receipt(request, case_id, review_id):
    case = case_for(request.user, case_id)
    with limit_queries(1500):
        value = LocalAcceptanceReportAdapter().read(request.user, case.pk, review_id)
    return {'id': value['review'], 'verdict': value['verdict'], 'package_id': value['package'],
            'sha256': value['sha256'], 'status': position(value['status']),
            'requested_record_is_current': value['requested_record_is_current'], 'deployment_authorized': False}
