"""Read-only supplied/mock interface. No transport, credentials or external write tools."""
import hashlib
import json
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from apps.documents.contracts import validate

FIELDS=['status','summary','owner','severity','opened_at','resolved_at','root_cause_ref']
SCHEMA={'type':'object','properties':{
    'protocol':{'const':'issue-reference-readback/v1'},
    'source_identity':{'type':'string','minLength':1,'maxLength':200},
    'source_ref':{'type':'string','minLength':1,'maxLength':240},
    'observed_at':{'type':'string','maxLength':64},
    'availability':{'enum':['available','unavailable','unknown']},
    'fields':{'type':'object','properties':{key:{'anyOf':[{'type':'string','maxLength':2000},{'type':'null'}]} for key in FIELDS},'additionalProperties':False}},
    'required':['protocol','source_identity','source_ref','observed_at','availability','fields'],'additionalProperties':False}


def read_supplied(contract,evidence,source_ref):
    if contract.mode not in ['supplied','synthetic_mock'] or contract.mode=='synthetic_mock' and not contract.case.synthetic:
        raise ValidationError('Only explicitly scoped supplied or synthetic mock readback is supported')
    if evidence.kind!='agent_private_issue_readback' or evidence.sha256!=hashlib.sha256(evidence.body.encode()).hexdigest():
        raise ValidationError('Exact immutable supplied reference readback required')
    try:data=json.loads(evidence.body)
    except (TypeError,ValueError):raise ValidationError('Typed supplied reference readback required') from None
    validate(SCHEMA,data)
    if data['source_identity']!=contract.source_identity or data['source_ref']!=source_ref:
        raise ValidationError('Readback must match the exact selected source and record identity')
    observed=parse_datetime(data['observed_at'])
    if not observed or timezone.is_naive(observed) or observed>timezone.now():
        raise ValidationError('A timezone-aware actual observation time, not a future time, is required')
    if set(data['fields'])-set(contract.allowed_fields):raise ValidationError('Readback includes fields outside the confirmed source read scope')
    if data['availability']!='available' and data['fields']:raise ValidationError('Unavailable or unknown sources cannot claim current fields')
    return data,observed
