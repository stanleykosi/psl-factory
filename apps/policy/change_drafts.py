from uuid import uuid4
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.services import lock_case
from apps.pmo.clocks import aware
from apps.pmo.services import subject
from .registry import components
from .services import register_reference, save_draft

SCHEMAS = {'D11.change_go_live_client_applicability': 'schema:psl/change-go-live-client-applicability/v1',
    'D11.client_signature_contract': 'schema:psl/client-signature-contract/v1',
    'D01.change_type_catalogue': 'schema:psl/standard-catalogue-entry/v1',
    'D01.satisfied_gate_map': 'schema:psl/standard-satisfied-gates/v1',
    'D01.emergency_glpi_relationship':'schema:psl/emergency-glpi/v1',
    'D05.revision_invalidation_rules':'schema:psl/commercial-revision/v2',
    'D11.hypercare_criteria_ref':'schema:psl/hypercare-criteria/v1',
    'D11.template_storage_retention_rules':'schema:psl/document-storage/v2',
    'D05.decision_action_matrix':'schema:psl/decision-actions/v2',
    'D11.adapter_configuration_refs':'schema:psl/rfp-submission-route/v1'}


@transaction.atomic
def draft_standard_policy(actor, case_id, component, value, evidence_id, effective_from):
    case = lock_case(actor, case_id, 'policy.configure')
    subject(case, evidence_id, 'policy_decision')
    if component not in SCHEMAS:
        raise ValidationError('Choose a supported Standard change component')
    if component in ['D01.change_type_catalogue','D11.adapter_configuration_refs']:
        if not isinstance(value, list) or not 1 <= len(value) <= 100:
            raise ValidationError('Catalogue draft needs 1–100 explicit entry objects')
        records = [register_reference(actor, case_id, 'standard:'+str(uuid4()), SCHEMAS[component], item, evidence_id) for item in value]
        value = [r.ref for r in records]
    else:
        schema=SCHEMAS[component]
        if component=='D11.template_storage_retention_rules' and isinstance(value,dict) and 'template_owners' in value:
            schema='schema:psl/document-storage/v3'
        if component=='D05.decision_action_matrix' and isinstance(value,dict) and any(
            isinstance(rule,dict) and 'reaffirm_go_live' in rule.get('actions',[]) for rule in value.get('rules',[])):
            schema='schema:psl/decision-actions/v8'
        if component=='D01.emergency_glpi_relationship' and isinstance(value,dict) and 'role_eligibility' in value:
            schema='schema:psl/emergency-glpi/v2'
        if component=='D01.satisfied_gate_map' and isinstance(value,dict) and 'emergency' in value:
            schema='schema:psl/change-satisfied-gates/v2'
        r = register_reference(actor, case_id, 'change:'+str(uuid4()), schema, value, evidence_id)
        value = r.ref if component in ['D01.emergency_glpi_relationship','D11.hypercare_criteria_ref'] else {'artifact_ref': r.ref, 'artifact_version': r.version, 'sha256': r.sha256, 'schema_ref': r.schema_ref}
    return save_draft(actor, case_id, {'slot_id': component.split('.')[0], 'component_id': component,
        'component_schema_ref': components()[component]['schema_ref'], 'schema_version': '1',
        'policy_revision': 1, 'lifecycle': 'draft',
        'subject_scope': {'kind': 'project' if case.kind == 'project' else 'service', 'ref': str(case.pk)},
        'effective_from': aware(effective_from).isoformat(), 'effective_until': None,
        'evidence_refs': [f'evidence:{evidence_id}'], 'human_decision_ref': f'evidence:{evidence_id}',
        'implementation_id': 'psl.reference-validation', 'implementation_version': '1',
        'reviewed_implementation_ref': 'code:apps/policy/services.py#reference-validation-v1',
        'fixture_scope': 'synthetic_test' if case.synthetic else 'operational', 'value': value})
