"""PSL-owned inert metadata protocol; no vendor or financial execution contract."""
import hashlib,hmac,json,time
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate
from adapters.forecast import obj,KEY
from apps.finance.receipt_followup import PROJECTION,SHA
FORMAT='psl.finance-followup-delivery/v1'
ACK='psl.finance-followup-intake/v1'
ENVELOPE=obj({'format':{'const':FORMAT},'operation_key':SHA,'sender_ref':KEY,'destination_ref':KEY,
    'projection':PROJECTION,'publication_receipt_sha256':SHA})
RESULT=obj({'format':{'const':ACK},'operation_key':SHA,'sender_ref':KEY,'destination_ref':KEY,
    'outcome':{'enum':['unknown','acknowledged']},'envelope_sha256':{'anyOf':[SHA,{'type':'null'}]},
    'request_sha256':{'anyOf':[SHA,{'type':'null'}]},'receipt_ref':{'anyOf':[{'type':'string','pattern':'^[0-9]+$'},{'type':'null'}]},
    'authenticated_transport':{'const':True},'execution_authorized':{'const':False},'financial_effect_verified':{'const':False},'debt_waived':{'const':False}})
MAX_BYTES=16384

def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def path(case_id,operation_key):return f'/finance/followup-inbox/{case_id}/{operation_key}/'
def signature(secret,method,path,stamp,body):
    data='\n'.join([method,path,stamp,hashlib.sha256(body).hexdigest()]).encode()
    return hmac.new(secret.encode(),data,hashlib.sha256).hexdigest()
def verify(secret,method,path,stamp,body,supplied,seconds):
    try:
        if not stamp.isdigit() or len(stamp)>20 or abs(time.time()-int(stamp))>seconds:raise ValueError()
    except (ValueError,AttributeError,OverflowError):raise ValidationError('Fresh authenticated timestamp required') from None
    if not isinstance(supplied,str) or not hmac.compare_digest(signature(secret,method,path,stamp,body),supplied):raise ValidationError('Authentication rejected')
def result(value,envelope):
    from apps.documents.contracts import digest
    validate(RESULT,value)
    if any(value[k]!=envelope[k] for k in ['operation_key','sender_ref','destination_ref']):raise ValidationError('Exact source intake receipt identity required')
    found=value['outcome']=='acknowledged'
    if found:
        if value['envelope_sha256']!=digest(envelope) or value['request_sha256']!=digest(envelope['projection']) or value['receipt_ref'] is None:raise ValidationError('Exact delivered metadata receipt required')
    elif any(value[k] is not None for k in ['envelope_sha256','request_sha256','receipt_ref']):raise ValidationError('Unknown intake cannot carry a receipt')
    return value if found else None
