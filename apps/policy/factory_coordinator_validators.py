"""Explicit coordinator mode and metadata-egress contract, without owner defaults."""
from django.core.exceptions import ValidationError
from adapters.forecast import obj
from .document_validators import typed
from .factory_validators import ID

COMPONENT='OPS.factory_coordinator'
SCHEMA='schema:psl/factory-coordinator/v1'
from adapters.factory_planner_contracts import DATA_SCOPE as SCOPE,PROTOCOL
VALUE=obj({'mode':{'enum':[None,'internal_permitted_step_v1','authenticated_planner_v1']},
    'contract_id':ID,'planner_id':ID,'data_scope':{'const':SCOPE},
    'max_output_chars':{'type':'integer','minimum':100,'maximum':2048}})

def validate_reference(component,target,case,runtime=False):
    value=typed(target,SCHEMA,VALUE)
    from apps.identity.models import Grant
    from apps.workflows.readiness_models import IntegrationContract
    for key in ['contract_id','planner_id']:
        if value[key] is not None and type(value[key]) is not int:raise ValidationError('Exact coordinator identities required')
    if value['mode']=='internal_permitted_step_v1' and value['contract_id'] is not None:
        raise ValidationError('Internal coordination must not bind an external provider')
    if value['contract_id'] is not None:
        contract=IntegrationContract.objects.filter(pk=value['contract_id'],case=case,payload__kind='provider',payload__implementation='authenticated_json_v1').first()
        if not contract or contract.payload['contract_version'] not in [None,PROTOCOL]:raise ValidationError('Select this workspace reviewed factory-planner provider protocol')
    if not runtime and value['planner_id'] is not None:
        for action in ['case.read','factory.read','factory.execute']:
            if not Grant.objects.filter(case=case,user_id=value['planner_id'],user__is_active=True,action=action,active=True).exists():raise ValidationError('Coordinator nominee requires current same-workspace permissions; selection grants no authority')
    return value
