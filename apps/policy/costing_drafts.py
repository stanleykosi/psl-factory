from uuid import uuid4
from django.db import transaction
from apps.core.services import lock_case
from apps.pmo.clocks import aware
from .registry import components
from .services import register_reference,save_draft
from .costing_validators import COMPONENT,SCHEMAS

@transaction.atomic
def draft_costing_policy(actor,case_id,content,evidence_id,effective_from):
    c=lock_case(actor,case_id,'policy.configure');r=register_reference(actor,c.pk,'p14:'+str(uuid4()),SCHEMAS[COMPONENT][0],content,evidence_id)
    return save_draft(actor,c.pk,{'slot_id':'P14-Q01','component_id':COMPONENT,'component_schema_ref':components()[COMPONENT]['schema_ref'],'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'project' if c.kind=='project' else 'service','ref':str(c.pk)},'effective_from':aware(effective_from).isoformat(),'effective_until':None,'evidence_refs':['evidence:'+str(evidence_id)],'human_decision_ref':'evidence:'+str(evidence_id),'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test' if c.synthetic else 'operational','value':{'artifact_ref':r.ref,'artifact_version':r.version,'sha256':r.sha256,'schema_ref':r.schema_ref}})
