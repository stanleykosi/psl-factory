"""Explicit delegated role bundles; no inferred qualification or action grants."""
from copy import deepcopy
from decimal import Decimal,InvalidOperation
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from jsonschema import Draft202012Validator,FormatChecker
from .document_validators import ROLES
from .role_assignments import ELIGIBILITY,instant,eligibility

V1='schema:psl/decision-delegation/v1'
V2='schema:psl/decision-delegation/v2'
V3='schema:psl/decision-delegation/v3'
BASE={'role':{'enum':ROLES},'principal_id':{'type':'integer','minimum':1},'delegate_id':{'type':'integer','minimum':1},
    'valid_from':{'type':'string'},'valid_until':{'type':'string'}}
DELEGATE_ELIGIBILITY=deepcopy(ELIGIBILITY);DELEGATE_ELIGIBILITY['properties']['roles']['minItems']=1
SCHEMAS={V1:{'type':'object','properties':BASE,'required':list(BASE),'additionalProperties':False},
    V2:{'type':'object','properties':dict(BASE,delegate_eligibility=DELEGATE_ELIGIBILITY),'required':list(BASE)+['delegate_eligibility'],'additionalProperties':False}}
DECISION_SCOPE={'type':'object','properties':{'decision_type':{'const':'finance.invoice.review'},
    'case_ref':{'type':'string','format':'uuid'},
    'actions':{'type':['array','null'],'minItems':1,'maxItems':3,'uniqueItems':True,'items':{'enum':['approve','return','reject']}},
    'currency':{'type':['string','null'],'pattern':'^[A-Z]{3}$'},
    'maximum_amount':{'type':['string','null'],'maxLength':40,'pattern':r'^(0|[1-9][0-9]*)(\.[0-9]+)?$'}},
    'required':['decision_type','case_ref','actions','currency','maximum_amount'],'additionalProperties':False}
SCHEMAS[V3]=deepcopy(SCHEMAS[V2]);SCHEMAS[V3]['properties']['decision_scope']=DECISION_SCOPE
SCHEMAS[V3]['required'].append('decision_scope')


def validate_reference(target,case):
    schema=SCHEMAS.get(target.schema_ref)
    if schema is None or list(Draft202012Validator(schema,format_checker=FormatChecker()).iter_errors(target.content)):
        raise ValidationError('Expected a closed typed delegation v1, eligible-role delegation v2 or scoped invoice delegation v3')
    value=target.content;start,end=instant(value['valid_from']),instant(value['valid_until'])
    if start>=end or value['principal_id']==value['delegate_id']:raise ValidationError('Delegation needs distinct active people and a finite aware validity window')
    if get_user_model().objects.filter(pk__in=[value['principal_id'],value['delegate_id']],is_active=True).count()!=2:
        raise ValidationError('Delegation principals must be active')
    if target.schema_ref in [V2,V3]:
        if any(type(value[k]) is not int for k in ['principal_id','delegate_id']):raise ValidationError('Exact integer delegation principal identities required')
        e=value['delegate_eligibility'];left,right=instant(e['valid_from']),instant(e['valid_until'])
        if value['role'] not in e['roles'] or left>=right or max(left,start)>=min(right,end):
            raise ValidationError('Delegate eligibility must include the delegated role and overlap its authority window')
    if target.schema_ref==V3:
        scope=value['decision_scope']
        if scope['case_ref']!=str(case.pk):raise ValidationError('Invoice delegation must name this exact project or service scope')
        if scope['maximum_amount'] is not None and Decimal(scope['maximum_amount'])<=0:
            raise ValidationError('Delegated invoice limit must be positive or explicitly unknown')


def invoice_scope_status(value,context):
    """Unknown limits confer no authority; exact currency only, with no inferred FX."""
    scope=value.get('decision_scope')
    if scope is None:return 'NO_MATCH'
    if list(Draft202012Validator(DECISION_SCOPE,format_checker=FormatChecker()).iter_errors(scope)):
        raise ValidationError('Malformed current invoice delegation scope')
    if any(type(value.get(k)) is not int for k in ['principal_id','delegate_id']):
        raise ValidationError('Exact integer scoped delegation identities required')
    if not isinstance(context,dict) or set(context)!={'decision_type','case_ref','action','currency','amount'}:
        raise ValidationError('Exact trusted invoice delegation context required')
    if scope['decision_type']!=context['decision_type'] or scope['case_ref']!=context['case_ref']:return 'NO_MATCH'
    if scope['actions'] is not None and context['action'] not in scope['actions']:return 'NO_MATCH'
    if scope['currency'] is not None and scope['currency']!=context['currency']:return 'NO_MATCH'
    if any(scope[k] is None for k in ['actions','currency','maximum_amount']):return 'UNCONFIGURED'
    if not isinstance(context['amount'],str):raise ValidationError('Native invoice amount must be exact decimal text')
    try:amount=Decimal(context['amount']);maximum=Decimal(scope['maximum_amount'])
    except InvalidOperation as exc:raise ValidationError('Exact finite delegation amounts required') from exc
    if not amount.is_finite() or not maximum.is_finite() or amount<=0 or maximum<=0:
        raise ValidationError('Positive finite native invoice and delegation limit required')
    return 'MATCH' if amount<=maximum else 'NO_MATCH'


def assert_delegate_eligible(actor,case,value,assignments):
    if not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('Current active delegate required')
    own=eligibility(case,assignments,actor.pk);combined=set(own['roles'])|{value['role']}
    if len(own['roles'])>1 and not own['eligible_role_bundle']:
        raise ValidationError('Current eligibility for the delegate nominated role bundle is required')
    if 'delegate_eligibility' in value:
        e=value['delegate_eligibility'];now=timezone.now()
        if set(e['roles'])!=combined or not instant(e['valid_from'])<=now<instant(e['valid_until']):
            raise ValidationError('Exact delegated role-bundle eligibility changed or is outside its explicit window')
    elif len(combined)>1 and not case.synthetic:
        raise ValidationError('Operational delegated role-bundle eligibility is not configured')
