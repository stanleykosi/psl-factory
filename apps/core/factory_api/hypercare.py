"""Source observations and exact release stability qualification."""
from time import monotonic

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.read_observation import read_observation
from apps.core.services import lock_case
from apps.identity.services import active_case_grants
from apps.policy.change_drafts import draft_standard_policy
from apps.policy.delivery_validators import METRIC, criteria_schema
from apps.policy.services import active_component, reference_values
from apps.workflows import factory_hypercare as domain
from apps.workflows.stability_forms import observation_forms

from .commands import require_line
from .delivery import PROOF, proof_rows, recorded, RESPONSE
from .http import BOOLEAN, DATETIME, ID, TEXT, array, choice, endpoint, nullable, obj
from .reviews import VERSIONS


COMPONENT = 'D11.hypercare_criteria_ref'
OWNER = choice('Engineering', 'Infrastructure')
CONFIRMED = nullable(BOOLEAN)
CRITERIA = {'oneOf': [criteria_schema(), criteria_schema(include_issue_clearance=True)]}
METRIC_KEY = METRIC['properties']['key']
SECTION = obj({'name': choice(*domain.TITLES), 'status': choice('ready', 'held'), 'finding': nullable(TEXT)})


@endpoint(response=obj({**VERSIONS, 'dossier_id': ID, 'checks': array(SECTION), 'proofs': array(PROOF, limit=50),
    'configuration_id': nullable(ID), 'criteria': nullable(CRITERIA), 'can_draft_criteria': BOOLEAN,
    'observation_owners': array(OWNER), 'assessment_id': nullable(ID),
    'qualified': CONFIRMED, 'observations': array(obj({'owner': OWNER, 'source_id': ID, 'verification_id': ID})),
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
        try:
            configuration = active_component(COMPONENT, work.case)
            criteria = reference_values(configuration)[0]
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
