from uuid import uuid4
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.services import lock_case
from apps.pmo.clocks import aware
from .registry import components
from .services import register_reference,save_draft
from .payment_validators import SCHEMAS,PEOPLE,DELEGATION,VALIDITY

@transaction.atomic
def draft_payment_policy(actor,case_id,component,content,evidence_id,effective_from):
    case=lock_case(actor,case_id,'policy.configure')
    if component not in SCHEMAS:raise ValidationError('Choose a typed D13 component')
    values=content if component==PEOPLE else [content]
    if not isinstance(values,list) or not values:raise ValidationError('Provide explicit human principal records')
    refs=[register_reference(actor,case.pk,'payment:'+str(uuid4()),SCHEMAS[component][0],v,evidence_id) for v in values]
    r=refs[0]
    value=[x.ref for x in refs] if component in [PEOPLE,DELEGATION] else {'artifact_ref':r.ref,'artifact_version':r.version,'sha256':r.sha256,'schema_ref':r.schema_ref} if component==VALIDITY else r.ref
    return save_draft(actor,case.pk,{'slot_id':'D13','component_id':component,'component_schema_ref':components()[component]['schema_ref'],'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'project' if case.kind=='project' else 'service','ref':str(case.pk)},'effective_from':aware(effective_from).isoformat(),'effective_until':None,'evidence_refs':['evidence:'+str(evidence_id)],'human_decision_ref':'evidence:'+str(evidence_id),'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test' if case.synthetic else 'operational','value':value})
