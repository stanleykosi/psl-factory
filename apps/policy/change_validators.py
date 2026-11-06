"""Engineering proposal for Q04: explicit catalogue conditions and human gate reuse.

Only Product/Engineering scope gates are supported for reuse in v1. Costing,
client/timeline decisions and production release remain independent controls.
"""
from django.core.exceptions import ValidationError
from apps.core.models import Evidence
from .document_validators import typed

SUPPORTED = {'D01.change_type_catalogue', 'D01.satisfied_gate_map'}
REUSABLE_ROLES = ['Product', 'Engineering']
FLAGS = ['cost_impact', 'timeline_impact', 'client_facing']


def validate_reference(component, target, case):
    if component == 'D01.change_type_catalogue':
        content = typed(target, 'schema:psl/standard-catalogue-entry/v1', {
            'type': 'object', 'properties': {
                'key': {'type': 'string', 'pattern': '^[a-zA-Z0-9_-]{1,80}$'},
                'module': {'type': 'string', 'minLength': 1, 'maxLength': 160},
                'procedure_evidence_id': {'type': 'integer', 'minimum': 1},
                'procedure_sha256': {'type': 'string', 'pattern': '^[a-f0-9]{64}$'},
                'expected_impact': {'type': 'object', 'properties': {k: {'type': 'boolean'} for k in FLAGS},
                    'required': FLAGS, 'additionalProperties': False},
                'production_gate': {'const': 'independent_release_controls'}},
            'required': ['key', 'module', 'procedure_evidence_id', 'procedure_sha256', 'expected_impact', 'production_gate'],
            'additionalProperties': False})
        if not content['module'].strip() or not Evidence.objects.filter(case=case,
                pk=content['procedure_evidence_id'], kind='change_procedure', sha256=content['procedure_sha256']).exists():
            raise ValidationError('Catalogue requires an exact case-owned procedure evidence version and hash')
    else:
        if target.schema_ref == 'schema:psl/change-satisfied-gates/v2':
            from .emergency_validators import EMERGENCY_GATES
            from types import SimpleNamespace
            from apps.documents.contracts import validate
            validate({'type':'object','properties':{'standard':{'type':'array'},'emergency':EMERGENCY_GATES},
                'minProperties':1,'additionalProperties':False},target.content)
            if 'standard' in target.content:
                validate_reference(component,SimpleNamespace(schema_ref='schema:psl/standard-satisfied-gates/v1',content={'standard':target.content['standard']}),case)
            return
        typed(target, 'schema:psl/standard-satisfied-gates/v1', {
            'type': 'object', 'properties': {'standard': {'type': 'array', 'minItems': 1, 'maxItems': 100,
                'items': {'type': 'object', 'properties': {
                    'catalogue_key': {'type': 'string', 'pattern': '^[a-zA-Z0-9_-]{1,80}$'},
                    'roles': {'type': 'array', 'minItems': 1, 'uniqueItems': True,
                        'items': {'enum': REUSABLE_ROLES}}},
                    'required': ['catalogue_key', 'roles'], 'additionalProperties': False}}},
            'required': ['standard'], 'additionalProperties': False})
        keys = [r['catalogue_key'] for r in target.content['standard']]
        if len(keys) != len(set(keys)):
            raise ValidationError('Each Standard catalogue key needs exactly one gate mapping')
