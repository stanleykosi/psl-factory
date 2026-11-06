"""Authenticated metadata intake with fresh source authority; no owner decisions or effects."""
import os,json,hmac,hashlib
from django.conf import settings
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from apps.core.models import Case
from apps.core.services import lock_case
from apps.identity.services import require
from apps.identity.models import Grant
from apps.policy.services import active_component,reference_values,decision_authority
from apps.policy.followup_transport_validators import INBOUND
from apps.documents.contracts import digest,validate
from adapters import finance_followup_protocol as wire
from . import receipt_followup as source
from .models import Invoice,InvoiceCorrection
from .transport_models import FinanceAuthenticatedIntake as Receipt

def credentials(case,sender):
    try:
        v=settings.FINANCE_INBOX_SENDERS[sender]
        assert set(v)=={'credential_ref','credential_revision','destination_ref','case_ids','classification'}
        assert str(case.pk) in v['case_ids'] and v['classification']==('synthetic' if case.synthetic else 'operational')
        credential=settings.READINESS_SECRET_REFS[v['credential_ref']]
        assert set(credential)=={'env','revision'} and credential['revision']==v['credential_revision']
        secret=os.environ[credential['env']]
        assert 32<=len(secret)<=4096 and '\n' not in secret and '\r' not in secret
    except (KeyError,AssertionError,TypeError):raise PermissionDenied('Current source inbox sender/key/case binding unavailable') from None
    binding=digest({'sender':sender,'registry':v,'key_binding':hmac.new(settings.SECRET_KEY.encode(),secret.encode(),hashlib.sha256).hexdigest()})
    return v,secret,binding

def authority(c,sender,purpose):
    cfg=active_component(INBOUND,c);v=reference_values(cfg)[0]
    if v['sender_ref']!=sender:raise PermissionDenied('Configured source sender required')
    a=get_user_model().objects.get(pk=v['principal_id'],is_active=True)
    source.access(a,c);role=decision_authority(a,c,v['principal_role'])
    if purpose=='receive':source.access(a,c,'receive');require(a,c,'finance.receipt_followup.transport_receive')
    return a,cfg,v,role

def response(receipt,op,sender,destination):
    return {'format':wire.ACK,'operation_key':op,'sender_ref':sender,'destination_ref':destination,'outcome':'acknowledged' if receipt else 'unknown',
        'envelope_sha256':receipt.sha256 if receipt else None,'request_sha256':receipt.followup.sha256 if receipt else None,'receipt_ref':str(receipt.pk) if receipt else None,
        'authenticated_transport':True,'execution_authorized':False,'financial_effect_verified':False,'debt_waived':False}

@transaction.atomic
def accept(a,c,cfg,v,role,binding,envelope):
    c=Case.objects.select_for_update().get(pk=c.pk)
    list(get_user_model().objects.select_for_update().filter(pk=a.pk))
    list(Grant.objects.select_for_update().filter(case=c,user=a).order_by('pk'))
    fresh,current,values,current_role=authority(c,v['sender_ref'],'receive')
    if fresh.pk!=a.pk or current.pk!=cfg.pk or values!=v or current_role!=role:
        raise PermissionDenied('Intake authority changed; authenticate a fresh command')
    a=fresh
    validate(wire.ENVELOPE,envelope)
    if envelope['sender_ref']!=v['sender_ref'] or envelope['destination_ref']!=v['destination_ref'] or envelope['projection']['source_case_id']!=str(c.pk):raise ValidationError('Exact destination/source-case envelope required')
    p=envelope['projection']
    if p['variant'] not in v['variants'] or not Invoice.objects.filter(pk=p['source_invoice_id'],case=c).exists():raise ValidationError('Configured same-case invoice subject required')
    if p['source_correction_id'] is not None and not InvoiceCorrection.objects.filter(pk=p['source_correction_id'],case=c,issue__invoice_id=p['source_invoice_id']).exists():raise ValidationError('Exact same-obligation correction subject required')
    old=Receipt.objects.filter(sender_ref=v['sender_ref'],destination_ref=v['destination_ref'],operation_key=envelope['operation_key']).first()
    if old:
        if old.sha256!=digest(envelope) or old.followup.case_id!=c.pk:raise ValidationError('Intake operation identity conflicts with prior immutable evidence')
        return old
    r=source.receive(a,c.pk,p,v['evidence_id'])
    return Receipt.objects.create(followup=r,sender_ref=v['sender_ref'],destination_ref=v['destination_ref'],operation_key=envelope['operation_key'],envelope=envelope,sha256=digest(envelope),
        pin={'policy':cfg.pk,'role':role,'binding_sha256':binding,'authenticated_transport':True,'execution_authorized':False,'financial_effect_verified':False,'debt_waived':False},actor=a)

@csrf_exempt
@transaction.atomic
def endpoint(request,case_id,operation_key):
    status=403
    try:
        validate(wire.SHA,operation_key)
        if request.method not in ['GET','POST'] or request.META.get('QUERY_STRING') or int(request.META.get('CONTENT_LENGTH') or 0)>wire.MAX_BYTES:raise ValidationError('Bounded signed inbox command required')
        c=Case.objects.get(pk=case_id);sender=request.headers.get('X-PSL-Sender','')
        registry,secret,binding=credentials(c,sender)
        if not c.synthetic and not request.is_secure():raise PermissionDenied('HTTPS required for operational intake')
        a,cfg,v,role=authority(c,sender,'receive' if request.method=='POST' else 'read')
        if registry['destination_ref']!=v['destination_ref']:raise PermissionDenied('Current destination binding differs')
        body=request.body
        if len(body)>wire.MAX_BYTES or request.method=='GET' and body:raise ValidationError('Bounded exact command required')
        wire.verify(secret,request.method,request.path,request.headers.get('X-PSL-Date',''),body,request.headers.get('X-PSL-Signature',''),v['signature_window_seconds'])
        if request.method=='POST':
            if request.content_type!='application/json':raise ValidationError('JSON metadata required')
            envelope=json.loads(body)
            if envelope.get('operation_key')!=operation_key:raise ValidationError('Exact operation identity required')
            receipt=accept(a,c,cfg,v,role,binding,envelope)
        else:
            receipt=Receipt.objects.filter(sender_ref=sender,destination_ref=v['destination_ref'],operation_key=operation_key,followup__case=c).select_related('followup').first()
        value=response(receipt,operation_key,sender,v['destination_ref']);raw=wire.encode(value)
        stamp=request.headers['X-PSL-Date']
        result=JsonResponse(value);result['X-PSL-Signature']=wire.signature(secret,'RESPONSE',request.path,stamp,raw);result['Cache-Control']='no-store';return result
    except (ValidationError,PermissionDenied,Case.DoesNotExist,get_user_model().DoesNotExist,ValueError,TypeError,KeyError,AttributeError):
        return JsonResponse({'held':'source_intake_authentication_scope_or_policy'},status=status,headers={'Cache-Control':'no-store'})
