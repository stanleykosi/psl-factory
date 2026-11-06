from django.core.exceptions import ValidationError
from .document_validators import typed
from adapters.forecast import obj

COMPONENT='OPS.factory_execution'
SCHEMA='schema:psl/factory-execution/v1'
ID={'anyOf':[{'type':'integer','minimum':1},{'type':'null'}]}
VALUE=obj({
    'definition':{'const':'pmo-finance/v1'},
    'max_steps':{'type':'integer','minimum':1,'maximum':100},
    'max_tokens':{'type':'integer','minimum':1,'maximum':1000000},
    'tokens_per_call':{'type':'integer','minimum':1,'maximum':32000},
    'max_children':{'type':'integer','minimum':1,'maximum':100},
    'max_depth':{'type':'integer','minimum':1,'maximum':5},
    'lease_seconds':{'type':'integer','minimum':1,'maximum':300},
    'max_age_seconds':{'type':'integer','minimum':1,'maximum':31536000},
    'required_evidence_kinds':{'type':'array','minItems':1,'maxItems':16,'uniqueItems':True,'items':{'type':'string','pattern':'^[a-z][a-z0-9_]{1,48}$'}},
    'information_resolver_id':ID,'executor_id':ID,
    'review_role':{'const':'Finance'},'provider':{'const':'synthetic_factory_v1'},
    'enabled':{'type':'boolean'}})

PLANNING_COMPONENT='OPS.factory_planning_execution'
PLANNING_SCHEMA='schema:psl/factory-planning-execution/v1'
from copy import deepcopy
PLANNING_VALUE=deepcopy(VALUE)
PLANNING_VALUE['properties']['definition']={'const':'planning/v1'}
PLANNING_VALUE['properties']['review_role']={'type':'null'}
PLANNING_VALUE['properties']['executor_id']={'type':'null'}
PLANNING_VALUE['properties']['information_resolver_id']={'type':'null'}
COMMERCIAL_COMPONENT='OPS.factory_commercial_execution'
COMMERCIAL_SCHEMA='schema:psl/factory-commercial-execution/v1'
COMMERCIAL_VALUE=deepcopy(VALUE)
COMMERCIAL_VALUE['properties']['definition']={'const':'commercial/v1'}
COMMERCIAL_VALUE['properties']['review_role']={'type':'null'}
COMMERCIAL_VALUE['properties']['information_resolver_id']={'type':'null'}
DELIVERY_COMPONENT='OPS.factory_delivery_execution'
DELIVERY_SCHEMA='schema:psl/factory-delivery-execution/v1'
DELIVERY_VALUE=deepcopy(PLANNING_VALUE)
DELIVERY_VALUE['properties']['definition']={'const':'delivery-release/v1'}
HYPERCARE_COMPONENT='OPS.factory_hypercare_execution'
HYPERCARE_SCHEMA='schema:psl/factory-hypercare-execution/v1'
HYPERCARE_VALUE=deepcopy(PLANNING_VALUE)
HYPERCARE_VALUE['properties']['definition']={'const':'delivery-hypercare/v1'}
ARCHIVE_COMPONENT='OPS.factory_archive_execution'
ARCHIVE_SCHEMA='schema:psl/factory-archive-execution/v1'
ARCHIVE_VALUE=deepcopy(COMMERCIAL_VALUE)
ARCHIVE_VALUE['properties']['definition']={'const':'delivery-archive/v1'}
HANDOVER_COMPONENT='OPS.factory_handover_execution'
HANDOVER_SCHEMA='schema:psl/factory-handover-execution/v1'
HANDOVER_VALUE=deepcopy(COMMERCIAL_VALUE)
HANDOVER_VALUE['properties']['definition']={'const':'delivery-handover/v1'}
CLOSURE_COMPONENT='OPS.factory_closure_execution'
CLOSURE_SCHEMA='schema:psl/factory-closure-execution/v1'
CLOSURE_VALUE=deepcopy(COMMERCIAL_VALUE)
CLOSURE_VALUE['properties']['definition']={'const':'delivery-closure/v1'}
GO_LIVE_COMPONENT='OPS.factory_go_live_execution'
GO_LIVE_SCHEMA='schema:psl/factory-go-live-execution/v1'
GO_LIVE_VALUE=deepcopy(COMMERCIAL_VALUE)
GO_LIVE_VALUE['properties'].update(definition={'const':'delivery-go-live/v1'},preparer_id=deepcopy(ID))
GO_LIVE_VALUE['required'].append('preparer_id')

CHANGE_COMPONENT='OPS.factory_change_execution'
CHANGE_SCHEMA='schema:psl/factory-change-execution/v1'
CHANGE_VALUE=deepcopy(GO_LIVE_VALUE)
CHANGE_VALUE['properties']['definition']={'const':'pmo-change/v1'}

PPE_COMPONENT='OPS.factory_ppe_execution'
PPE_SCHEMA='schema:psl/factory-ppe-execution/v1'
PPE_VALUE=deepcopy(PLANNING_VALUE)
PPE_VALUE['properties']['definition']={'const':'finance-ppe/v1'}

def validate_reference(component,target,case,runtime=False):
    planning=component==PLANNING_COMPONENT
    commercial=component==COMMERCIAL_COMPONENT
    delivery=component==DELIVERY_COMPONENT
    hypercare=component==HYPERCARE_COMPONENT
    archive=component==ARCHIVE_COMPONENT
    handover=component==HANDOVER_COMPONENT
    closure=component==CLOSURE_COMPONENT
    change=component==CHANGE_COMPONENT
    go_live=component==GO_LIVE_COMPONENT or change
    schema,shape={COMPONENT:(SCHEMA,VALUE),PLANNING_COMPONENT:(PLANNING_SCHEMA,PLANNING_VALUE),
        COMMERCIAL_COMPONENT:(COMMERCIAL_SCHEMA,COMMERCIAL_VALUE),DELIVERY_COMPONENT:(DELIVERY_SCHEMA,DELIVERY_VALUE),
        HYPERCARE_COMPONENT:(HYPERCARE_SCHEMA,HYPERCARE_VALUE),ARCHIVE_COMPONENT:(ARCHIVE_SCHEMA,ARCHIVE_VALUE),
        HANDOVER_COMPONENT:(HANDOVER_SCHEMA,HANDOVER_VALUE),CLOSURE_COMPONENT:(CLOSURE_SCHEMA,CLOSURE_VALUE),
        GO_LIVE_COMPONENT:(GO_LIVE_SCHEMA,GO_LIVE_VALUE),CHANGE_COMPONENT:(CHANGE_SCHEMA,CHANGE_VALUE),PPE_COMPONENT:(PPE_SCHEMA,PPE_VALUE)}.get(component,(SCHEMA,VALUE))
    from .factory_provider_profiles import shape_for,scope
    value=typed(target,*shape_for(target,schema,shape));scope(case,value)
    if value['tokens_per_call']>value['max_tokens']:raise ValidationError('Call reservation exceeds aggregate token budget')
    from types import SimpleNamespace
    from apps.core.evidence_access import restricted
    if any(restricted(SimpleNamespace(kind=k)) for k in value['required_evidence_kinds']):raise ValidationError('Restricted evidence requires its native domain provider interface')
    from django.contrib.auth import get_user_model
    from apps.identity.models import Grant
    for name in ['information_resolver_id','executor_id']+(['preparer_id'] if go_live else []):
        if not runtime and value[name] is not None:
            action='factory.information' if name=='information_resolver_id' else 'factory.execute'
            if not get_user_model().objects.filter(pk=value[name],is_active=True).exists() or not Grant.objects.filter(case=case,user_id=value[name],action=action,active=True).exists():raise ValidationError('Configured principal requires an actual current same-case grant')
            if planning and not Grant.objects.filter(case=case,user_id=value[name],action='planning.read',active=True).exists():raise ValidationError('Planning principals require current same-case planning access')
            if commercial and name=='executor_id' and not Grant.objects.filter(case=case,user_id=value[name],action='document.publish',active=True).exists():raise ValidationError('Commercial publisher requires current same-case document publication access')
            if archive and name=='executor_id':
                for required in ['case.read','delivery.read','delivery.manage']:
                    if not Grant.objects.filter(case=case,user_id=value[name],action=required,active=True).exists():raise ValidationError('Archive operator requires current same-case delivery and archive permissions')
            if handover and name=='executor_id':
                for required in ['case.read','delivery.read','document.publish']:
                    if not Grant.objects.filter(case=case,user_id=value[name],action=required,active=True).exists():raise ValidationError('Handover publisher requires current same-case document publication and delivery access')
            if closure and name=='executor_id':
                for required in ['case.read','delivery.read','delivery.manage']:
                    if not Grant.objects.filter(case=case,user_id=value[name],action=required,active=True).exists():raise ValidationError('Closure finaliser requires current same-case delivery permissions; PM business authority is rechecked at runtime')
            if go_live:
                required_actions=['case.read','change.read' if change else 'delivery.read']+(['document.publish'] if name=='executor_id' else
                    ['change.manage' if change else 'delivery.manage','document.draft','document.request_review'] if name=='preparer_id' else [])
                for required in required_actions:
                    if not Grant.objects.filter(case=case,user_id=value[name],action=required,active=True).exists():raise ValidationError('Go-live principal requires current same-project permissions; selection does not appoint a PM')
    return value
