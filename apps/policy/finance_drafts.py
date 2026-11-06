from uuid import uuid4
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.services import lock_case
from apps.pmo.clocks import aware
from .finance_validators import SCHEMAS
from .billing_validators import SCHEMAS as BILLING_SCHEMAS,ARRAYS as BILLING_ARRAYS,STRINGS as BILLING_STRINGS
from .settlement_validators import SCHEMAS as SETTLEMENT_SCHEMAS,ARRAYS as SETTLEMENT_ARRAYS,STRINGS as SETTLEMENT_STRINGS
SCHEMAS=dict(SCHEMAS,**BILLING_SCHEMAS,**SETTLEMENT_SCHEMAS)
from .registry import components
from .services import register_reference,save_draft

ARRAYS={'D06.account_bu_maps','D06.rule_oracle_refs','D07.authorized_input_refs','D07.allocation_pool_rules','D10.report_category_effective_dates'}
STRINGS={'D07.join_overlap_rule_id','D07.effective_membership_ref','D07.rounding_residual_rule_id','D06.source_schema_ref','D10.restatement_rule_id'}
EXTRA={'D10.restatement_rule_id':'schema:psl/finance-restatement/v1','D05.decision_action_matrix':'schema:psl/decision-actions/v4','D06.unit_sign_currency_period':'schema:psl/source-conventions/v2','D06.source_schema_ref':'schema:psl/controlled-csv/v1'}

ARRAYS |= BILLING_ARRAYS | SETTLEMENT_ARRAYS
STRINGS |= BILLING_STRINGS | SETTLEMENT_STRINGS | {'D10.forecast_inclusion_rule_id'}
EXTRA['D10.forecast_inclusion_rule_id']='schema:psl/forecast-method/v1'

@transaction.atomic
def draft_finance_policy(actor,case_id,component,content,evidence_id,effective_from):
    case=lock_case(actor,case_id,'policy.configure')
    if component not in SCHEMAS and component not in EXTRA:raise ValidationError('Select a supported Finance configuration interface')
    schema=EXTRA.get(component) or 'schema:psl/'+SCHEMAS[component][0]+'/v1'
    if component=='D05.decision_action_matrix' and isinstance(content,dict) and any(x.get('purpose')=='invoice' for x in content.get('finance',[])):schema='schema:psl/decision-actions/v5'
    if component=='D05.decision_action_matrix' and isinstance(content,dict) and any(x.get('purpose') in ['invoice_correction','cash_successor'] for x in content.get('finance',[])):schema='schema:psl/decision-actions/v6'
    from .correction_validators import schema_for
    if component=='D05.decision_action_matrix' and isinstance(content,dict) and any(x.get('purpose') in ['forecast','forecast_rollover','forecast_priority'] for x in content.get('finance',[])):schema='schema:psl/decision-actions/v7'
    if component=='D10.audience_projection_rules' and isinstance(content,dict) and 'forecast' in content:schema='schema:psl/forecast-projection/v1'
    schema=schema_for(component,content,schema)
    if component=='D06.unit_sign_currency_period' and isinstance(content,dict) and 'performance' in content:schema='schema:psl/source-conventions/v3'
    if component=='D10.audience_projection_rules' and isinstance(content,dict) and 'forecast' not in content and any('columns' in x for x in content.get('audiences',[])):schema='schema:psl/finance-projection/v2'
    if component in ARRAYS:
        if not isinstance(content,list) or not 1<=len(content)<=100:raise ValidationError('Supply 1–100 explicit configuration records')
        value=[register_reference(actor,case.pk,'finance:'+str(uuid4()),schema_for(component,v,schema),v,evidence_id).ref for v in content]
    else:
        r=register_reference(actor,case.pk,'finance:'+str(uuid4()),schema,content,evidence_id)
        value=r.ref if component in STRINGS else {'artifact_ref':r.ref,'artifact_version':r.version,'sha256':r.sha256,'schema_ref':r.schema_ref}
    return save_draft(actor,case.pk,{'slot_id':component.split('.')[0],'component_id':component,'component_schema_ref':components()[component]['schema_ref'],
        'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'project' if case.kind=='project' else 'service','ref':str(case.pk)},
        'effective_from':aware(effective_from).isoformat(),'effective_until':None,'evidence_refs':[f'evidence:{evidence_id}'],'human_decision_ref':f'evidence:{evidence_id}',
        'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1',
        'fixture_scope':'synthetic_test' if case.synthetic else 'operational','value':value})
