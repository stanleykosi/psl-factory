from uuid import uuid4
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.services import lock_case
from apps.pmo.clocks import aware
from .registry import components
from .services import register_reference,save_draft
from .readiness_validators import SCHEMAS as READINESS_SCHEMAS
from .agent_data_validators import SCHEMAS as DATA_SCHEMAS
SCHEMAS={**READINESS_SCHEMAS,**DATA_SCHEMAS}

@transaction.atomic
def draft_readiness_policy(a,case_id,component,content,evidence_id,effective_from):
    c=lock_case(a,case_id,'policy.configure')
    if component not in SCHEMAS:raise ValidationError('Choose a supplemental integration interface')
    from .readiness_validators import ADAPTER,NATIVE_SCHEMA,PRIVATE_SCHEMA,PRIVATE_COMPONENT,FILE_SCHEMA
    schema=NATIVE_SCHEMA if component==ADAPTER and isinstance(content,dict) and 'native_publication_job_ids' in content else FILE_SCHEMA if component==PRIVATE_COMPONENT and isinstance(content,dict) and 'private_file_job_ids' in content else SCHEMAS[component][0]
    r=register_reference(a,c.pk,'integration:'+str(uuid4()),schema,content,evidence_id)
    return save_draft(a,c.pk,{'slot_id':'INT','component_id':component,'component_schema_ref':components()[component]['schema_ref'],'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'project' if c.kind=='project' else 'service','ref':str(c.pk)},'effective_from':aware(effective_from).isoformat(),'effective_until':None,'evidence_refs':['evidence:'+str(evidence_id)],'human_decision_ref':'evidence:'+str(evidence_id),'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test' if c.synthetic else 'operational','value':{'artifact_ref':r.ref,'artifact_version':r.version,'schema_ref':r.schema_ref,'sha256':r.sha256}})
