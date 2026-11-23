"""Source observations and exact release stability qualification."""
from time import monotonic

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.read_observation import read_observation
from apps.core.services import lock_case
from apps.identity.services import active_case_grants, require
from apps.pmo.delivery_closure import hypercare_inputs
from apps.pmo.release_proofs import own_pdfs
from apps.policy.change_drafts import draft_standard_policy
from apps.policy.delivery_validators import METRIC, criteria_schema
from apps.policy.services import active_component, reference_values
from apps.workflows import factory_hypercare as domain
from apps.workflows.stability_forms import observation_forms

from .commands import require_line
from .delivery import NOTE, PIN, PROOF, REFERENCE, RESPONSE, SIGNER, proof_rows, recorded, signer_attestation
from .http import BOOLEAN, DATETIME, ID, TEXT, array, choice, endpoint, nullable, obj
from .reviews import VERSIONS


COMPONENT = 'D11.hypercare_criteria_ref'
OWNER = choice('Engineering', 'Infrastructure')
CONFIRMED = nullable(BOOLEAN)
CRITERIA = {'oneOf': [criteria_schema(), criteria_schema(include_issue_clearance=True)]}
METRIC_KEY = METRIC['properties']['key']
SECTION = obj({'name': choice(*domain.TITLES), 'status': choice('ready', 'held'), 'finding': nullable(TEXT)})


@endpoint(response=obj({**VERSIONS, 'can_record_release': BOOLEAN, 'readiness_ids': array(ID, limit=50),
    'release_evidence': array(PROOF, limit=50), 'signatures': array(PROOF, limit=50),
    'private_logs': array(obj({'id': ID, 'filename': TEXT}), limit=50),
    'acceptance_packet': nullable(PIN), 'receipts': array(obj({'id': ID, 'version_id': ID, 'at': DATETIME}))}),
    summary='Read actual release and Go-live acceptance controls for independently started stability work')
@read_observation
def events(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, domain.DEFINITION)
    with limit_queries(800, deadline=monotonic() + 8):
        dossier = domain.subject(work, actor, current=False)
        controls = domain.event_controls(actor, work, dossier, domain.checks(dossier))
        evidence = public_evidence(work.case.evidence.all()).only('kind', 'version').order_by('-pk')
        can_release = controls['can_record_release']
        logs = []
        if can_release:
            try:
                require(actor, work.case, 'evidence.add')
            except PermissionDenied:
                pass
            else:
                logs = [{'id': row.pk, 'filename': row.name} for row in own_pdfs(actor, work.case).order_by('-pk')[:50]]
        return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'can_record_release': can_release,
                'readiness_ids': list(dossier.records.filter(kind='release_ready').order_by('-pk').values_list('pk', flat=True)[:50])
                                 if can_release else [],
                'release_evidence': proof_rows(evidence[:50]) if can_release else [],
                'signatures': proof_rows(evidence.filter(kind='signature')[:50]) if controls['can_accept_go_live'] else [],
                'private_logs': logs, 'acceptance_packet': controls['acceptance_packet'],
                'receipts': [{'id': row.pk, 'version_id': row.publication.version_id, 'at': row.created_at}
                             for row in controls['go_live_receipts']]}


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': 'release'}, **VERSIONS, 'readiness_id': nullable(ID), 'released_at': DATETIME,
         'reference': REFERENCE, 'evidence_id': ID, 'note': NOTE,
         'environment': nullable({**TEXT, 'maxLength': 160}), 'private_log_id': nullable(ID)}),
    obj({'action': {'const': 'acceptance'}, **VERSIONS, 'packet': PIN, 'receipt_id': ID,
         'pm_signature_id': ID, 'client_signature_id': ID, 'signers': obj({'PM': SIGNER, 'Client': SIGNER}),
         'note': NOTE}),
]}, response=RESPONSE, status=201,
    summary='Record the observed release or the separate exact PM and client signatures')
def record_event(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, domain.DEFINITION)
    action = body['action']
    if action == 'release':
        data = {'readiness': body['readiness_id'], 'released_at': body['released_at'], 'reference': body['reference'],
                'evidence': body['evidence_id'], 'note': body['note'], 'deployment_environment': body['environment'],
                'private_log': body['private_log_id']}
    else:
        require(actor, work.case, 'delivery.manage')
        dossier = domain.subject(work, actor, current=False)
        receipt = next((row for row in domain.receipts(dossier) if row.pk == body['receipt_id']), None)
        if receipt is None:
            raise ValidationError('Choose the exact delivered Go-live receipt.')
        ids = {'PM': body['pm_signature_id'], 'Client': body['client_signature_id']}
        data = {'receipt': receipt.pk, 'packet': body['packet'], 'pm_signature': ids['PM'], 'client_signature': ids['Client'],
                'note': body['note'], 'attestation': signer_attestation(actor, dossier, receipt, ids, body['signers'])}
    row = domain.observe(actor, work.pk, body['expected_revision'], body['case_revision'], action, data)
    return recorded(work, row)


@endpoint(response=obj({**VERSIONS, 'dossier_id': ID, 'checks': array(SECTION), 'proofs': array(PROOF, limit=50),
    'configuration_id': nullable(ID), 'criteria': nullable(CRITERIA), 'can_draft_criteria': BOOLEAN,
    'observation_owners': array(OWNER), 'assessment_id': nullable(ID),
    'qualified': CONFIRMED, 'observations': array(obj({'owner': OWNER, 'source_id': ID, 'verification_id': ID})),
    'criterion_results': array(obj({'owner': nullable(OWNER), 'key': TEXT, 'status': choice('met', 'not_met', 'unknown')})),
    'findings': array(TEXT), 'due_at': nullable(DATETIME), 'verified': BOOLEAN,
}), summary='Read active stability criteria, current observations and the exact qualified assessment')
@read_observation
def detail(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, domain.DEFINITION)
    with limit_queries(800, deadline=monotonic() + 8):
        dossier = domain.subject(work, actor, current=False)
        grants = {action for _, action in active_case_grants(actor, [work.case_id])}
        checks = domain.checks(dossier)
        state = checks['stability'].get('inputs', {})
        configuration = None
        criteria = None
        criterion_results = []
        try:
            configuration = active_component(COMPONENT, work.case)
            criteria = reference_values(configuration)[0]
            if state:
                _, criterion_results = hypercare_inputs(dossier, detailed=True)
        except (PermissionDenied, ValidationError):
            pass
        owners = [form.owner_name for form in observation_forms(actor, work)]
        assessment = domain.assessed(work)
        current = bool(assessment and assessment.snapshot == state)
        verified = False
        if current and work.status == 'verified':
            try:
                verified = domain.verify(work, actor)['verified']
            except (PermissionDenied, ValidationError):
                pass
        proofs = proof_rows(public_evidence(work.case.evidence.all()).only('kind', 'version').order_by('-pk')[:50]) if owners else []
    return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'dossier_id': dossier.pk,
            'checks': [{'name': name, 'status': check['status'], 'finding': check.get('finding') or None}
                       for name, check in checks.items()], 'proofs': proofs,
            'configuration_id': configuration.pk if configuration else None, 'criteria': criteria,
            'can_draft_criteria': 'policy.configure' in grants, 'observation_owners': owners,
            'assessment_id': assessment.pk if current else None, 'qualified': state.get('qualified'),
            'criterion_results': criterion_results,
            'observations': [{'owner': owner, 'source_id': ids[0], 'verification_id': ids[1]}
                             for owner, ids in state.get('sources', {}).items()],
            'findings': state.get('findings', []), 'due_at': state.get('due_at'), 'verified': verified}


@endpoint(method='POST', request=obj({**VERSIONS, 'configuration_id': ID, 'owner': OWNER, 'observed_at': DATETIME,
    'confirmed': CONFIRMED, 'reference': {**TEXT, 'maxLength': 240}, 'evidence_id': ID,
    'verify_sample': BOOLEAN, 'metrics': {'type': 'object', 'propertyNames': METRIC_KEY,
                                        'maxProperties': 20, 'additionalProperties': nullable({'type': 'number'})},
}, optional=('verify_sample',)), response=RESPONSE, status=201,
          summary='Capture exact supplied stability observations against the current reviewed metric definitions')
def observe(request, work_id, *, body):
    work = require_line(request.user, work_id, domain.DEFINITION)
    form = next((row for row in observation_forms(request.user, work) if row.owner_name == body['owner']), None)
    if form is None:
        raise PermissionDenied('A current reviewed stability rule and permitted source owner are required.')
    if form.configuration_id != body['configuration_id']:
        raise ValidationError('STALE_VERSION: Review the current stability rule before recording observations.')
    keys = [metric['key'] for metric in form.metrics]
    if set(keys) != set(body['metrics']):
        raise ValidationError('Supply each metric in the current rule. Use null for an unknown value.')
    if body.get('verify_sample') and not work.case.synthetic:
        raise ValidationError('Synthetic verification requires a sample project.')
    data = {'configuration': body['configuration_id'], 'owner': body['owner'], 'observed_at': body['observed_at'],
            'confirmed': {True: 'yes', False: 'no', None: 'unknown'}[body['confirmed']],
            'reference': body['reference'], 'evidence': body['evidence_id'], 'verify_sample': body.get('verify_sample', False),
            **{f'metric_{i}': body['metrics'][key] for i, key in enumerate(keys)}}
    source = domain.record_stability(request.user, work.pk, body['expected_revision'], body['case_revision'], data)
    return recorded(work, source)


@endpoint(method='POST', request=obj({'case_revision': VERSIONS['case_revision'], 'criteria': CRITERIA,
    'evidence_id': ID, 'effective_from': DATETIME}), response=obj({'configuration_id': ID}), status=201,
          summary='Draft evidenced stability criteria for separate policy review')
@transaction.atomic
def draft_criteria(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, domain.DEFINITION)
    case = lock_case(actor, work.case_id, 'policy.configure', body['case_revision'])
    if not public_evidence(case.evidence.filter(pk=body['evidence_id'], kind='policy_decision')).exists():
        raise ValidationError('Choose an available project policy decision.')
    configuration = draft_standard_policy(actor, case.pk, COMPONENT, body['criteria'], body['evidence_id'], body['effective_from'])
    return {'configuration_id': configuration.pk}
