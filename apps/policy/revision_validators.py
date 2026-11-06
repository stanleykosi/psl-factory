from .document_validators import typed, ROLES

SUPPORTED = {'D05.revision_invalidation_rules'}


def validate_reference(component, target, case):
    properties = {
        'unchanged_subject_reuse_roles': {'type': 'array', 'uniqueItems': True,
            'items': {'enum': ROLES[:4]}},
        'changed_cost_requires_full_chain': {'const': True}}
    schema = 'schema:psl/commercial-revision/v1'
    if target.schema_ref == 'schema:psl/commercial-revision/v2':
        schema = target.schema_ref
        properties['historical_authority'] = {'type':'object', 'minProperties':1,
            'properties': {kind: {'type':'object', 'properties': {
                'roles': {'type':'array','minItems':1,'maxItems':13,'uniqueItems':True,'items':{'enum':ROLES}},
                'scope': {'const':'authority_only'}, 'original_times': {'const':'preserve'},
                'financial_release_controls': {'const':'independent'}},
                'required':['roles','scope','original_times','financial_release_controls'],
                'additionalProperties':False} for kind in ['emergency_outcome','signed_adoption']},
            'additionalProperties':False}
    typed(target, schema, {
        'type': 'object', 'properties': properties,
        'required': ['unchanged_subject_reuse_roles', 'changed_cost_requires_full_chain'],
        'additionalProperties': False})
