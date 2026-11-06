"""D05 nomination/eligibility interfaces; explicit owner values, never action grants."""
import json
from datetime import datetime
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from jsonschema import Draft202012Validator,FormatChecker
from apps.core.services import lock_case
from .document_validators import ROLES

COMPONENT='D05.role_principal_assignments'
V1='schema:psl/role-assignment/v1'
V2='schema:psl/role-assignment/v2'
ELIGIBILITY={'type':'object','properties':{'roles':{'type':'array','minItems':2,'maxItems':len(ROLES),'uniqueItems':True,'items':{'enum':ROLES}},
    'valid_from':{'type':'string','format':'date-time'},'valid_until':{'type':'string','format':'date-time'}},
    'required':['roles','valid_from','valid_until'],'additionalProperties':False}
BASE={'role':{'enum':ROLES},'user_id':{'type':'integer','minimum':1}}
SCHEMAS={V1:{'type':'object','properties':BASE,'required':list(BASE),'additionalProperties':False},
    V2:{'type':'object','properties':dict(BASE,eligibility=ELIGIBILITY),'required':list(BASE)+['eligibility'],'additionalProperties':False}}


def instant(value):
    try:
        result=datetime.fromisoformat(value.replace('Z','+00:00'))
        if timezone.is_naive(result):raise ValueError()
        return result
    except (ValueError,TypeError,AttributeError):raise ValidationError('Explicit timezone-aware eligibility timestamps required') from None


def signature(value):
    e=value['eligibility']
    return (tuple(sorted(e['roles'])),instant(e['valid_from']),instant(e['valid_until']))


def validate_reference(target,case):
    schema=SCHEMAS.get(target.schema_ref)
    if schema is None or list(Draft202012Validator(schema,format_checker=FormatChecker()).iter_errors(target.content)):
        raise ValidationError('Expected a closed typed role assignment v1 or explicit eligibility v2')
    value=target.content
    if not get_user_model().objects.filter(pk=value['user_id'],is_active=True).exists():raise ValidationError('Unknown or inactive nominated human')
    if 'eligibility' in value:
        roles,start,end=signature(value)
        if value['role'] not in roles or start>=end:raise ValidationError('Eligibility must include this role and have a positive explicit window')


def validate_collection(values):
    for user_id in {v['user_id'] for v in values}:
        group=[v for v in values if v['user_id']==user_id]
        explicit=[v for v in group if 'eligibility' in v]
        if explicit:
            expected=signature(explicit[0])
            if len(explicit)!=len(group) or any(signature(v)!=expected for v in explicit) or set(expected[0])!={v['role'] for v in group}:
                raise ValidationError('Every assigned role in this exact human bundle needs the same explicit eligibility and window')


def eligibility(case,values,user_id,at=None):
    group=[v for v in values if v['user_id']==user_id];roles=sorted({v['role'] for v in group})
    state='not_assigned';eligible=False
    if roles:
        if len(roles)==1:state='single_role';eligible=True
        elif all('eligibility' in v for v in group):
            start,end=signature(group[0])[1:];eligible=start<=(at or timezone.now())<end
            state='explicit_current' if eligible else 'eligibility_window_not_current'
        elif case.synthetic:state='synthetic_fixture_only';eligible=True
        else:state='owner_eligibility_unconfigured'
    return {'user_id':user_id,'roles':roles,'eligibility':state,'eligible_role_bundle':eligible,
        'action_authority_granted':False,'independence_controls_waived':False}


def assert_assigned(actor,case,values,role):
    if not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():raise PermissionDenied('Current active nominated human required')
    if not any(v['role']==role and v['user_id']==actor.pk for v in values):raise PermissionDenied('Human role is not assigned by current policy')
    result=eligibility(case,values,actor.pk)
    if not result['eligible_role_bundle']:
        if result['eligibility']=='owner_eligibility_unconfigured':raise ValidationError('Operational dual-role eligibility is not configured for this exact bundle')
        raise ValidationError('Explicit role-bundle eligibility window is not current')


def _draft(actor,case_id,assignments,evidence_id,effective_from,component,v1,v2,key,prefix,v3=None):
    from .services import register_reference,save_draft
    from .registry import components
    from apps.core.models import Evidence
    case=lock_case(actor,case_id,'policy.configure')
    if not isinstance(assignments,list) or not 1<=len(assignments)<=100 or any(not isinstance(v,dict) for v in assignments):
        raise ValidationError('Supply one to100 assignment objects within this technical draft budget')
    if len(json.dumps(assignments,allow_nan=False))>32000:raise ValidationError('Role assignment draft budget exceeded')
    if timezone.is_naive(effective_from):raise ValidationError('Timezone-aware configuration effective time required')
    if not Evidence.objects.filter(case=case,pk=evidence_id,kind='policy_decision').exists():raise ValidationError('Exact case owner-decision evidence required')
    refs=[register_reference(actor,case_id,prefix+':'+str(uuid4()),v3 if v3 and 'decision_scope' in v else v2 if key in v else v1,v,evidence_id).ref for v in assignments]
    return save_draft(actor,case_id,{'slot_id':'D05','component_id':component,'component_schema_ref':components()[component]['schema_ref'],
        'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'project' if case.kind=='project' else 'service','ref':str(case.pk)},
        'effective_from':effective_from.isoformat(),'effective_until':None,'evidence_refs':[f'evidence:{evidence_id}'],
        'human_decision_ref':f'evidence:{evidence_id}','implementation_id':'psl.reference-validation','implementation_version':'1',
        'reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test' if case.synthetic else 'operational','value':refs})


@transaction.atomic
def draft(actor,case_id,assignments,evidence_id,effective_from):
    return _draft(actor,case_id,assignments,evidence_id,effective_from,COMPONENT,V1,V2,'eligibility','roles')


@transaction.atomic
def draft_delegations(actor,case_id,delegations,evidence_id,effective_from):
    from .delegation_validators import V1 as D1,V2 as D2,V3 as D3
    return _draft(actor,case_id,delegations,evidence_id,effective_from,'D05.delegation_rules',D1,D2,'delegate_eligibility','delegations',D3)


def invoice_delegation_source(actor,case):
    from .services import resolve,reference_values
    from .impact import configuration,context
    context(actor,case.pk);authorize_header(actor,case,'D05.delegation_rules')
    result=resolve('D05.delegation_rules',case)
    if result.status=='ACTIVE':
        config=configuration(actor,case.pk,result.configuration.pk)
        return config,reference_values(config)
    if result.status in ['CONFLICT','AMBIGUOUS']:raise ValidationError('Resolve conflicting delegation sources before editing invoice delegates')
    return None,[]


@transaction.atomic
def draft_invoice_delegation(actor,case_id,value,evidence_id,effective_from,source_configuration,replacement=None):
    """Preserve other native delegation records; replace only an exact scoped invoice row."""
    from apps.finance.billing import digest
    case=lock_case(actor,case_id,'policy.configure')
    current,records=invoice_delegation_source(actor,case)
    if source_configuration is not None and type(source_configuration) is not int:raise ValidationError('Exact delegation source version required')
    if source_configuration!=(current.pk if current else None):raise ValidationError('STALE_VERSION: delegation source changed; reload before saving')
    updated=list(records)
    if replacement:
        matches=[i for i,r in enumerate(records) if digest(r)==replacement and r.get('decision_scope',{}).get('decision_type')=='finance.invoice.review'
            and r['decision_scope']['case_ref']==str(case.pk)]
        if len(matches)!=1:raise ValidationError('STALE_VERSION: select one unchanged invoice delegation to replace')
        updated[matches[0]]=value
    else:updated.append(value)
    return draft_delegations(actor,case_id,updated,evidence_id,effective_from)


def authorize_header(actor,case,component):
    from .impact import configuration
    from .models import Configuration
    for candidate in Configuration.objects.filter(case=case,component=component).order_by('-revision'):
        if candidate.states.order_by('-pk').first().state in ['active','revoked','superseded']:
            return configuration(actor,case.pk,candidate.pk)
    return None


def report(actor,case_id):
    from .impact import context,configuration
    from .services import resolve,reference_values
    case=context(actor,case_id)
    # Reauthorize the stored origin even when revocation makes resolution unavailable.
    # An empty/unavailable result must not bypass the same source boundary as a current one.
    authorize_header(actor,case,COMPONENT)
    resolved=resolve(COMPONENT,case)
    if resolved.status!='ACTIVE':return {'component':COMPONENT,'status':resolved.status,'assignments':[],'effects_scheduled':False}
    cfg=configuration(actor,case_id,resolved.configuration.pk);values=reference_values(cfg)
    return {'component':COMPONENT,'configuration':cfg.pk,'status':'ACTIVE','assignments':[eligibility(case,values,pk) for pk in sorted({v['user_id'] for v in values})],
        'effects_scheduled':False,'action_authority_granted':False,'independence_controls_waived':False}
