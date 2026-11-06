from uuid import uuid4
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.services import lock_case
from apps.pmo.services import subject
from apps.pmo.clocks import aware
from .registry import components
from .services import register_reference, save_draft

SCHEMAS={'D04.working_calendar_ref':'schema:psl/working-calendar/v1','D04.clock_anchor_pause_rules':'schema:psl/action-clock/v1',
    'D04.deadline_parameters':'schema:psl/deadline-parameters/v1'}

@transaction.atomic
def draft_clock_policy(actor,case_id,component,value,evidence_id,effective_from):
    case=lock_case(actor,case_id,'policy.configure')
    subject(case,evidence_id,'policy_decision')
    if component not in SCHEMAS and component!='D04.iana_timezone':raise ValidationError('Unsupported clock component')
    if component in SCHEMAS:
        record=register_reference(actor,case_id,'clock:'+str(uuid4()),SCHEMAS[component],value,evidence_id)
        value=record.ref if component=='D04.working_calendar_ref' else {'artifact_ref':record.ref,'artifact_version':record.version,'sha256':record.sha256,'schema_ref':record.schema_ref}
    return save_draft(actor,case_id,{'slot_id':'D04','component_id':component,'component_schema_ref':components()[component]['schema_ref'],
        'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'project' if case.kind=='project' else 'service','ref':str(case.pk)},
        'effective_from':aware(effective_from).isoformat(),'effective_until':None,'evidence_refs':[f'evidence:{evidence_id}'],
        'human_decision_ref':f'evidence:{evidence_id}','implementation_id':'psl.reference-validation','implementation_version':'1',
        'reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test' if case.synthetic else 'operational','value':value})
