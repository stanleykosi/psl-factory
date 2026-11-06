from uuid import uuid4
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.services import lock_case
from apps.pmo.clocks import aware
from .registry import components
from .services import register_reference,save_draft

@transaction.atomic
def draft_baas_policy(actor,case_id,component,content,evidence_id,effective_from):
    case=lock_case(actor,case_id,'policy.configure')
    schemas={'D09.reconciliation_contract_ref':'schema:psl/baas-reconciliation/v1','D09.queue_state_command_map':'schema:psl/baas-queue-commands/v1'}
    if component not in schemas:raise ValidationError('Select a supported BaaS policy interface')
    r=register_reference(actor,case.pk,'baas:'+str(uuid4()),schemas[component],content,evidence_id)
    value=r.ref if component=='D09.reconciliation_contract_ref' else {'artifact_ref':r.ref,'artifact_version':r.version,'sha256':r.sha256,'schema_ref':r.schema_ref}
    return save_draft(actor,case.pk,{'slot_id':'D09','component_id':component,'component_schema_ref':components()[component]['schema_ref'],'schema_version':'1','policy_revision':1,'lifecycle':'draft',
        'subject_scope':{'kind':'project' if case.kind=='project' else 'service','ref':str(case.pk)},'effective_from':aware(effective_from).isoformat(),'effective_until':None,
        'evidence_refs':['evidence:'+str(evidence_id)],'human_decision_ref':'evidence:'+str(evidence_id),'implementation_id':'psl.reference-validation','implementation_version':'1',
        'reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test' if case.synthetic else 'operational','value':value})
