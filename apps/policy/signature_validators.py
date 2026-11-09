"""Owner-supplied Q09 identity/method scope. Internal PM authority is not client authority."""
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate
from .document_validators import typed

COMPONENT = 'D11.client_signature_contract'
SCHEMA = 'schema:psl/client-signature-contract/v1'
TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 200, 'pattern': r'\S'}
ID = {'type': 'integer', 'minimum': 1}

def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}

PARTY = obj({'party_ref': TEXT, 'display_name': TEXT, 'identity_evidence_id': ID,
             'documents': {'type': 'array', 'minItems': 1, 'uniqueItems': True, 'items': {'enum': ['sow', 'prd']}}})
VALUE = obj({'parties': {'type': 'array', 'minItems': 0, 'maxItems': 100, 'items': PARTY},
             'methods': {'type': 'array', 'minItems': 0, 'maxItems': 20, 'uniqueItems': True, 'items': TEXT},
             'assurance': {'const': 'human_verified_reference_only'},
             'unchanged_prd_signature_reuse': {'enum': ['unconfigured', 'same_document_reference_allowed', 'fresh_document_signature_required']},
             'applicability': {'enum': ['client_project', 'internal_project', 'unresolved']},
             'signature_requirement': {'enum': ['required', 'not_applicable', 'unresolved']},
             'scope_evidence_id': {'anyOf': [ID, {'type': 'null'}]}, 'allow_synthetic': {'type': 'boolean'}})
SIGNATURE = obj({'evidence_id': ID, 'party_ref': {'anyOf': [TEXT, {'type': 'null'}]},
                 'method': {'anyOf': [TEXT, {'type': 'null'}]},
                 'locator': {'anyOf': [{'type': 'string', 'minLength': 1, 'maxLength': 500, 'pattern': r'\S'}, {'type': 'null'}]},
                 'human_verified': {'type': 'boolean'}})
SIGNATURES = {'type': 'object', 'properties': {kind: SIGNATURE for kind in ['sow', 'prd']}, 'additionalProperties': False}


def validate_reference(component, target, case, runtime=False):
    from apps.pmo.services import subject
    value = typed(target, SCHEMA, VALUE)
    if case.kind != 'project' or value['allow_synthetic'] != case.synthetic:
        raise ValidationError('Signature contract requires exact project and synthetic/operational scope')
    if len({p['party_ref'] for p in value['parties']}) != len(value['parties']):
        raise ValidationError('Signature party references must be unambiguous')
    applicability, requirement = value['applicability'], value['signature_requirement']
    if applicability == 'unresolved' and requirement != 'unresolved':
        raise ValidationError('Unresolved project classification cannot authorize signatures or an exemption')
    if requirement == 'not_applicable' and applicability != 'internal_project':
        raise ValidationError('Client projects cannot claim an internal signature exemption')
    if applicability == 'internal_project':
        subject(case, value['scope_evidence_id'], 'internal_project_scope')
    elif value['scope_evidence_id'] is not None:
        subject(case, value['scope_evidence_id'], 'client_project_scope')
    if requirement == 'required' and (not value['parties'] or not value['methods']):
        raise ValidationError('Required signatures need actual owner-eligible parties and methods')
    if requirement != 'required' and (value['parties'] or value['methods']):
        raise ValidationError('Unresolved or not-applicable signatures must not invent signer identities or methods')
    for party in value['parties']:
        subject(case, party['identity_evidence_id'], 'internal_signer_identity' if applicability == 'internal_project' else 'client_identity')
    return value
