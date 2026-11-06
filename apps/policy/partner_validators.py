from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from apps.identity.models import Grant
from adapters.forecast import obj,rows,KEY
from .document_validators import typed,ROLES
import copy
from types import SimpleNamespace

STAGES='D09.onboarding_stage_catalogue'
DEADLINES='D04.deadline_parameters'
ACTIVITY='D10.audience_projection_rules'
METER='D08.billing_calendar'
ID={'type':'integer','minimum':1}
ROLES_LIST={'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':ROLES}}
KEYS={'type':'array','maxItems':100,'uniqueItems':True,'items':KEY}
STAGE=obj({'key':KEY,'initial':{'type':'boolean'},'terminal':{'type':'boolean'},'next_stages':KEYS,'roles':ROLES_LIST,'required_evidence_kinds':KEYS,'clock':{'const':'elapsed_seconds'},'pause':{'enum':['not_permitted','freeze_elapsed']},'reentry':{'const':'reset_on_explicit_entry'},'followup_after_seconds':{'anyOf':[{'type':'integer','minimum':1,'maximum':31536000},{'type':'null'}]}})
DEADLINE=obj({'implementation':{'const':'explicit_agreement_dates_v1'},'timezone':{'type':'string'},'expiry_boundary':{'enum':['start_of_day','end_of_day']},'review_clock':{'const':'calendar_days'},'agreement_roles':ROLES_LIST,'renewal_roles':ROLES_LIST,'followup_roles':ROLES_LIST,'notice_lead_days':{'type':'integer','minimum':0,'maximum':3650},'expiry_lead_days':{'type':'integer','minimum':0,'maximum':3650}})
PROJECTION=obj({'implementation':{'const':'partner_activity_v1'},'timezone':{'type':'string'},'sources':KEYS,'active_kinds':KEYS,'excluded_kinds':KEYS,'reviewer_roles':ROLES_LIST,'sender_roles':ROLES_LIST,'allow_preparer_review':{'type':'boolean'},'allow_partial':{'type':'boolean'},'recipient_id':ID,'columns':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['product','event_count','active_users','coverage']}},'lease_seconds':{'type':'integer','minimum':15,'maximum':300},'max_attempts':{'type':'integer','minimum':1,'maximum':10}})
METER_SCHEMA=obj({'implementation':{'const':'explicit_event_quantity_v1'},'coverage_id':ID,'partner':KEY,'product':KEY,'event_kinds':KEYS,'unit':KEY,'quantity_method':{'const':'sum_supplied_quantities'},'allow_partial':{'type':'boolean'}})
SCHEMAS={STAGES:'schema:psl/onboarding-stage/v1',DEADLINES:'schema:psl/partner-deadlines/v1',ACTIVITY:'schema:psl/partner-activity/v1',METER:'schema:psl/partner-meter/v1'}

# Preserve optional existing namespaces in the same independently versioned component.
from .clock_validators import DEADLINE_SCHEMA
DEADLINE['properties'].update(copy.deepcopy(DEADLINE_SCHEMA['properties']))
from .finance_validators import SCHEMAS as FINANCE_SCHEMAS
from .forecast_validators import PROJECTION as FORECAST_PROJECTION
PROJECTION['properties'].update(copy.deepcopy(FINANCE_SCHEMAS[ACTIVITY][1]['properties']))
audience=PROJECTION['properties']['audiences']['items']
audience['properties'].update(columns={'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['actual','budget','prior','variance','prior_variance','ratio']}},charts={'type':'boolean'})
PROJECTION['properties'].update(copy.deepcopy(FORECAST_PROJECTION['properties']))

def handles(component,target):return component==STAGES or component in SCHEMAS and target.schema_ref==SCHEMAS[component]

def validate_reference(component,target,case,runtime=False):
    v=typed(target,SCHEMAS[component],{STAGES:STAGE,DEADLINES:DEADLINE,ACTIVITY:PROJECTION,METER:METER_SCHEMA}[component])
    if component==STAGES:
        if v['key'] in v['next_stages'] or v['terminal'] and v['next_stages']:raise ValidationError('Terminal stages have no next stage; reentry must use an explicit different stage')
        if not v['required_evidence_kinds']:raise ValidationError('Stage completion requires explicit evidence kinds')
    elif component==DEADLINES:
        try:ZoneInfo(v['timezone'])
        except (ValueError,ZoneInfoNotFoundError):raise ValidationError('Configure actual agreement IANA timezone')
        legacy={k:v[k] for k in DEADLINE_SCHEMA['properties'] if k in v}
        if legacy:
            from .clock_validators import validate_reference as validate_clock
            validate_clock(component,SimpleNamespace(schema_ref='schema:psl/deadline-parameters/v1',content=legacy),case)
    elif component==ACTIVITY:
        try:ZoneInfo(v['timezone'])
        except (ValueError,ZoneInfoNotFoundError):raise ValidationError('Configure actual activity IANA timezone')
        if not v['sources'] or not v['active_kinds'] or set(v['active_kinds']) & set(v['excluded_kinds']):raise ValidationError('Activity sources and disjoint active/excluded kinds are required')
        if not {'product','coverage'}<=set(v['columns']):raise ValidationError('Report must disclose product and coverage')
        legacy={k:v[k] for k in ['forecast','disclosure','audiences'] if k in v}
        if 'forecast' in legacy:
            from .forecast_validators import validate_projection
            validate_projection(SimpleNamespace(schema_ref='schema:psl/forecast-projection/v1',content=legacy))
        elif legacy:
            from .finance_validators import validate_reference as validate_finance
            version='v2' if any('columns' in a or 'charts' in a for a in legacy.get('audiences',[])) else 'v1'
            validate_finance(component,SimpleNamespace(schema_ref='schema:psl/finance-projection/'+version,content=legacy),case,runtime)
        if not runtime:
            from .services import decision_authority
            person=get_user_model().objects.filter(pk=v['recipient_id'],is_active=True).first()
            if not person or not Grant.objects.filter(case=case,user=person,action='partner.finance.receive',active=True).exists():raise ValidationError('Finance recipient needs current case receive grant')
            decision_authority(person,case,'Finance')
    elif component==METER:
        from apps.finance.models import BillingCoverage
        if not BillingCoverage.objects.filter(case=case,pk=v['coverage_id']).exists() or not v['event_kinds']:raise ValidationError('Meter needs exact case Finance coverage and explicit kinds')

def validate_collection(component,values):
    if component!=STAGES:return
    keys=[v['key'] for v in values]
    if len(set(keys))!=len(keys) or sum(v['initial'] for v in values)!=1:raise ValidationError('Onboarding stages need unique keys and one explicit initial stage')
    if any(set(v['next_stages'])-set(keys) for v in values):raise ValidationError('Unknown next onboarding stage')
