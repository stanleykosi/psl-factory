from uuid import uuid4
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.services import lock_case
from apps.pmo.clocks import aware
from .registry import components
from .services import register_reference,save_draft
from .validation_validators import SCHEMAS,SOP,ACCEPTANCE,PRIVATE_SCHEMA,PROTECTION_ACCEPTANCE,PROTECTION_FILE_SCHEMA
from .validation_validators import NATIVE_SCHEMA

@transaction.atomic
def draft_validation_policy(actor,case_id,component,content,evidence_id,effective_from):
    case=lock_case(actor,case_id,'policy.configure')
    if component not in SCHEMAS:raise ValidationError('Choose a validation interface')
    schema=PRIVATE_SCHEMA if component==ACCEPTANCE and isinstance(content,dict) and 'private_readiness' in content else SCHEMAS[component][0]
    if component==ACCEPTANCE and isinstance(content,dict) and 'native_execution' in content:schema=NATIVE_SCHEMA
    if component==PROTECTION_ACCEPTANCE and isinstance(content,dict):
        section=content.get('private_protection');rows=section.get('inventory') if isinstance(section,dict) else None
        if isinstance(rows,list) and any(isinstance(row,dict) and 'native_kind' in row for row in rows):schema=PROTECTION_FILE_SCHEMA
    r=register_reference(actor,case.pk,'validation:'+str(uuid4()),schema,content,evidence_id)
    value=r.ref if component==SOP else {'artifact_ref':r.ref,'artifact_version':r.version,'sha256':r.sha256,'schema_ref':r.schema_ref}
    return save_draft(actor,case.pk,{'slot_id':components()[component]['parent_decision_id'],'component_id':component,'component_schema_ref':components()[component]['schema_ref'],'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'project' if case.kind=='project' else 'service','ref':str(case.pk)},'effective_from':aware(effective_from).isoformat(),'effective_until':None,'evidence_refs':['evidence:'+str(evidence_id)],'human_decision_ref':'evidence:'+str(evidence_id),'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test' if case.synthetic else 'operational','value':value})
