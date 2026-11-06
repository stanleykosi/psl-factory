"""Reviewed metadata protocol. Authenticated remote claims are not vendor proof.

This code owns psl.domain-receipt/v1 and psl.destination-preflight/v1 only.
No implicit QuickBooks/GLPI/vendor protocol or arbitrary dispatch is supported.
"""
from types import SimpleNamespace
from datetime import datetime,timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate,digest
from adapters.forecast import obj,KEY
from adapters.readiness import binding as integration_binding,http,VERSION
from adapters.reconstitution import ROUTES

SHA={'type':'string','pattern':'^[a-f0-9]{64}$'}
NULL={'type':'null'}
OPTIONAL={'anyOf':[VERSION,NULL]}
COMMON={
    'implementation':{'enum':['authenticated_json_v1','reference_only']},
    'target_key':{'anyOf':[{'type':'string','pattern':'^endpoint:[a-z][a-z0-9_.-]{0,79}$'},NULL]},
    'credential_ref':{'anyOf':[{'type':'string','pattern':'^secret:[a-z][a-z0-9_.-]{0,79}$'},NULL]},
    'credential_revision':OPTIONAL,
    'principal_ref':{'anyOf':[{'type':'string','pattern':'^principal:[A-Za-z0-9_.@-]{1,80}$'},NULL]},
    'provider_ref':OPTIONAL,
    'contract_version':OPTIONAL,
}
PROVIDER=obj({**COMMON,'family':{'enum':list(ROUTES)},'source_payload_version':OPTIONAL,
    'operation_mapping':{'const':'sha256_original_operation_key_v1'},
    'intent_mapping':{'const':'postgres_jsonb_archived_job_row_sha256_v1'},
    'evidence_semantics':{'const':'authenticated_remote_receipt_claim'},
    'source_owner_ref':OPTIONAL})
PREREQUISITES=['identity','database','store','provisioning','outbound']
DESTINATION=obj({**COMMON,'destination_ref':VERSION,
    **{k+'_ref':OPTIONAL for k in PREREQUISITES},
    'activation_enabled':{'const':False},'archived_authority_accepted':{'const':False}})

def schema(kind):
    if kind not in ['provider','destination']:raise ValidationError('Typed provider or destination contract required')
    return PROVIDER if kind=='provider' else DESTINATION

def binding(contract):
    v=contract.payload;validate(schema(contract.kind),v)
    if v['implementation']!='authenticated_json_v1' or v['provider_ref'] is None:
        raise ValidationError('Reviewed authenticated implementation/provider remains unconfigured')
    version='psl.domain-receipt/v1' if contract.kind=='provider' else 'psl.destination-preflight/v1'
    if v['contract_version']!=version:raise ValidationError('Unsupported protocol version; install a reviewed adapter')
    if contract.kind=='provider' and any(v[k] is None for k in ['source_owner_ref','source_payload_version']):
        raise ValidationError('Explicit source owner and payload-version mapping required')
    # Reuse the reviewed endpoint, TLS, no-proxy/no-redirect and secret revision facilities.
    surrogate=SimpleNamespace(case=contract.plan.case,payload={**v,'kind':'adapter','model_id':None})
    return integration_binding(surrogate)

def timestamp(value):
    try:result=datetime.fromisoformat(value)
    except (ValueError,TypeError):raise ValidationError('Aware observation timestamp required') from None
    if timezone.is_naive(result):raise ValidationError('Aware observation timestamp required')
    return result

def current(result,seconds):
    observed=timestamp(result['observed_at']);expires=timestamp(result['expires_at']);now=timezone.now()
    if not observed<=now<min(expires,observed+timedelta(seconds=seconds)):
        raise ValidationError('Fresh bounded provider observation required')

def verify(contract,request,expected_binding,seconds):
    public,private=binding(contract)
    if public!=expected_binding:raise ValidationError('Reviewed endpoint/principal/credential binding changed')
    fields={'request_sha256':SHA,'provider_ref':VERSION,'principal_ref':COMMON['principal_ref'],'contract_version':VERSION,
            'observed_at':{'type':'string','maxLength':100},'expires_at':{'type':'string','maxLength':100}}
    if contract.kind=='provider':
        fields.update(outcome={'enum':['present','unknown','conflict']},receipt_ref=OPTIONAL,
                      receipt_sha256={'anyOf':[SHA,NULL]})
        path='/domain-receipts/verify'
    else:
        fields.update(prerequisites=obj({k:{'enum':['verified','missing','unknown','unsupported']} for k in PREREQUISITES}),
                      activation_enabled={'const':False},provisioning_executed={'const':False})
        path='/destinations/preflight'
    response=http(private,path,'POST',request);validate(obj(fields),response)
    for k in ['provider_ref','principal_ref','contract_version']:
        if response[k]!=contract.payload[k]:raise ValidationError('Exact reviewed provider identity/protocol required')
    if response['request_sha256']!=digest(request):raise ValidationError('Exact archive/case/effect/request binding required')
    current(response,seconds)
    if contract.kind=='provider':
        present=response['outcome']=='present'
        if present!=(response['receipt_ref'] is not None) or present!=(response['receipt_sha256'] is not None):
            raise ValidationError('Only present evidence carries exact receipt identity and digest')
    else:
        if any(response['prerequisites'][k]=='verified' and contract.payload[k+'_ref'] is None for k in PREREQUISITES):
            raise ValidationError('Unconfigured prerequisite cannot be verified')
    return {**response,'classification':public['classification'],'evidence_semantics':
            'authenticated_remote_receipt_claim' if contract.kind=='provider' else 'authenticated_remote_preflight_claim',
            'direct_vendor_verification':False,'activation_enabled':False,'business_jobs_reenacted':False}
