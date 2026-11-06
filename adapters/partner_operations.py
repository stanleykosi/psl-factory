"""Supplied bounded interchange; does not authenticate a portal, meter or signed agreement."""
import json
from datetime import date
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate
from adapters.forecast import obj,rows,KEY
from adapters.reconciliation import at,TIME,NULLKEY

NULLDATE={'anyOf':[{'type':'string','format':'date'},{'type':'null'}]}
AGREEMENT=obj({'partner':KEY,'customer':KEY,'contract':KEY,'starts_on':{'type':'string','format':'date'},'expires_on':NULLDATE,'notice_on':NULLDATE,'auto_renewal':{'enum':['yes','no','unknown']},'clause_reference':KEY,'executed_evidence_id':{'anyOf':[{'type':'integer','minimum':1},{'type':'null'}]},'executed_sha256':{'anyOf':[{'type':'string','pattern':'^[a-f0-9]{64}$'},{'type':'null'}]}})
ONBOARDING=obj({'partner':KEY,'customer':KEY,'tracker':KEY,'reported_stage':NULLKEY,'reported_entry_at':{'anyOf':[TIME,{'type':'null'}]},'missing_documents':{'type':'array','maxItems':100,'uniqueItems':True,'items':KEY}})
EVENT=obj({'event':KEY,'user':NULLKEY,'product':KEY,'kind':KEY,'at':TIME,'quantity':{'anyOf':[{'type':'string','pattern':r'^(0|[1-9][0-9]{0,15})(\.[0-9]{1,8})?$'},{'type':'null'}]}})
ACTIVITY=obj({'partner':KEY,'customer':KEY,'source':KEY,'period':{'type':'string','pattern':r'^[0-9]{4}-(0[1-9]|1[0-2])$'},'extracted_at':TIME,'completeness':{'enum':['complete','partial','unknown']},'products':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':KEY},'events':rows(EVENT,0)})

def parse(kind,body):
    if not isinstance(body,str) or len(body)>100000:raise ValidationError('Partner source exceeds bounded input size')
    try:v=json.loads(body)
    except (ValueError,TypeError):raise ValidationError('Supply bounded structured partner evidence')
    validate({'agreement':AGREEMENT,'onboarding':ONBOARDING,'activity':ACTIVITY}[kind],v)
    if kind=='agreement':
        start=date.fromisoformat(v['starts_on']);end=date.fromisoformat(v['expires_on']) if v['expires_on'] else None
        if end and end<start:raise ValidationError('Agreement expiry precedes start')
        if v['notice_on'] and end and date.fromisoformat(v['notice_on'])>end:raise ValidationError('Notice date cannot follow a known expiry')
    elif kind=='onboarding':
        if v['reported_entry_at']:at(v['reported_entry_at'])
    else:
        date.fromisoformat(v['period']+'-01');extracted=at(v['extracted_at'])
        for row in v['events']:
            if at(row['at'])>extracted:raise ValidationError('Activity observation follows extraction')
    return v

class InternalPartnerFinanceAdapter:
    def lookup(self,job):
        from apps.baas.models import PartnerFinanceReceipt
        from apps.finance.analysis import digest
        r=PartnerFinanceReceipt.objects.filter(job=job).first()
        if r and (r.payload!=job.intent['public'] or r.sha256!=digest(job.intent['public'])):raise ValidationError('Finance receipt differs from exact handoff')
        return r.pk if r else None
    def deliver(self,pk,fence):
        from apps.baas.partner_delivery import deliver_local
        return deliver_local(pk,fence)
