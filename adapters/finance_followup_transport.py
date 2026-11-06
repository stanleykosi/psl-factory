"""Reviewed signed HTTPS metadata transfer. No arbitrary URLs, redirects or financial dispatch."""
import time,json,urllib.request,urllib.error,hmac
from types import SimpleNamespace
from django.core.exceptions import ValidationError
from apps.documents.contracts import digest
from . import finance_followup_protocol as wire
from .readiness import binding as integration_binding,NoRedirect

def binding(case,v):
    contract=SimpleNamespace(case=case,payload={'implementation':'authenticated_json_v1','kind':'adapter','family':'invoice','model_id':None,
        'target_key':v['endpoint_ref'],'credential_ref':v['credential_ref'],'credential_revision':v['credential_revision'],
        'principal_ref':v['sender_ref'],'contract_version':wire.FORMAT})
    public,private=integration_binding(contract)
    if len(private['secret'])<32:raise ValidationError('At least32 characters of source signing key required')
    return {**public,'implementation':'psl_signed_finance_v1','auth_mode':'hmac_sha256','sender_ref':v['sender_ref'],'destination_ref':v['destination_ref']},private

def request(job,method):
    current,private=binding(job.packet.mapping.plan.case,job.intent['rules'])
    if current!=job.intent['binding']:raise ValidationError('Original sender/endpoint/credential binding differs')
    envelope=job.intent['envelope'];path=wire.path(envelope['projection']['source_case_id'],job.operation_key)
    body=wire.encode(envelope) if method=='POST' else b'';stamp=str(int(time.time()))
    headers={'X-PSL-Sender':envelope['sender_ref'],'X-PSL-Date':stamp,'X-PSL-Signature':wire.signature(private['secret'],method,path,stamp,body),'Accept':'application/json'}
    if method=='POST':headers['Content-Type']='application/json'
    command=urllib.request.Request(private['url']+path,data=body if method=='POST' else None,method=method,headers=headers)
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        with opener.open(command,timeout=5) as response:
            raw=response.read(wire.MAX_BYTES+1)
            if len(raw)>wire.MAX_BYTES or response.headers.get_content_type()!='application/json':raise ValidationError('Bounded source JSON receipt required')
            value=json.loads(raw)
            expected=wire.signature(private['secret'],'RESPONSE',path,stamp,wire.encode(value))
            if not hmac.compare_digest(expected,response.headers.get('X-PSL-Signature','')):raise ValidationError('Authenticated source receipt signature differs')
    except urllib.error.HTTPError as e:
        if e.code in [400,401,403,409]:raise ValidationError('Current source inbox rejected command') from None
        raise ConnectionError('Source inbox unavailable') from None
    except (OSError,TimeoutError):raise ConnectionError('Source inbox outcome unresolved') from None
    except (ValueError,TypeError):raise ValidationError('Typed source receipt required') from None
    return wire.result(value,envelope)

class FinanceFollowupTransport:
    def lookup(self,job):return request(job,'GET')
    def deliver(self,job):
        value=request(job,'POST')
        if value is None:raise ConnectionError('Source intake was not acknowledged')
        return value
