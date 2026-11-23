"""Reviewed HR field visibility and typed department policy drafts."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from apps.core.evidence_access import public_evidence
from apps.core.services import bump, lock_case
from apps.identity.services import active_case_grants, require
from apps.policy import impact
from apps.policy.bu_drafts import draft_bu_policy
from apps.policy.bu_validators import SCHEMAS as BU_RULES
from apps.policy.approval_drafts import draft_approval_policy
from apps.policy.approval_validators import SCHEMAS as APPROVAL_RULES
from apps.policy.hrfinance_drafts import draft_disclosure_fields, disclosure_field_review, review_disclosure_fields
from apps.policy.hrfinance_validators import DISCLOSURE, EXTENDED_FIELD_LIST, FIELDS
from apps.policy.ledger_drafts import draft_ledger_policy
from apps.policy.ledger_validators import SCHEMAS as LEDGER_RULES
from apps.policy.models import Configuration
from apps.policy.payroll_drafts import draft_payroll_policy
from apps.policy.payroll_validators import SCHEMAS as PAYROLL_RULES, SUCCESSOR_SCHEMAS
from apps.policy.ppe_drafts import draft_ppe_policy
from apps.policy.ppe_validators import SCHEMAS as ASSET_RULES
from apps.policy.schedule_drafts import draft_schedule_policy
from apps.policy.schedule_validators import SCHEMAS as SCHEDULE_RULES
from apps.policy.registry import envelope_schema
from apps.policy.services import reference_values, register_reference, resolve, save_draft, validate_envelope
from apps.policy.validation_drafts import draft_validation_policy
from apps.policy.validation_validators import ACCEPTANCE, NATIVE_VALUE, PRIVATE_VALUE, SCHEMAS as EVIDENCE_RULES

from .delivery import PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, Problem, array, choice, endpoint, nullable, obj
from .policy_reviews import CONFIG, config_payload, states


FIELD = EXTENDED_FIELD_LIST['items']
VERSION = obj({'id': ID, 'version': REVISION, 'state': choice('draft', 'validated', 'active', 'revoked', 'superseded')})
FIELD_RESULT = obj({'case_revision': REVISION, 'configuration_id': ID, 'version': REVISION,
    'original': array(FIELD), 'proposed': array(FIELD), 'reason': TEXT,
    'state': VERSION['properties']['state'], 'current': BOOLEAN})


@endpoint(response=obj({'case_revision': REVISION, 'base_id': nullable(ID), 'latest_version': nullable(REVISION),
    'status': TEXT, 'fields': array(obj({'key': FIELD, 'included': BOOLEAN, 'supported': BOOLEAN})),
    'draft': nullable(VERSION), 'can_propose': BOOLEAN, 'proofs': array(PROOF, limit=30)}),
    summary='Read current permitted HR field visibility and its latest reviewed proposal')
def visibility(request, case_id):
    actor = request.user
    case = impact.context(actor, case_id)
    policy = resolve(DISCLOSURE, case)
    config = value = latest = None
    status = policy.status
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    if policy.status == 'ACTIVE':
        try:
            config = impact.configuration(actor, case.pk, policy.configuration.pk)
            value = reference_values(config)[0]
            latest = states(Configuration.objects.filter(case=case, component=DISCLOSURE)).order_by('-revision').first()
            if latest:
                impact.configuration(actor, case.pk, latest.pk)
        except PermissionDenied:
            config = value = latest = None
            status = 'source_access_needed'
    draft = None
    if latest and latest.pk != config.pk and latest.current_state in ('draft', 'validated'):
        try:
            disclosure_field_review(actor, case.pk, latest.pk)
        except (ValidationError, PermissionDenied):
            pass
        else:
            draft = {'id': latest.pk, 'version': latest.revision, 'state': latest.current_state}
    can_propose = value is not None and 'policy.configure' in grants
    evidence = public_evidence(case.evidence.filter(kind='policy_decision')).only('id', 'kind', 'version').order_by('-pk')
    return {'case_revision': case.revision, 'base_id': config.pk if config else None,
            'latest_version': latest.revision if latest else None, 'status': status, 'draft': draft,
            'fields': [{'key': key, 'included': key in value['allowed_fields'],
                        'supported': key in value.get('source_fields', FIELDS)} for key in FIELD['enum']] if value else [],
            'can_propose': can_propose, 'proofs': proof_rows(evidence[:30]) if can_propose else []}


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'base_id': ID, 'latest_version': REVISION,
    'fields': EXTENDED_FIELD_LIST, 'evidence_id': ID, 'effective_from': DATETIME, 'reason': {**TEXT, 'maxLength': 1000}}),
    response=CONFIG, status=201, summary='Draft exact HR field changes separately from other approved disclosure terms')
def propose(request, case_id, *, body):
    actor = request.user
    case = impact.context(actor, case_id)
    seen = draft_disclosure_fields(actor, case.pk, body['base_id'], body['latest_version'], body['fields'], body['evidence_id'],
                                   parse_datetime(body['effective_from']), body['case_revision'], reason=body['reason'])
    return config_payload(states(Configuration.objects.all()).get(pk=seen.pk))


@endpoint(response=FIELD_RESULT, summary='Compare exact currently reviewed HR visibility fields with the proposed revision')
def field_review(request, case_id, configuration_id):
    case = impact.context(request.user, case_id)
    review = disclosure_field_review(request.user, case.pk, configuration_id)
    return {'case_revision': case.revision, 'configuration_id': configuration_id,
            'version': review['configuration'].revision, 'state': review['state'], 'current': review['current'],
            'original': review['original']['allowed_fields'], 'proposed': review['proposed']['allowed_fields'],
            'reason': review['reason']}


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'state': choice('draft', 'validated'),
    'action': choice('validate', 'activate')}), response=CONFIG, summary='Review and apply the exact proposed HR field visibility')
def decide(request, case_id, configuration_id, *, body):
    case = impact.context(request.user, case_id)
    review_disclosure_fields(request.user, case.pk, configuration_id, body['state'], body['action'], body['case_revision'])
    return config_payload(states(Configuration.objects.all()).get(pk=configuration_id))


DRAFTERS = {key: (definition[1], function) for definitions, function in (
    (BU_RULES, draft_bu_policy), (LEDGER_RULES, draft_ledger_policy), (ASSET_RULES, draft_ppe_policy),
    (SCHEDULE_RULES, draft_schedule_policy), (EVIDENCE_RULES, draft_validation_policy),
    (APPROVAL_RULES, draft_approval_policy), (PAYROLL_RULES, draft_payroll_policy),
) for key, definition in definitions.items()}
DRAFTERS[ACCEPTANCE] = ({'anyOf': [EVIDENCE_RULES[ACCEPTANCE][1], PRIVATE_VALUE, NATIVE_VALUE]}, draft_validation_policy)
for key, (_, successor) in SUCCESSOR_SCHEMAS.items():
    DRAFTERS[key] = ({'anyOf': [PAYROLL_RULES[key][1], successor]}, draft_payroll_policy)
POLICY_DRAFT = {'oneOf': [obj({'component': {'const': key}, 'case_revision': REVISION, 'evidence_id': ID,
                              'effective_from': DATETIME, 'value': fields})
                          for key, (fields, _) in DRAFTERS.items()]}


@endpoint(method='POST', request=POLICY_DRAFT, response=CONFIG, status=201,
    summary='Draft a supported typed Finance and evidence policy using its existing validator and owner decision')
@transaction.atomic
def draft_policy(request, case_id, *, body):
    actor = request.user
    case = lock_case(actor, case_id, 'policy.configure', body['case_revision'])
    require(actor, case, 'case.read')
    require(actor, case, 'policy.read')
    if not public_evidence(case.evidence.filter(pk=body['evidence_id'], kind='policy_decision')).exists():
        raise Problem(422, 'invalid_input', 'Choose an available owner decision from this project.')
    component = body['component']
    previous = Configuration.objects.filter(case=case, component=component).order_by('-revision').first()
    if previous:
        impact.configuration(actor, case.pk, previous.pk)
    _, operation = DRAFTERS[component]
    config = operation(actor, case.pk, component, body['value'], body['evidence_id'], parse_datetime(body['effective_from']))
    validate_envelope(case, config.envelope)
    bump(case)
    return config_payload(states(Configuration.objects.all()).get(pk=config.pk))


ENVELOPE = {key: value for key, value in envelope_schema().items() if key not in ('$schema', '$id')}
REFERENCE = obj({'id': ID, 'ref': TEXT, 'version': REVISION, 'schema_ref': TEXT, 'sha256': TEXT})


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'ref': {**TEXT, 'maxLength': 160},
    'schema_ref': {**TEXT, 'pattern': '^schema:', 'maxLength': 240}, 'content': {}, 'evidence_id': ID}),
    response=REFERENCE, status=201, summary='Register exact supplied owner evidence for a policy document')
@transaction.atomic
def register_policy_reference(request, case_id, *, body):
    actor = request.user
    case = lock_case(actor, case_id, 'policy.configure', body['case_revision'])
    require(actor, case, 'case.read')
    require(actor, case, 'policy.read')
    if not public_evidence(case.evidence.filter(pk=body['evidence_id'], kind='policy_decision')).exists():
        raise Problem(422, 'invalid_input', 'Choose an available owner decision from this project.')
    reference = register_reference(actor, case.pk, body['ref'], body['schema_ref'], body['content'], body['evidence_id'])
    bump(case)
    return {key: getattr(reference, key) for key in REFERENCE['properties']}


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'envelope': ENVELOPE}), response=CONFIG,
    status=201, summary='Draft a policy envelope and validate its exact scoped, versioned owner references')
@transaction.atomic
def draft_envelope(request, case_id, *, body):
    actor = request.user
    case = lock_case(actor, case_id, 'policy.configure', body['case_revision'])
    require(actor, case, 'case.read')
    require(actor, case, 'policy.read')
    config = save_draft(actor, case.pk, body['envelope'])
    impact.configuration(actor, case.pk, config.pk)
    validate_envelope(case, config.envelope)
    bump(case)
    return config_payload(states(Configuration.objects.all()).get(pk=config.pk))
