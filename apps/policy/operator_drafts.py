from uuid import uuid4
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.services import lock_case
from apps.pmo.clocks import aware
from .registry import components
from .services import register_reference,save_draft
from .operator_validators import SCHEMAS,PROTECTION,PRIVATE_SCHEMA

@transaction.atomic
def draft_operator_policy(a,case_id,component,content,evidence_id,effective_from):
    c=lock_case(a,case_id,'policy.configure')
    if component not in SCHEMAS:raise ValidationError('Choose a supplemental operator interface')
    schema=PRIVATE_SCHEMA if component==PROTECTION and isinstance(content,dict) and 'private_readiness_packet_ids' in content else SCHEMAS[component][0]
    from .factory_routing_validators import COMPONENT as RESPONSIBILITY,METHOD_V2,SCHEMA_V2,METHOD_V3,SCHEMA_V3
    if component==RESPONSIBILITY and isinstance(content,dict) and content.get('method')==METHOD_V2:schema=SCHEMA_V2
    if component==RESPONSIBILITY and isinstance(content,dict) and content.get('method')==METHOD_V3:schema=SCHEMA_V3
    if isinstance(content,dict) and 'provider' in SCHEMAS[component][1].get('properties',{}) and content.get('provider')!='synthetic_factory_v1':schema=schema.rsplit('/',1)[0]+'/v2'
    r=register_reference(a,c.pk,'ops:'+str(uuid4()),schema,content,evidence_id)
    return save_draft(a,c.pk,{'slot_id':components()[component]['parent_decision_id'],'component_id':component,'component_schema_ref':components()[component]['schema_ref'],'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'project' if c.kind=='project' else 'service','ref':str(c.pk)},'effective_from':aware(effective_from).isoformat(),'effective_until':None,'evidence_refs':['evidence:'+str(evidence_id)],'human_decision_ref':'evidence:'+str(evidence_id),'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test' if c.synthetic else 'operational','value':{'artifact_ref':r.ref,'artifact_version':r.version,'schema_ref':r.schema_ref,'sha256':r.sha256}})
